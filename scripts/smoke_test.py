"""Quick check that everything works on this machine before the long run.

    python scripts/smoke_test.py
    python scripts/smoke_test.py --model bge-small

It loads the model, times it on realistic text, downloads the CoIR apps data,
prints its size and a sample, and estimates how long the full evaluation will
take. Everything is also written to smoke_test_report.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codeprism import HybridRetriever, PipelineConfig  # noqa: E402
from codeprism.preprocess import clean_code, query_views  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gte-modernbert-base")
    args = ap.parse_args()
    report: dict = {"python": sys.version.split()[0], "platform": platform.platform()}

    import mteb
    import sentence_transformers
    import torch
    import transformers

    report["versions"] = {
        "mteb": mteb.__version__,
        "sentence_transformers": sentence_transformers.__version__,
        "transformers": transformers.__version__,
        "torch": torch.__version__,
    }
    print(report["versions"], flush=True)

    # 1. data
    t0 = time.perf_counter()
    task = mteb.get_task("AppsRetrieval")
    task.load_data()
    split = task.dataset["default"]["test"]
    corpus, queries, qrels = split["corpus"], split["queries"], split["relevant_docs"]
    report["data_load_seconds"] = round(time.perf_counter() - t0, 1)
    report["corpus_columns"] = corpus.column_names
    report["query_columns"] = queries.column_names
    report["n_docs"], report["n_queries"] = len(corpus), len(queries)
    lens_d = [len(t) for t in corpus["text"]]
    lens_q = [len(t) for t in queries["text"]]
    report["doc_chars_median_max"] = [statistics.median(lens_d), max(lens_d)]
    report["query_chars_median_max"] = [statistics.median(lens_q), max(lens_q)]
    first_q = queries["text"][0]
    qid = str(queries["id"][0])
    rel_id = next(iter(qrels[qid]))
    rel_text = corpus["text"][[str(i) for i in corpus["id"]].index(rel_id)]
    report["sample_query_start"] = first_q[:500]
    report["sample_query_views"] = {
        "statement_chars": len(query_views(first_q).statement),
        "full_chars": len(query_views(first_q).full),
    }
    report["sample_relevant_doc_start"] = rel_text[:500]
    print(f"data: {report['n_docs']} docs, {report['n_queries']} queries, load {report['data_load_seconds']}s", flush=True)
    print("query start:", first_q[:200].replace("\n", " "), flush=True)
    print("relevant doc start:", rel_text[:200].replace("\n", " "), flush=True)

    # 2. model speed on real text
    cfg = PipelineConfig(model=args.model, cache_path=None)
    t0 = time.perf_counter()
    retr = HybridRetriever(cfg)
    report["model_load_seconds"] = round(time.perf_counter() - t0, 1)

    sample_docs = [clean_code(t, cfg.doc_max_chars) for t in corpus["text"][:48]]
    sample_qs = [query_views(t).full for t in queries["text"][:48]]
    t0 = time.perf_counter()
    retr.embedder.embed(sample_docs, "doc", 32)
    per_doc = (time.perf_counter() - t0) / len(sample_docs)
    t0 = time.perf_counter()
    retr.embedder.embed(sample_qs, "query_full", 32)
    per_q = (time.perf_counter() - t0) / len(sample_qs)
    report["seconds_per_doc"] = round(per_doc, 4)
    report["seconds_per_query_view"] = round(per_q, 4)
    # queries are embedded in about 1.7 views on average (full text, plus the statement when it differs)
    est = report["n_docs"] * per_doc + report["n_queries"] * per_q * 1.7
    report["estimated_full_run_minutes"] = round(est / 60, 1)
    print(f"model {args.model}: load {report['model_load_seconds']}s, {per_doc:.3f}s per doc, {per_q:.3f}s per query view", flush=True)
    print(f"estimated full run: about {report['estimated_full_run_minutes']} minutes", flush=True)

    # 3. tiny end to end check on real rows
    ids = [str(i) for i in corpus["id"][:200]]
    idx = retr.build_index(ids, list(corpus["text"][:200]))
    hits = retr.search(idx, [first_q], top_k=3)[0]
    report["tiny_search_top3"] = hits
    print("tiny search on first 200 docs, top 3:", hits, flush=True)

    Path("smoke_test_report.json").write_text(json.dumps(report, indent=2, default=str))
    print("wrote smoke_test_report.json")


if __name__ == "__main__":
    main()
