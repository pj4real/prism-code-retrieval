"""Copy the numbers from run_summary.json into the Results block of README.md.

    python scripts/update_results.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"


def main() -> None:
    summary = json.loads((ROOT / "run_summary.json").read_text())
    cfg = summary["config"]
    lines = [
        "Measured on the CoIR apps test split with `scripts/run_eval.py` (full corpus, all queries).",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| NDCG@10 | {summary['ndcg_at_10']} |",
        f"| MRR@10 | {summary['mrr_at_10']} |",
        f"| Documents / queries | {summary['docs']} / {summary['queries']} |",
        f"| Recall@10 | {summary['recall_at_10']} |",
        f"| Total wall clock | {summary['wall_clock_seconds']} s on {summary['cpu_count']} CPU cores |",
        "",
        f"Model: `{cfg['model']}`. BM25 weight {cfg['bm25_weight']}, topic weight {cfg['topic_weight']}, "
        f"fusion {cfg['fusion']}, topic tags in text: {cfg['augment_tags']}.",
    ]
    runs = ROOT / "runs"
    if runs.exists():
        lines += ["", "Every full run we made, with the same code and weights (`runs/*/run_summary.json`):", "",
                  "| Model | NDCG@10 | MRR@10 | Wall clock | CPU cores |", "| --- | --- | --- | --- | --- |"]
        for p in sorted(runs.glob("*/run_summary.json")):
            r = json.loads(p.read_text())
            lines.append(f"| {r['config']['model']} | {r['ndcg_at_10']} | {r['mrr_at_10']} | {r['wall_clock_seconds']} s | {r['cpu_count']} |")
        lines += ["", "We submitted the model with the higher score. Both were scored on the same test split, so picking between "
                  "them is a choice made on test data, and the submitted number should be read with that in mind. "
                  "bge-small ran on a MacBook (10 cores), bge-base on a teammate's Windows laptop (Intel Core i7-14650HX, 24 logical cores), "
                  "so the wall clock times are not comparable. Both runs were CPU only."]
    tuning = ROOT / "tuning_report.json"
    if not tuning.exists():
        lines += ["", "These weights were set by hand. They were not tuned."]
    if tuning.exists():
        lines += ["", "Ablation on the tuning sample (see `tuning_report.json`), NDCG@10:", ""]
        rows = json.loads(tuning.read_text())
        wanted = {"dense only, full view", "dense, both views"}
        best_hybrid = max((r for r in rows if r["variant"].startswith("hybrid")), key=lambda r: r["ndcg_at_10"], default=None)
        lines += ["| Variant | NDCG@10 | MRR@10 |", "| --- | --- | --- |"]
        for r in rows:
            if r["variant"] in wanted and not r["tags"]:
                lines.append(f"| {r['variant']} ({r['model']}) | {r['ndcg_at_10']:.4f} | {r['mrr_at_10']:.4f} |")
        if best_hybrid:
            lines.append(f"| {best_hybrid['variant']} ({best_hybrid['model']}) | {best_hybrid['ndcg_at_10']:.4f} | {best_hybrid['mrr_at_10']:.4f} |")

    readme = ROOT / "README.md"
    text = readme.read_text()
    head, _, rest = text.partition(START)
    _, _, tail = rest.partition(END)
    readme.write_text(head + START + "\n" + "\n".join(lines) + "\n" + END + tail)
    print("README results block updated")


if __name__ == "__main__":
    main()
