"""Retrieval across versions of a codebase (goals P1 and the bonus).

Idea: a snippet's embedding depends only on its text. So the text is hashed,
and each unique text is embedded once, forever (the sqlite cache does this).
A new version of the code then costs one embedding per changed snippet, and
building a searchable index for any version is: look up cached vectors, refit
BM25 (well under a second for thousands of snippets).

Two ways to search:

  search(query, version="v3")      one version, the normal case (P1)
  search(query, version="all")     every version at once (bonus). Hits are
                                   grouped by snippet identity. Versions whose
                                   text is identical are folded into one hit,
                                   and versions that changed the snippet are
                                   listed with their own scores, so near
                                   duplicates do not crowd out other results.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Sequence

from .retriever import CodeIndex, HybridRetriever


def content_hash(text: str) -> str:
    normalised = "\n".join(line.rstrip() for line in text.strip().split("\n"))
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:16]


@dataclass
class VersionStats:
    version: str
    snippets: int
    new_or_changed: int
    unchanged: int
    seconds: float


@dataclass
class Hit:
    id: str
    score: float
    version: str  # the version this hit's text comes from
    text: str
    location: str = ""  # file and line range in that version, when known
    same_in_versions: list[str] = field(default_factory=list)  # other versions with identical text
    changed_in_versions: list[tuple[str, float]] = field(default_factory=list)  # (version, score) with different text


class VersionedIndex:
    def __init__(self, retriever: HybridRetriever):
        self.retriever = retriever
        self.versions: dict[str, dict[str, str]] = {}  # version -> {snippet id: text}
        self.locations: dict[str, dict[str, str]] = {}  # version -> {snippet id: "file:start-end"}
        self._index_cache: dict[tuple[str, ...], CodeIndex] = {}

    # ---------------------------------------------------------------- building

    def add_version(
        self, version: str, snippets: dict[str, str], locations: dict[str, str] | None = None
    ) -> VersionStats:
        """Register a version. Embeds only text the cache has not seen.

        snippets maps a stable snippet id (for code, file plus function name,
        so it survives edits above it) to its text. locations optionally maps
        the same ids to a display label such as 'src/a.js:10-24'.
        """
        t0 = time.perf_counter()
        self.versions[version] = dict(snippets)
        self.locations[version] = dict(locations or {})
        self._index_cache.clear()
        before = self.retriever.embedder.misses
        # build the index for this version now; unchanged snippets come from the cache
        self._index_for((version,))
        new = self.retriever.embedder.misses - before
        return VersionStats(
            version=version,
            snippets=len(snippets),
            new_or_changed=new,
            unchanged=max(len(snippets) - new, 0),
            seconds=time.perf_counter() - t0,
        )

    def _index_for(self, versions: Sequence[str]) -> CodeIndex:
        key = tuple(versions)
        if key in self._index_cache:
            return self._index_cache[key]
        ids: list[str] = []
        texts: list[str] = []
        seen: set[tuple[str, str]] = set()
        for v in versions:
            for sid, text in self.versions[v].items():
                pair = (sid, content_hash(text))
                if len(versions) > 1 and pair in seen:
                    continue  # identical text already present from an earlier version
                seen.add(pair)
                # in multi-version mode the id carries the content hash so each distinct text is one entry
                ids.append(sid if len(versions) == 1 else f"{sid}@{pair[1]}")
                texts.append(text)
        index = self.retriever.build_index(ids, texts)
        self._index_cache[key] = index
        return index

    # ---------------------------------------------------------------- searching

    def search(self, query: str, version: str = "latest", top_k: int = 5) -> list[Hit]:
        names = list(self.versions)
        if version == "latest":
            version = names[-1]
        if version == "all":
            return self._search_all(query, names, top_k)
        index = self._index_for((version,))
        hits = self.retriever.search(index, [query], top_k=top_k)[0]
        return [
            Hit(
                id=i,
                score=s,
                version=version,
                text=self.versions[version][i],
                location=self.locations[version].get(i, ""),
            )
            for i, s in hits
        ]

    def _search_all(self, query: str, names: list[str], top_k: int) -> list[Hit]:
        index = self._index_for(tuple(names))
        # ask for extra so that grouping by snippet still leaves top_k distinct snippets
        raw = self.retriever.search(index, [query], top_k=min(len(index), max(top_k * 6, 30)))[0]

        # which versions carry each (snippet id, content hash)
        holders: dict[tuple[str, str], list[str]] = {}
        for v in names:
            for sid, text in self.versions[v].items():
                holders.setdefault((sid, content_hash(text)), []).append(v)

        text_of = dict(zip(index.ids, index.texts))
        grouped: dict[str, list[tuple[str, float, str]]] = {}
        for entry_id, score in raw:
            sid, _, h = entry_id.rpartition("@")
            grouped.setdefault(sid, []).append((h, score, entry_id))

        hits: list[Hit] = []
        for sid, variants in grouped.items():
            variants.sort(key=lambda x: -x[1])
            best_hash, best_score, best_entry = variants[0]
            same = holders[(sid, best_hash)]
            hits.append(
                Hit(
                    id=sid,
                    score=best_score,
                    version=same[-1],
                    text=text_of[best_entry],
                    location=self.locations[same[-1]].get(sid, ""),
                    same_in_versions=same,
                    changed_in_versions=[(holders[(sid, h)][-1], s) for h, s, _ in variants[1:]],
                )
            )
        hits.sort(key=lambda h: -h.score)
        return hits[:top_k]
