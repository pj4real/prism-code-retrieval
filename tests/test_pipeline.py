import numpy as np

from codeprism import HybridRetriever, PipelineConfig
from codeprism.categories import code_topics, query_topics, TOPIC_NAMES
from codeprism.lexical import BM25Index
from codeprism.preprocess import clean_code, code_lexical_terms, query_views, split_identifier
from tests.toy_data import QUERIES, SNIPPETS


def test_split_identifier():
    assert split_identifier("getUserID") == ["get", "user", "id"]
    assert split_identifier("shortest_path_v2") == ["shortest", "path", "v2"]


def test_query_views_drops_examples():
    text = "Count the primes.\n\n-----Input-----\n\nOne integer n.\n\n-----Output-----\n\nPrint the count.\n\n-----Examples-----\nInput\n10\nOutput\n4\n"
    v = query_views(text)
    assert v.statement == "Count the primes."
    assert "One integer n." in v.full and "Print the count." in v.full
    assert "Examples" not in v.full and "10" not in v.full


def test_query_views_plain_question():
    v = query_views("Where is the bluetooth deeplink used?")
    assert v.full == v.statement


def test_clean_code_keeps_head_and_tail():
    code = "\n".join(f"line{i}" for i in range(2000))
    out = clean_code(code, max_chars=500)
    assert out.startswith("line0") and out.endswith("line1999") and len(out) <= 520


def test_bm25_prefers_matching_doc():
    idx = BM25Index().fit([["heap", "graph", "dist"], ["palindrome", "reverse"], ["sort", "max"]])
    s = idx.scores([["graph", "heap"]])
    assert s.argmax() == 0 and s[0, 1] == 0


def test_topics_line_up():
    q = query_topics("shortest path in a graph with weighted edges")
    d = code_topics(SNIPPETS["dijkstra"])
    assert TOPIC_NAMES[int(np.argmax(q))] == "graph"
    assert d[TOPIC_NAMES.index("graph")] > 0


def test_end_to_end_ranking_with_hashing_backend():
    r = HybridRetriever(PipelineConfig(model="hashing", cache_path=None))
    ids = list(SNIPPETS)
    idx = r.build_index(ids, [SNIPPETS[i] for i in ids])
    qids = list(QUERIES)
    hits = r.search(idx, [QUERIES[q][0] for q in qids], top_k=3)
    top1 = sum(h[0][0] == QUERIES[q][1] for q, h in zip(qids, hits))
    assert top1 >= 5, f"only {top1}/{len(qids)} top-1 with the offline backend"


def test_rrf_and_zscore_both_run():
    for fusion in ("zscore", "rrf"):
        r = HybridRetriever(PipelineConfig(model="hashing", cache_path=None, fusion=fusion))
        idx = r.build_index(list(SNIPPETS), list(SNIPPETS.values()))
        out = r.search(idx, ["sum of the array"], top_k=5)
        assert len(out[0]) == 5
