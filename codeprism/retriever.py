"""The retrieval pipeline, independent of MTEB.

Stages for one query:

  1. Preprocess. Split the problem into a full view and a statement view,
     pull out content words, detect topics.
  2. First pass. Dense similarity (both views) and BM25 over the whole corpus.
  3. Second pass. Combine dense, BM25 and topic agreement into one score.
     Scores are standardised per query first, so the weights mean the same
     thing for every query.

The same class serves the MTEB evaluation, the command line demo and the
versioned index.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Sequence

import numpy as np

from .categories import code_topics, query_topics, top_tags, topic_similarity
from .embedders import CachedEmbedder, build_embedder
from .lexical import BM25Index
from .preprocess import clean_code, code_lexical_terms, query_lexical_terms, query_views


@dataclass
class PipelineConfig:
    # model
    model: str = "gte-modernbert-base"
    max_seq_length: int | None = None  # None keeps the preset value
    cache_path: str | None = ".cache/embeddings.sqlite"
    batch_size: int = 32
    # preprocessing
    doc_max_chars: int = 1800  # about 512 tokens of code, so head and tail both survive truncation
    augment_tags: bool = False  # write topic tags into the text the model sees
    # first pass weights
    w_full: float = 0.6  # dense score weight for the full query view
    w_stmt: float = 0.4  # dense score weight for the statement-only view
    # second pass fusion
    fusion: str = "zscore"  # "zscore" or "rrf"
    bm25_weight: float = 0.25
    topic_weight: float = 0.15
    bm25_k1: float = 1.2
    bm25_b: float = 0.75
    rrf_k: int = 60
    query_chunk: int = 128

    @classmethod
    def load(cls, path_or_dict: "str | dict | None") -> "PipelineConfig":
        if path_or_dict is None:
            return cls()
        if isinstance(path_or_dict, str):
            with open(path_or_dict) as f:
                data = json.load(f)
        else:
            data = dict(path_or_dict)
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


@dataclass
class CodeIndex:
    ids: list[str]
    texts: list[str]
    dense: np.ndarray
    bm25: BM25Index
    topics: np.ndarray
    build_seconds: float = 0.0
    embedded_new: int = 0
    embedded_cached: int = 0

    def __len__(self) -> int:
        return len(self.ids)


def _zscore(x: np.ndarray) -> np.ndarray:
    mu = x.mean(axis=1, keepdims=True)
    sd = x.std(axis=1, keepdims=True)
    sd[sd < 1e-6] = 1.0
    return (x - mu) / sd


def _rank_score(x: np.ndarray, k: int) -> np.ndarray:
    order = np.argsort(-x, axis=1)
    ranks = np.empty_like(order)
    rows = np.arange(x.shape[0])[:, None]
    ranks[rows, order] = np.arange(x.shape[1])[None, :]
    return 1.0 / (k + ranks + 1.0)


class HybridRetriever:
    def __init__(self, config: PipelineConfig | None = None, embedder: CachedEmbedder | None = None):
        self.cfg = config or PipelineConfig()
        if embedder is None:
            overrides = {}
            if self.cfg.max_seq_length:
                overrides["max_seq_length"] = self.cfg.max_seq_length
            embedder = build_embedder(self.cfg.model, cache_path=self.cfg.cache_path, **overrides)
        self.embedder = embedder

    # ------------------------------------------------------------------ text views

    def doc_dense_text(self, code: str, topics: np.ndarray | None = None) -> str:
        text = clean_code(code, self.cfg.doc_max_chars)
        if self.cfg.augment_tags:
            tags = top_tags(code_topics(code) if topics is None else topics)
            if tags:
                text = f"# topics: {', '.join(tags)}\n{text}"
        return text

    def _query_dense_texts(self, raw: str) -> tuple[str, str | None]:
        views = query_views(raw)
        full, stmt = views.full, views.statement
        if self.cfg.augment_tags:
            tags = top_tags(query_topics(raw))
            if tags:
                prefix = f"Topics: {', '.join(tags)}. "
                full = prefix + full
                stmt = prefix + stmt
        return full, (None if stmt == full else stmt)

    # ------------------------------------------------------------------ indexing

    def build_index(self, ids: Sequence[str], texts: Sequence[str]) -> CodeIndex:
        t0 = time.perf_counter()
        hits0, miss0 = self.embedder.hits, self.embedder.misses
        topics = np.stack([code_topics(t) for t in texts]) if len(texts) else np.zeros((0, 1), np.float32)
        dense_texts = [self.doc_dense_text(t, topics[i]) for i, t in enumerate(texts)]
        dense = self.embedder.embed(dense_texts, "doc", self.cfg.batch_size)
        bm25 = BM25Index(self.cfg.bm25_k1, self.cfg.bm25_b).fit([code_lexical_terms(t) for t in texts])
        return CodeIndex(
            ids=list(ids),
            texts=list(texts),
            dense=dense,
            bm25=bm25,
            topics=topics,
            build_seconds=time.perf_counter() - t0,
            embedded_new=self.embedder.misses - miss0,
            embedded_cached=self.embedder.hits - hits0,
        )

    # ------------------------------------------------------------------ searching

    def search(
        self, index: CodeIndex, queries: Sequence[str], top_k: int = 10
    ) -> list[list[tuple[str, float]]]:
        """Return, per query, a list of (doc_id, score) sorted best first."""
        cfg = self.cfg
        nq, nd = len(queries), len(index)
        if nq == 0 or nd == 0:
            return [[] for _ in range(nq)]
        top_k = min(top_k, nd)

        # pass 1a: dense views
        pairs = [self._query_dense_texts(q) for q in queries]
        full_vec = self.embedder.embed([p[0] for p in pairs], "query_full", cfg.batch_size)
        stmt_idx = [i for i, p in enumerate(pairs) if p[1] is not None]
        stmt_vec = None
        if stmt_idx:
            stmt_vec = self.embedder.embed([pairs[i][1] for i in stmt_idx], "query_stmt", cfg.batch_size)
        has_stmt = np.zeros(nq, dtype=bool)
        has_stmt[stmt_idx] = True
        stmt_row = {i: r for r, i in enumerate(stmt_idx)}

        q_terms = [query_lexical_terms(query_views(q).full) for q in queries]
        q_topics = np.stack([query_topics(q) for q in queries])

        results: list[list[tuple[str, float]]] = []
        for start in range(0, nq, cfg.query_chunk):
            end = min(start + cfg.query_chunk, nq)
            rows = range(start, end)

            dense = full_vec[start:end] @ index.dense.T
            if stmt_vec is not None:
                # queries that have a distinct statement view blend both views
                blended = dense.copy()
                for local, i in enumerate(rows):
                    if has_stmt[i]:
                        s = stmt_vec[stmt_row[i]] @ index.dense.T
                        blended[local] = cfg.w_full * dense[local] + cfg.w_stmt * s
                dense = blended

            bm = index.bm25.scores(q_terms[start:end])
            topic = topic_similarity(q_topics[start:end], index.topics)

            if cfg.fusion == "rrf":
                score = _rank_score(dense, cfg.rrf_k)
                if cfg.bm25_weight:
                    score = score + cfg.bm25_weight * _rank_score(bm, cfg.rrf_k)
                if cfg.topic_weight:
                    score = score + cfg.topic_weight * _rank_score(topic, cfg.rrf_k)
            else:
                score = _zscore(dense)
                if cfg.bm25_weight:
                    score = score + cfg.bm25_weight * _zscore(bm)
                if cfg.topic_weight:
                    score = score + cfg.topic_weight * _zscore(topic)

            k = min(top_k, nd)
            part = np.argpartition(-score, k - 1, axis=1)[:, :k]
            for local in range(end - start):
                cand = part[local]
                order = cand[np.argsort(-score[local, cand])]
                results.append([(index.ids[j], float(score[local, j])) for j in order])
        return results
