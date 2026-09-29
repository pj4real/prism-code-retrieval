"""Embedding backends and the on-disk embedding cache.

The cache matters for two reasons. During tuning it means the model runs once
per text and every later experiment is instant. For code that changes between
versions it means only changed snippets are embedded again.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import zlib
from typing import Iterable, Sequence

import numpy as np

from .preprocess import code_lexical_terms

# Presets for models that are known to load with plain sentence-transformers.
# max_seq_length is kept at 512 to keep CPU time reasonable.
PRESETS: dict[str, dict] = {
    "gte-modernbert-base": {"model_name": "Alibaba-NLP/gte-modernbert-base"},
    "bge-base": {
        "model_name": "BAAI/bge-base-en-v1.5",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
    },
    "bge-small": {
        "model_name": "BAAI/bge-small-en-v1.5",
        "query_prefix": "Represent this sentence for searching relevant passages: ",
    },
    "e5-base": {
        "model_name": "intfloat/e5-base-v2",
        "query_prefix": "query: ",
        "doc_prefix": "passage: ",
    },
    "minilm": {"model_name": "sentence-transformers/all-MiniLM-L6-v2", "max_seq_length": 256},
    # Needs trust_remote_code and the einops package.
    "coderank": {
        "model_name": "nomic-ai/CodeRankEmbed",
        "query_prefix": "Represent this query for searching relevant code: ",
        "trust_remote_code": True,
    },
    # No download, no model. Keyword hashing only. For tests and emergencies.
    "hashing": {"model_name": "hashing"},
}


def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return (x / n).astype(np.float32)


class EmbeddingCache:
    """sqlite key/value store: sha1(model|kind|text) -> float32 vector."""

    def __init__(self, path: str | None) -> None:
        self.path = path
        self._mem: dict[str, np.ndarray] = {}
        self._db: sqlite3.Connection | None = None
        if path:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            self._db = sqlite3.connect(path)
            self._db.execute("CREATE TABLE IF NOT EXISTS emb (k TEXT PRIMARY KEY, v BLOB)")
            self._db.commit()

    def get_many(self, keys: Sequence[str]) -> dict[str, np.ndarray]:
        found = {k: self._mem[k] for k in keys if k in self._mem}
        missing = [k for k in keys if k not in found]
        if self._db is not None and missing:
            for i in range(0, len(missing), 500):
                chunk = missing[i : i + 500]
                marks = ",".join("?" * len(chunk))
                rows = self._db.execute(f"SELECT k, v FROM emb WHERE k IN ({marks})", chunk)
                for k, blob in rows:
                    vec = np.frombuffer(blob, dtype=np.float32)
                    self._mem[k] = vec
                    found[k] = vec
        return found

    def put_many(self, items: dict[str, np.ndarray]) -> None:
        self._mem.update(items)
        if self._db is not None and items:
            self._db.executemany(
                "INSERT OR REPLACE INTO emb (k, v) VALUES (?, ?)",
                [(k, v.astype(np.float32).tobytes()) for k, v in items.items()],
            )
            self._db.commit()


class BaseEmbedder:
    name = "base"

    def embed(self, texts: Sequence[str], kind: str, batch_size: int = 32) -> np.ndarray:
        raise NotImplementedError


class SentenceTransformerEmbedder(BaseEmbedder):
    def __init__(
        self,
        model_name: str,
        max_seq_length: int = 512,
        query_prefix: str = "",
        doc_prefix: str = "",
        trust_remote_code: bool = False,
        device: str = "cpu",
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.name = model_name
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self.model = SentenceTransformer(
            model_name, device=device, trust_remote_code=trust_remote_code
        )
        if max_seq_length:
            self.model.max_seq_length = max_seq_length

    def embed(self, texts: Sequence[str], kind: str, batch_size: int = 32) -> np.ndarray:
        prefix = self.query_prefix if kind.startswith("query") else self.doc_prefix
        batch = [prefix + t for t in texts]
        vecs = self.model.encode(
            batch,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=len(batch) > 256,
        )
        return np.asarray(vecs, dtype=np.float32)


class HashingEmbedder(BaseEmbedder):
    """Signed feature hashing of code words. Not a real semantic model.

    It exists so the whole pipeline can be run and tested with no downloads.
    """

    def __init__(self, dim: int = 1024) -> None:
        self.name = f"hashing-{dim}"
        self.dim = dim

    def embed(self, texts: Sequence[str], kind: str, batch_size: int = 32) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            terms = code_lexical_terms(text)
            grams = terms + [a + "_" + b for a, b in zip(terms, terms[1:])]
            for g in grams:
                h = zlib.crc32(g.encode("utf-8"))
                out[i, h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0
            row = out[i]
            out[i] = np.sign(row) * np.log1p(np.abs(row))
        return _l2(out)


class CachedEmbedder:
    """Wraps an embedder with the sqlite cache. Same texts are never embedded twice."""

    def __init__(self, embedder: BaseEmbedder, cache: EmbeddingCache | None = None) -> None:
        self.embedder = embedder
        self.cache = cache or EmbeddingCache(None)
        self.hits = 0
        self.misses = 0

    @property
    def name(self) -> str:
        return self.embedder.name

    def _key(self, kind: str, text: str) -> str:
        raw = f"{self.embedder.name}|{kind}|{text}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()

    def embed(self, texts: Sequence[str], kind: str, batch_size: int = 32) -> np.ndarray:
        keys = [self._key(kind, t) for t in texts]
        found = self.cache.get_many(list(dict.fromkeys(keys)))
        todo: dict[str, str] = {}
        for k, t in zip(keys, texts):
            if k not in found and k not in todo:
                todo[k] = t
        self.hits += len(keys) - len(todo)
        self.misses += len(todo)
        if todo:
            todo_keys = list(todo)
            vecs = self.embedder.embed([todo[k] for k in todo_keys], kind, batch_size)
            new = {k: v for k, v in zip(todo_keys, vecs)}
            self.cache.put_many(new)
            found.update(new)
        return np.stack([found[k] for k in keys]).astype(np.float32)


def build_embedder(
    preset_or_model: str,
    *,
    cache_path: str | None = None,
    device: str = "cpu",
    **overrides,
) -> CachedEmbedder:
    """Create a cached embedder from a preset name or a raw model id."""
    conf = dict(PRESETS.get(preset_or_model, {"model_name": preset_or_model}))
    conf.update({k: v for k, v in overrides.items() if v is not None})
    if conf["model_name"] == "hashing":
        base: BaseEmbedder = HashingEmbedder()
    else:
        try:
            import torch

            torch.set_num_threads(os.cpu_count() or 1)
        except Exception:
            pass
        base = SentenceTransformerEmbedder(device=device, **conf)
    return CachedEmbedder(base, EmbeddingCache(cache_path))
