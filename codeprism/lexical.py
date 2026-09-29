"""BM25 keyword search implemented with scipy sparse matrices.

rank_bm25 loops in Python per document, which is far too slow for thousands
of queries against thousands of snippets. Here the whole corpus is one sparse
matrix and a batch of queries is one sparse matrix product.
"""

from __future__ import annotations

from collections import Counter
from typing import Sequence

import numpy as np
from scipy import sparse


class BM25Index:
    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.vocab: dict[str, int] = {}
        self.weights: sparse.csr_matrix | None = None  # (docs, terms)
        self.n_docs = 0

    def fit(self, docs_terms: Sequence[Sequence[str]]) -> "BM25Index":
        self.n_docs = len(docs_terms)
        vocab: dict[str, int] = {}
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        lengths = np.zeros(self.n_docs, dtype=np.float32)
        for i, terms in enumerate(docs_terms):
            counts = Counter(terms)
            lengths[i] = len(terms)
            for term, c in counts.items():
                j = vocab.setdefault(term, len(vocab))
                rows.append(i)
                cols.append(j)
                vals.append(float(c))
        self.vocab = vocab
        tf = sparse.csr_matrix(
            (vals, (rows, cols)), shape=(self.n_docs, max(len(vocab), 1)), dtype=np.float32
        )
        avgdl = float(lengths.mean()) if self.n_docs else 1.0
        avgdl = avgdl or 1.0
        df = np.asarray((tf > 0).sum(axis=0)).ravel().astype(np.float32)
        idf = np.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)

        tf = tf.tocoo()
        denom = tf.data + self.k1 * (1.0 - self.b + self.b * lengths[tf.row] / avgdl)
        data = idf[tf.col] * (tf.data * (self.k1 + 1.0)) / denom
        self.weights = sparse.csr_matrix(
            (data.astype(np.float32), (tf.row, tf.col)), shape=tf.shape
        )
        return self

    def _query_matrix(self, queries_terms: Sequence[Sequence[str]]) -> sparse.csr_matrix:
        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        for i, terms in enumerate(queries_terms):
            for term, c in Counter(terms).items():
                j = self.vocab.get(term)
                if j is None:
                    continue
                rows.append(i)
                cols.append(j)
                # damp repeated query words
                vals.append(1.0 + np.log(c))
        return sparse.csr_matrix(
            (vals, (rows, cols)), shape=(len(queries_terms), self.weights.shape[1]), dtype=np.float32
        )

    def scores(self, queries_terms: Sequence[Sequence[str]]) -> np.ndarray:
        """Dense (n_queries, n_docs) score matrix. Call in chunks for big sets."""
        if self.weights is None:
            raise RuntimeError("fit() first")
        q = self._query_matrix(queries_terms)
        return np.asarray((q @ self.weights.T).todense(), dtype=np.float32)
