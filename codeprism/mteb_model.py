"""MTEB adapter.

The organizers' harness expects a class called PrePostPipelineEncoder that
subclasses AbsEncoder. This one does that, and it also implements index() and
search() so MTEB hands it the whole retrieval job instead of only asking for
embeddings. That is what lets the keyword search and the second pass fusion
run inside mteb.evaluate.

encode() still works on its own and returns plain dense embeddings of the
preprocessed text, so the class stays a valid encoder for any tool that only
calls encode().
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from mteb.models.abs_encoder import AbsEncoder
from mteb.models.model_meta import ModelMeta, ScoringFunction
from mteb.types import PromptType

from .retriever import CodeIndex, HybridRetriever, PipelineConfig


def _texts_from_batches(inputs: Any) -> list[str]:
    texts: list[str] = []
    for batch in inputs:
        texts.extend(list(batch["text"]))
    return texts


class PrePostPipelineEncoder(AbsEncoder):
    def __init__(self, config: "PipelineConfig | dict | str | None" = None, retriever: HybridRetriever | None = None):
        cfg = config if isinstance(config, PipelineConfig) else PipelineConfig.load(config)
        self.cfg = cfg
        self.retriever = retriever or HybridRetriever(cfg)
        self.model = self.retriever.embedder
        self.mteb_model_meta = ModelMeta(
            loader=None,
            name=f"codeprism/hybrid-{cfg.model.split('/')[-1]}",
            revision="1",
            release_date="2026-09-29",
            languages=["eng-Latn", "python-Code", "javascript-Code"],
            n_parameters=None,
            memory_usage_mb=None,
            max_tokens=float(cfg.max_seq_length or 512),
            embed_dim=None,
            license="mit",
            open_weights=True,
            public_training_code=None,
            public_training_data=None,
            framework=["Sentence Transformers"],
            similarity_fn_name=ScoringFunction.COSINE,
            use_instructions=False,
            training_datasets=None,
        )
        self._index: CodeIndex | None = None
        self.stats: dict[str, float] = {}

    # ---- plain encoder interface ---------------------------------------------

    def encode(
        self,
        inputs: Any,
        *,
        task_metadata: Any = None,
        hf_split: str = "",
        hf_subset: str = "",
        prompt_type: PromptType | None = None,
        **kwargs: Any,
    ) -> np.ndarray:
        texts = _texts_from_batches(inputs)
        bs = int(kwargs.get("batch_size", self.cfg.batch_size))
        if prompt_type == PromptType.query:
            prepared = [self.retriever._query_dense_texts(t)[0] for t in texts]
            return self.retriever.embedder.embed(prepared, "query_full", bs)
        prepared = [self.retriever.doc_dense_text(t) for t in texts]
        return self.retriever.embedder.embed(prepared, "doc", bs)

    # ---- search interface (what mteb.evaluate uses) ----------------------------

    def index(
        self,
        corpus: Any,
        *,
        task_metadata: Any = None,
        hf_split: str = "",
        hf_subset: str = "",
        encode_kwargs: dict | None = None,
        num_proc: int | None = None,
    ) -> None:
        ids = [str(i) for i in corpus["id"]]
        texts = _combine_title(corpus)
        bs = (encode_kwargs or {}).get("batch_size")
        if bs:
            self.retriever.cfg.batch_size = int(bs)
        self._index = self.retriever.build_index(ids, texts)
        self.stats["index_seconds"] = self._index.build_seconds
        self.stats["docs"] = len(ids)

    def search(
        self,
        queries: Any,
        *,
        task_metadata: Any = None,
        hf_split: str = "",
        hf_subset: str = "",
        top_k: int = 100,
        encode_kwargs: dict | None = None,
        top_ranked: Any = None,
        num_proc: int | None = None,
    ) -> dict[str, dict[str, float]]:
        if self._index is None:
            raise ValueError("index() must be called before search()")
        qids = [str(i) for i in queries["id"]]
        texts = list(queries["text"])
        if "instruction" in queries.column_names:
            texts = [t if not ins else f"{t} {ins}" for t, ins in zip(texts, queries["instruction"])]

        t0 = time.perf_counter()
        ranked = self.retriever.search(self._index, texts, top_k=top_k)
        seconds = time.perf_counter() - t0
        self.stats["search_seconds"] = seconds
        self.stats["queries"] = len(qids)
        self.stats["ms_per_query_after_encoding"] = 1000 * seconds / max(len(qids), 1)

        if top_ranked is not None:
            # reranking tasks pass a candidate list per query; keep only those
            out: dict[str, dict[str, float]] = {}
            for qid, hits in zip(qids, ranked):
                allowed = set(top_ranked.get(qid, []))
                out[qid] = {d: s for d, s in hits if d in allowed} if allowed else dict(hits)
            return out
        return {qid: dict(hits) for qid, hits in zip(qids, ranked)}


def _combine_title(corpus: Any) -> list[str]:
    texts = [t or "" for t in corpus["text"]]
    if "title" in corpus.column_names:
        titles = corpus["title"]
        texts = [f"{ti} {t}".strip() if ti else t for ti, t in zip(titles, texts)]
    return texts
