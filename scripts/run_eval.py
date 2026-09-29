"""Run the CoIR apps test split through MTEB and write the results file.

    python scripts/run_eval.py
    python scripts/run_eval.py --config configs/tuned.json

Writes appsretrieval_results.json (the file the organizers ask for) and
run_summary.json (config, scores, timings) next to it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mteb  # noqa: E402

from codeprism import PipelineConfig  # noqa: E402
from codeprism.mteb_model import PrePostPipelineEncoder  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="JSON config. Defaults to configs/tuned.json if present, else configs/default.json")
    ap.add_argument("--model", default=None, help="override the model preset or id in the config")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--out", default="appsretrieval_results.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    config_path = args.config
    if config_path is None:
        tuned = root / "configs" / "tuned.json"
        config_path = str(tuned if tuned.exists() else root / "configs" / "default.json")
    cfg = PipelineConfig.load(config_path)
    if args.model:
        cfg.model = args.model
    print(f"config: {config_path}\n{cfg.to_json()}", flush=True)

    model = PrePostPipelineEncoder(cfg)
    task = mteb.get_task("AppsRetrieval")

    t0 = time.perf_counter()
    result = mteb.evaluate(
        model,
        [task],
        encode_kwargs={"batch_size": args.batch_size},
        cache=None,  # always run, never reuse an old MTEB result
    )
    wall = time.perf_counter() - t0

    task_result = list(result.task_results)[0]
    out = Path(args.out)
    # to_disk is MTEB's own writer. It stores the date as a timestamp, which
    # json.dump(task_result.to_dict()) cannot do on recent MTEB versions.
    task_result.to_disk(out)

    score = json.loads(out.read_text())["scores"]["test"][0]
    summary = {
        "ndcg_at_10": score.get("ndcg_at_10"),
        "mrr_at_10": score.get("mrr_at_10"),
        "recall_at_10": score.get("recall_at_10"),
        "wall_clock_seconds": round(wall, 1),
        "index_seconds": round(model.stats.get("index_seconds", 0), 1),
        "search_seconds_after_query_encoding": round(model.stats.get("search_seconds", 0), 1),
        "docs": model.stats.get("docs"),
        "queries": model.stats.get("queries"),
        "cpu_count": os.cpu_count(),
        "config": json.loads(cfg.to_json()),
    }
    Path("run_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n=== result ===")
    print(f"NDCG@10 : {summary['ndcg_at_10']}")
    print(f"MRR@10  : {summary['mrr_at_10']}")
    print(f"wall    : {summary['wall_clock_seconds']} s")
    print(f"wrote   : {out.resolve()} and run_summary.json")


if __name__ == "__main__":
    main()
