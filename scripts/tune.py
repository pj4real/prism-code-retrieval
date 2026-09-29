"""Quick tuning on a sample of the CoIR apps test split.

Model comparison and weight search on the full task takes too long on a
laptop CPU, so this samples queries and keeps all their relevant documents
plus random distractors. Absolute scores are higher than on the full corpus;
compare variants against each other, not against the final number.

Because embeddings are cached in sqlite, each text is embedded once per
model. The weight grid after that is nearly free.

    python scripts/tune.py --models gte-modernbert-base,bge-small --queries 300 --docs 3000
    python scripts/tune.py --models gte-modernbert-base --write-config configs/tuned.json

Honest note: this tunes on samples of the test split, because that is the
only labelled split we know the organizers score on. The weights are few
(four numbers) and the report says so.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mteb  # noqa: E402

from codeprism import HybridRetriever, PipelineConfig  # noqa: E402


def load_split(task_name: str = "AppsRetrieval"):
    task = mteb.get_task(task_name)
    task.load_data()
    split = task.dataset["default"]["test"]
    corpus, queries, qrels = split["corpus"], split["queries"], split["relevant_docs"]
    if not isinstance(qrels, dict):  # HF dataset with query-id / corpus-id / score
        d: dict[str, dict[str, float]] = {}
        for row in qrels:
            d.setdefault(str(row["query-id"]), {})[str(row["corpus-id"])] = float(row["score"])
        qrels = d
    return corpus, queries, {str(q): {str(k): float(v) for k, v in r.items()} for q, r in qrels.items()}


def ndcg_mrr(results: dict[str, list[tuple[str, float]]], qrels, k: int = 10) -> tuple[float, float]:
    nd, rr, n = 0.0, 0.0, 0
    for qid, hits in results.items():
        rel = qrels.get(qid)
        if not rel:
            continue
        n += 1
        top = [d for d, _ in hits[:k]]
        dcg = sum(rel.get(d, 0.0) / math.log2(i + 2) for i, d in enumerate(top))
        ideal = sorted(rel.values(), reverse=True)[:k]
        idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
        nd += dcg / idcg if idcg else 0.0
        for i, d in enumerate(top):
            if rel.get(d, 0.0) > 0:
                rr += 1.0 / (i + 1)
                break
    return nd / max(n, 1), rr / max(n, 1)


def sample(corpus, queries, qrels, n_queries: int, n_docs: int, seed: int):
    rng = random.Random(seed)
    qids = [str(q) for q in queries["id"]]
    qtext = dict(zip(qids, queries["text"]))
    usable = [q for q in qids if qrels.get(q)]
    rng.shuffle(usable)
    chosen = usable[:n_queries]
    needed = {d for q in chosen for d in qrels[q]}
    ids = [str(i) for i in corpus["id"]]
    texts = list(corpus["text"])
    if "title" in corpus.column_names:
        texts = [f"{t} {x}".strip() if t else x for t, x in zip(corpus["title"], texts)]
    doc_text = dict(zip(ids, texts))
    extra = [d for d in ids if d not in needed]
    rng.shuffle(extra)
    keep = list(needed) + extra[: max(n_docs - len(needed), 0)]
    return (
        [q for q in chosen],
        [qtext[q] for q in chosen],
        keep,
        [doc_text[d] for d in keep],
        {q: qrels[q] for q in chosen},
    )


def run_variant(retriever: HybridRetriever, index, qids, qtexts, qrels):
    t0 = time.perf_counter()
    ranked = retriever.search(index, qtexts, top_k=10)
    dt = time.perf_counter() - t0
    res = {q: h for q, h in zip(qids, ranked)}
    return (*ndcg_mrr(res, qrels), dt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="gte-modernbert-base")
    ap.add_argument("--queries", type=int, default=300)
    ap.add_argument("--docs", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--cache", default=".cache/embeddings.sqlite")
    ap.add_argument("--write-config", default=None)
    ap.add_argument("--tags", action="store_true", help="also try writing topic tags into the text the model sees (doubles embedding time)")
    args = ap.parse_args()

    corpus, queries, qrels = load_split()
    qids, qtexts, dids, dtexts, sub_qrels = sample(corpus, queries, qrels, args.queries, args.docs, args.seed)
    print(f"sample: {len(qids)} queries, {len(dids)} documents", flush=True)

    rows = []
    best = None
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        for tags in ((False, True) if args.tags else (False,)):
            base = PipelineConfig(model=model, cache_path=args.cache, augment_tags=tags)
            retr = HybridRetriever(base)
            t0 = time.perf_counter()
            index = retr.build_index(dids, dtexts)
            print(f"[{model} tags={tags}] indexed in {time.perf_counter() - t0:.0f}s "
                  f"(new={index.embedded_new}, cached={index.embedded_cached})", flush=True)

            grid = [
                ("dense only, full view", dict(w_full=1.0, w_stmt=0.0, bm25_weight=0.0, topic_weight=0.0)),
                ("dense, both views", dict(w_full=0.6, w_stmt=0.4, bm25_weight=0.0, topic_weight=0.0)),
            ]
            for bm, tp in itertools.product((0.1, 0.25, 0.5), (0.0, 0.15, 0.3)):
                grid.append((f"hybrid bm25={bm} topic={tp}", dict(bm25_weight=bm, topic_weight=tp)))
            grid.append(("hybrid rrf", dict(fusion="rrf", bm25_weight=0.5, topic_weight=0.15)))

            for name, overrides in grid:
                retr.cfg = replace(base, **overrides)
                ndcg, mrr, secs = run_variant(retr, index, qids, qtexts, sub_qrels)
                rows.append((model, tags, name, ndcg, mrr))
                print(f"  {name:32s} ndcg@10={ndcg:.4f} mrr@10={mrr:.4f} ({secs:.1f}s)", flush=True)
                if best is None or ndcg > best[0]:
                    best = (ndcg, retr.cfg)

    print("\nbest by NDCG@10 on the sample:")
    print(best[1].to_json())
    if args.write_config:
        best[1].cache_path = ".cache/embeddings.sqlite"
        Path(args.write_config).write_text(best[1].to_json())
        print(f"wrote {args.write_config}")
    Path("tuning_report.json").write_text(
        json.dumps([dict(model=m, tags=t, variant=n, ndcg_at_10=a, mrr_at_10=b) for m, t, n, a, b in rows], indent=2)
    )


if __name__ == "__main__":
    main()
