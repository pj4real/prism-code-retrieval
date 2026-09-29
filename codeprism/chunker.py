"""Split source files into function sized snippets with file and line numbers.

Python uses the ast module. JavaScript uses a small brace matcher that copes
with strings, comments and template literals. Anything else, or a file where
no function is found, falls back to overlapping line windows.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

JS_EXT = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
PY_EXT = {".py"}

_JS_HEADERS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function\b[^(]*)?\(?[^)=]*\)?\s*=>?\s*\{?"),
    re.compile(r"^\s*(?:export\s+)?class\s+([A-Za-z_$][\w$]*)"),
    re.compile(r"^\s*(?:async\s+)?(?:static\s+)?([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{\s*$"),
]
_METHOD_BLOCKLIST = {"if", "for", "while", "switch", "catch", "function", "return"}


@dataclass
class Snippet:
    id: str  # "path:start-end"
    path: str
    start: int  # 1 based, inclusive
    end: int
    name: str
    text: str


def _match_braces(lines: list[str], start_idx: int) -> int | None:
    """Return the index of the line where the block opened at start_idx closes."""
    depth = 0
    paren = 0  # braces inside ( ... ) are default values or destructuring, not the body
    opened = False
    in_str: str | None = None
    in_block_comment = False
    for i in range(start_idx, len(lines)):
        line = lines[i]
        j = 0
        while j < len(line):
            ch = line[j]
            nxt = line[j + 1] if j + 1 < len(line) else ""
            if in_block_comment:
                if ch == "*" and nxt == "/":
                    in_block_comment = False
                    j += 1
            elif in_str:
                if ch == "\\":
                    j += 1
                elif ch == in_str:
                    in_str = None
            else:
                if ch == "/" and nxt == "*":
                    in_block_comment = True
                    j += 1
                elif ch == "/" and nxt == "/":
                    break
                elif ch in "\"'`":
                    in_str = ch
                elif ch == "(":
                    paren += 1
                elif ch == ")":
                    paren = max(paren - 1, 0)
                elif ch == "{" and paren == 0:
                    depth += 1
                    opened = True
                elif ch == "}" and paren == 0:
                    depth -= 1
                    if opened and depth == 0:
                        return i
            j += 1
        if in_str in ("\"", "'"):
            in_str = None  # unterminated plain string, do not leak to next line
        if not opened and i - start_idx > 3:
            return None  # header without a body nearby, e.g. an arrow function expression
    return None


def _chunk_js(path: str, source: str) -> list[Snippet]:
    lines = source.split("\n")
    out: list[Snippet] = []
    i = 0
    while i < len(lines):
        name = None
        for pat in _JS_HEADERS:
            m = pat.match(lines[i])
            if m and m.group(1) not in _METHOD_BLOCKLIST:
                name = m.group(1)
                break
        if name:
            end = _match_braces(lines, i)
            if end is not None and end >= i:
                text = "\n".join(lines[i : end + 1])
                out.append(Snippet(f"{path}:{i + 1}-{end + 1}", path, i + 1, end + 1, name, text))
                # a class is kept whole and its methods are still visited
                i = i + 1 if lines[i].lstrip().startswith(("class ", "export class ")) else end + 1
                continue
        i += 1
    return out


def _chunk_py(path: str, source: str) -> list[Snippet]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.split("\n")
    out: list[Snippet] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            if getattr(node, "decorator_list", None):
                start = min(d.lineno for d in node.decorator_list)
            end = node.end_lineno or node.lineno
            text = "\n".join(lines[start - 1 : end])
            out.append(Snippet(f"{path}:{start}-{end}", path, start, end, node.name, text))
    return sorted(out, key=lambda s: (s.start, -s.end))


def _windows(path: str, source: str, size: int = 40, overlap: int = 10) -> list[Snippet]:
    lines = source.split("\n")
    out: list[Snippet] = []
    step = max(size - overlap, 1)
    for start in range(0, max(len(lines), 1), step):
        chunk = lines[start : start + size]
        if not "".join(chunk).strip():
            continue
        end = start + len(chunk)
        out.append(Snippet(f"{path}:{start + 1}-{end}", path, start + 1, end, f"lines {start + 1}-{end}", "\n".join(chunk)))
        if start + size >= len(lines):
            break
    return out


def chunk_source(path: str, source: str) -> list[Snippet]:
    ext = Path(path).suffix.lower()
    snippets: list[Snippet] = []
    if ext in PY_EXT:
        snippets = _chunk_py(path, source)
    elif ext in JS_EXT:
        snippets = _chunk_js(path, source)
    return snippets or _windows(path, source)


def chunk_repo(root: str | Path, exts: set[str] | None = None) -> list[Snippet]:
    """Chunk every source file under root. Paths in ids are relative to root."""
    root = Path(root)
    exts = exts or (JS_EXT | PY_EXT)
    snippets: list[Snippet] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts and "node_modules" not in p.parts and ".git" not in p.parts:
            try:
                source = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            snippets.extend(chunk_source(str(p.relative_to(root)), source))
    return snippets
