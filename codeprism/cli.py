"""Command line entry point.

    python -m codeprism.cli demo                 scripted walkthrough on the sample repo
    python -m codeprism.cli search --repo DIR "where is the bluetooth deeplink built?"
    python -m codeprism.cli history --versions v1=DIR1 v2=DIR2 "how are utterances cleaned?"

Add --model hashing to run with no model download (keyword hashing only, for
a quick look). The default model comes from configs/tuned.json or
configs/default.json.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from .chunker import chunk_repo
from .retriever import HybridRetriever, PipelineConfig
from .versioned import VersionedIndex

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "demo" / "sample_repo"


def load_config(path: str | None, model: str | None) -> PipelineConfig:
    if path is None:
        tuned, default = ROOT / "configs" / "tuned.json", ROOT / "configs" / "default.json"
        path = str(tuned if tuned.exists() else default)
    cfg = PipelineConfig.load(path)
    if model:
        cfg.model = model
    if not Path(cfg.cache_path or "").is_absolute() and cfg.cache_path:
        cfg.cache_path = str(ROOT / cfg.cache_path)
    return cfg


def preview(text: str, lines: int = 4) -> str:
    body = [ln for ln in text.split("\n") if ln.strip()][:lines]
    return "\n".join("      | " + ln[:100] for ln in body)


def label(h) -> str:
    return h.location or h.id


def print_hits(hits) -> None:
    for rank, h in enumerate(hits, 1):
        print(f"  {rank}. {label(h)}   score {h.score:.2f}")
        print(preview(h.text))


def repo_to_snippets(path: str | Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return ({stable id: text}, {stable id: 'file:start-end'}).

    The stable id is file plus function name, so a function keeps its identity
    when lines above it are added or removed between versions.
    """
    texts: dict[str, str] = {}
    where: dict[str, str] = {}
    for s in chunk_repo(path):
        key = f"{s.path}::{s.name}"
        n = 2
        while key in texts:
            key = f"{s.path}::{s.name}#{n}"
            n += 1
        texts[key] = s.text
        where[key] = s.id
    return texts, where


def cmd_search(args) -> None:
    cfg = load_config(args.config, args.model)
    retriever = HybridRetriever(cfg)
    texts, where = repo_to_snippets(args.repo)
    vi = VersionedIndex(retriever)
    stats = vi.add_version("current", texts, where)
    print(f"indexed {stats.snippets} snippets in {stats.seconds:.1f}s\n")
    t0 = time.perf_counter()
    hits = vi.search(args.query, "current", top_k=args.top_k)
    ms = 1000 * (time.perf_counter() - t0)
    print(f"query: {args.query}   ({ms:.0f} ms)")
    print_hits(hits)


def cmd_history(args) -> None:
    cfg = load_config(args.config, args.model)
    retriever = HybridRetriever(cfg)
    vi = VersionedIndex(retriever)
    for spec in args.versions:
        name, _, path = spec.partition("=")
        texts, where = repo_to_snippets(path)
        stats = vi.add_version(name, texts, where)
        print(f"{name}: {stats.snippets} snippets, {stats.new_or_changed} embedded, {stats.unchanged} reused, {stats.seconds:.1f}s")
    print()
    show_across_versions(vi, args.query, args.top_k)


def show_across_versions(vi: VersionedIndex, query: str, top_k: int) -> None:
    t0 = time.perf_counter()
    hits = vi.search(query, "all", top_k=top_k)
    ms = 1000 * (time.perf_counter() - t0)
    print(f"query across all versions: {query}   ({ms:.0f} ms)")
    for rank, h in enumerate(hits, 1):
        same = ", ".join(h.same_in_versions)
        print(f"  {rank}. {label(h)}   score {h.score:.2f}   best text is in: {same}")
        for v, s in h.changed_in_versions:
            print(f"       also matched in {v} with different text (score {s:.2f})")
        print(preview(h.text, 3))


DEMO_QUERIES = [
    "How is the input cleaned before it is passed to the router?",
    "Where is the deeplink into the Settings app created?",
    "Which code retries a failed operation and waits longer each time?",
    "Where are passwords kept out of the logs?",
    "How does the assistant decide which agent should handle a request?",
]


def cmd_demo(args) -> None:
    cfg = load_config(args.config, args.model)
    print(f"model: {cfg.model}   fusion: {cfg.fusion}   bm25 weight: {cfg.bm25_weight}   topic weight: {cfg.topic_weight}\n")
    retriever = HybridRetriever(cfg)
    vi = VersionedIndex(retriever)

    print("== Building an index for each version of the sample repo ==")
    print("Only new or changed functions are embedded. Unchanged ones come from the cache.\n")
    for v in ("v1", "v2", "v3"):
        texts, where = repo_to_snippets(SAMPLE / v)
        stats = vi.add_version(v, texts, where)
        print(f"  {v}: {stats.snippets:3d} functions   embedded {stats.new_or_changed:3d}   reused {stats.unchanged:3d}   {stats.seconds:5.1f}s")

    print("\n== Queries against the latest version (v3) ==")
    latencies = []
    for q in DEMO_QUERIES:
        t0 = time.perf_counter()
        hits = vi.search(q, "v3", top_k=3)
        latencies.append(1000 * (time.perf_counter() - t0))
        print(f"\nquery: {q}   ({latencies[-1]:.0f} ms)")
        print_hits(hits)
    print(f"\nmedian latency {sorted(latencies)[len(latencies) // 2]:.0f} ms over {len(latencies)} queries (includes query embedding)")

    print("\n== Same question, older version (v1) ==")
    q = "How is the input cleaned before it is passed to the router?"
    print(f"query: {q}")
    print_hits(vi.search(q, "v1", top_k=1))

    print("\n== Across all versions at once ==")
    show_across_versions(vi, "How is the input cleaned before it is passed to the router?", 3)
    print()
    show_across_versions(vi, "Where is the deeplink into the Settings app created?", 3)


def main() -> None:
    ap = argparse.ArgumentParser(prog="codeprism")
    ap.add_argument("--config", default=None)
    ap.add_argument("--model", default=None, help="model preset or id, or 'hashing' for no download")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo").set_defaults(func=cmd_demo)

    s = sub.add_parser("search")
    s.add_argument("--repo", required=True)
    s.add_argument("--top-k", type=int, default=5)
    s.add_argument("query")
    s.set_defaults(func=cmd_search)

    h = sub.add_parser("history")
    h.add_argument("--versions", nargs="+", required=True, help="name=path pairs in order, oldest first")
    h.add_argument("--top-k", type=int, default=5)
    h.add_argument("query")
    h.set_defaults(func=cmd_history)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
