"""Query and snippet preprocessing.

Everything here is plain string handling, so it runs anywhere and is fast.
Two jobs:

1. Turn a natural language problem or question into a few clean "views"
   (the full text, and the short statement without input/output boilerplate).
2. Turn a code snippet into a dense view (cleaned, length bounded) and a
   lexical view (identifiers split into words, plus comments and strings).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")

# Section markers used by APPS-style problem statements and similar text.
_SECTION = re.compile(
    r"^\s*-{2,}\s*(input|output|examples?|note|notes|constraints?|explanation)\s*-{2,}\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_PLAIN_SECTION = re.compile(r"^\s*(Input|Output|Examples?|Note)\s*:?\s*$", re.MULTILINE)

STOPWORDS = frozenset(
    """a an and are as at be been by can could do does for from had has have how
    i if in into is it its of on or our shall should so than that the their
    them then there these they this those to was we were what when where which
    while who will with would you your given following each every any all
    also only such must may might one two""".split()
)

# Words that mean nothing for code search when they show up in code.
CODE_NOISE = frozenset(
    """self this true false none null undefined return var let const def class
    function new else elif pass print import from as in is not and or if for
    while end""".split()
)


def split_identifier(name: str) -> list[str]:
    """snake_case and camelCase to lower case words. 'getUserID' -> get, user, id."""
    parts: list[str] = []
    for chunk in name.split("_"):
        if not chunk:
            continue
        parts.extend(w.lower() for w in _CAMEL.split(chunk) if w)
    return parts


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


# ----------------------------------------------------------------------------
# Query side
# ----------------------------------------------------------------------------


@dataclass
class QueryViews:
    full: str  # statement plus input/output description, examples removed
    statement: str  # only the narrative part


def _normalise_ws(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def query_views(text: str) -> QueryViews:
    """Split a problem statement into the parts that carry meaning.

    Sample inputs and outputs are mostly digits and hurt embeddings, so they
    are dropped. If the text has no section markers (a plain question like
    'where is the bluetooth deeplink used?') both views are just the cleaned
    text.
    """
    text = _normalise_ws(text or "")
    markers = list(_SECTION.finditer(text))
    if not markers:
        markers = list(_PLAIN_SECTION.finditer(text))
    if not markers:
        return QueryViews(full=text, statement=text)

    first = markers[0].start()
    statement = text[:first].strip() or text
    keep = [statement]
    for i, m in enumerate(markers):
        name = m.group(1).lower()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        if name in {"input", "output", "constraint", "constraints"}:
            body = text[m.end() : end].strip()
            if body:
                keep.append(body)
    return QueryViews(full=_normalise_ws("\n\n".join(keep)), statement=statement)


# Natural language words to the tokens they usually turn into in code.
NL_TO_CODE: dict[str, tuple[str, ...]] = {
    "maximum": ("max",),
    "minimum": ("min",),
    "largest": ("max",),
    "smallest": ("min",),
    "sum": ("sum",),
    "total": ("sum",),
    "sort": ("sort", "sorted"),
    "sorted": ("sort", "sorted"),
    "ascending": ("sort",),
    "descending": ("sort", "reverse"),
    "reverse": ("reverse",),
    "modulo": ("mod", "pow"),
    "remainder": ("mod",),
    "divisible": ("mod",),
    "integer": ("int",),
    "integers": ("int", "map", "split"),
    "string": ("str", "input"),
    "strings": ("str", "input"),
    "characters": ("str", "ord"),
    "array": ("list", "arr", "range"),
    "sequence": ("list", "range"),
    "permutation": ("perm", "permutations"),
    "prime": ("prime", "sieve", "sqrt"),
    "gcd": ("gcd",),
    "divisor": ("gcd", "mod"),
    "graph": ("graph", "adj", "visited", "dfs", "bfs"),
    "vertices": ("adj", "visited", "graph"),
    "edges": ("adj", "graph"),
    "tree": ("parent", "children", "root", "dfs"),
    "shortest": ("bfs", "dijkstra", "heap", "dist"),
    "palindrome": ("palindrome", "reverse"),
    "substring": ("substr", "find", "count"),
    "subsequence": ("dp",),
    "binary": ("bin", "bit", "shift"),
    "xor": ("xor", "bit"),
    "queries": ("query", "range", "input"),
    "cases": ("range", "input", "int"),
    "matrix": ("grid", "matrix", "range"),
    "grid": ("grid", "matrix", "range"),
    "coordinates": ("sqrt", "abs", "math"),
    "distance": ("abs", "sqrt", "dist"),
    "ways": ("dp", "mod", "count"),
    "optimal": ("dp", "min", "max"),
    "greedy": ("sort", "min", "max"),
}


def query_lexical_terms(text: str) -> list[str]:
    """Content words of a query plus the code words they usually map to."""
    out: list[str] = []
    for w in words(text):
        if w in STOPWORDS or len(w) < 2:
            continue
        out.append(w)
        out.extend(NL_TO_CODE.get(w, ()))
        stem = _stem(w)
        if stem != w:
            out.append(stem)
    return out


def _stem(w: str) -> str:
    for suffix in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return w


# ----------------------------------------------------------------------------
# Code side
# ----------------------------------------------------------------------------

_LINE_COMMENT = re.compile(r"(#|//)(.*)$")
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING = re.compile(r"(\"\"\".*?\"\"\"|'''.*?'''|\"[^\"\n]*\"|'[^'\n]*')", re.DOTALL)


def clean_code(code: str, max_chars: int = 6000) -> str:
    """Whitespace cleanup and a length cap that keeps the head and the tail.

    Competitive programming solutions read input at the top and print at the
    bottom, so cutting only the end throws away the answer logic.
    """
    code = (code or "").replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    lines = [ln.rstrip() for ln in code.split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if len(text) <= max_chars:
        return text
    head = int(max_chars * 0.65)
    tail = max_chars - head
    return text[:head] + "\n...\n" + text[-tail:]


def code_comments_and_strings(code: str) -> str:
    """Natural language that lives inside the code: comments, docstrings, strings."""
    found: list[str] = []
    for m in _BLOCK_COMMENT.finditer(code):
        found.append(m.group(0))
    for m in _STRING.finditer(code):
        found.append(m.group(0))
    for line in code.split("\n"):
        m = _LINE_COMMENT.search(line)
        if m:
            found.append(m.group(2))
    return "\n".join(found)


def code_lexical_terms(code: str) -> list[str]:
    """Bag of words for keyword search over a snippet.

    Identifiers are split into words, and the original lower cased identifier
    is kept too, so both 'get_user_id' and 'user' can match.
    """
    terms: list[str] = []
    for ident in _IDENT.findall(code):
        low = ident.lower()
        pieces = split_identifier(ident)
        if low not in CODE_NOISE and len(low) > 1:
            terms.append(low)
        if len(pieces) > 1 or (pieces and pieces[0] != low):
            terms.extend(p for p in pieces if len(p) > 1 and p not in CODE_NOISE)
    for w in words(code_comments_and_strings(code)):
        if w not in STOPWORDS and len(w) > 1:
            terms.append(w)
    return terms
