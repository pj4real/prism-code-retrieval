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
        f"| NDCG@10 | {summary['ndcg_at_10']:.4f} |",
        f"| MRR@10 | {summary['mrr_at_10']:.4f} |",
        f"| Documents / queries | {summary['docs']} / {summary['queries']} |",
        f"| Total wall clock | {summary['wall_clock_seconds']:.0f} s on {summary['cpu_count']} CPU cores |",
        "",
        f"Model: `{cfg['model']}`. BM25 weight {cfg['bm25_weight']}, topic weight {cfg['topic_weight']}, "
        f"fusion {cfg['fusion']}, topic tags in text: {cfg['augment_tags']}.",
    ]
    tuning = ROOT / "tuning_report.json"
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
