"""Topic tags for queries and code snippets.

A small keyword lexicon per topic. The same topics are detected on both sides
(problem text and code) so that a query about a graph problem gets a small
boost for snippets that look like graph code, and so the tags can be written
into the text the embedding model sees.

This is deliberately simple and transparent. It is not a trained classifier.
"""

from __future__ import annotations

import re

import numpy as np

# topic -> (regex over natural language, regex over code)
_TOPICS: dict[str, tuple[str, str]] = {
    "graph": (
        r"\b(graph|vertex|vertices|edge|edges|node|nodes|path|connected|shortest|cycle|bfs|dfs|adjacen\w*|route|city|cities|road)\b",
        r"\b(adj|graph|visited|dfs|bfs|dijkstra|deque|heappush|heappop|edges|neighbors?|indeg|outdeg)\b",
    ),
    "tree": (
        r"\b(tree|root|leaf|leaves|parent|child|children|subtree|ancestor|lca)\b",
        r"\b(parent|children|subtree|root|depth|lca|tin|tout)\b",
    ),
    "dp": (
        r"\b(number of ways|minimum cost|maximum (sum|profit|value)|subsequence|knapsack|longest|optimal|modulo\s*10\^?9|998244353|dynamic programming)\b",
        r"(\bdp\b|\bdp\[|\bmemo\b|lru_cache|\bcache\b|\bf\[\w+\]\[\w+\])",
    ),
    "string": (
        r"\b(string|strings|substring|palindrome|characters?|letters?|lowercase|uppercase|word|words|alphabet)\b",
        r"(\.split\(|\.count\(|\[::-1\]|\bord\(|\bchr\(|\.join\(|\.lower\(|\.upper\(|\.find\(|\bstr\()",
    ),
    "math": (
        r"\b(prime|divisible|divisor|gcd|lcm|remainder|modulo|factor\w*|digit|digits|integer|arithmetic|sum of|parity|even|odd)\b",
        r"(\bgcd\b|\bpow\(|\bsqrt\b|\bmod\b|%\s*\w+|\bprime\b|\bsieve\b|\bfactor\w*|//)",
    ),
    "sorting_greedy": (
        r"\b(sort|sorted|order|greedy|arrange|rearrange|minimum number of|at most|at least|pair|pairs)\b",
        r"(\.sort\(|\bsorted\(|\bmin\(|\bmax\(|\.reverse\(|\bzip\()",
    ),
    "binary_search": (
        r"\b(binary search|monotonic|largest possible|smallest possible|k-?th|at least k)\b",
        r"(\bbisect\w*|\blo\b.*\bhi\b|\bmid\b|\blow\b.*\bhigh\b)",
    ),
    "bits": (
        r"\b(xor|bitwise|binary representation|bit|bits|and of|or of)\b",
        r"(\^|<<|>>|\bbin\(|&\s*\w|\bbit\w*)",
    ),
    "geometry": (
        r"\b(point|points|coordinate|coordinates|distance|circle|polygon|rectangle|angle|area|segment|line)\b",
        r"(\bhypot\b|\batan2?\b|\bsqrt\b|\bmath\.|\bcross\b|\bdot\b)",
    ),
    "grid": (
        r"\b(grid|matrix|cell|cells|rows?|columns?|chessboard|board|table)\b",
        r"(\bgrid\b|\bmatrix\b|\[\[|for\s+\w+\s+in\s+range\(\w+\):\s*\n\s*for\s+\w+\s+in\s+range\(\w+\))",
    ),
    "counting": (
        r"\b(permutation|permutations|combination|combinations|binomial|arrangements?|number of ways|count the number)\b",
        r"(\bfact\b|\bfactorial\b|\bcomb\b|\bchoose\b|\bcounter\b|\bdefaultdict\b|\bnCr\b)",
    ),
    "data_structure": (
        r"\b(queue|stack|heap|priority|set|dictionary|segment tree|fenwick|prefix sum|sliding window|two pointers)\b",
        r"(\bheapq\b|\bdeque\b|\bCounter\b|\bdefaultdict\b|\bbisect\b|\bSegmentTree\b|\bBIT\b|\bprefix\b|\bstack\b)",
    ),
    "multi_test": (
        r"\b(test cases?|queries)\b",
        r"(for\s+_\s+in\s+range\(int\(input\(\)\)\)|for\s+\w+\s+in\s+range\(t\)|while\s+t\b|\bt\s*=\s*int\()",
    ),
}

TOPIC_NAMES = list(_TOPICS)
_NL = {k: re.compile(v[0], re.IGNORECASE) for k, v in _TOPICS.items()}
_CODE = {k: re.compile(v[1], re.IGNORECASE | re.MULTILINE) for k, v in _TOPICS.items()}


def _vector(text: str, patterns: dict[str, re.Pattern]) -> np.ndarray:
    counts = np.array([len(patterns[k].findall(text)) for k in TOPIC_NAMES], dtype=np.float32)
    # squash so one very repetitive word does not dominate
    return np.log1p(counts)


def query_topics(text: str) -> np.ndarray:
    return _vector(text, _NL)


def code_topics(code: str) -> np.ndarray:
    return _vector(code, _CODE)


def top_tags(vec: np.ndarray, n: int = 3, min_score: float = 0.6) -> list[str]:
    order = np.argsort(-vec)
    return [TOPIC_NAMES[i] for i in order[:n] if vec[i] >= min_score]


def topic_similarity(q: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Cosine similarity between query topic vectors and snippet topic vectors.

    q: (nq, T), d: (nd, T). Returns (nq, nd). Rows with no detected topic
    score 0 against everything, so they neither help nor hurt.
    """
    qn = np.linalg.norm(q, axis=1, keepdims=True)
    dn = np.linalg.norm(d, axis=1, keepdims=True)
    qn[qn == 0] = 1.0
    dn[dn == 0] = 1.0
    return (q / qn) @ (d / dn).T
