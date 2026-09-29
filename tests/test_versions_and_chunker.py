from pathlib import Path

from codeprism import HybridRetriever, PipelineConfig
from codeprism.chunker import chunk_repo, chunk_source
from codeprism.cli import repo_to_snippets
from codeprism.versioned import VersionedIndex, content_hash

SAMPLE = Path(__file__).resolve().parents[1] / "demo" / "sample_repo"


def test_js_chunker_handles_default_args_and_arrows():
    src = (
        "const a = 1;\n"
        "function f(x = {}) {\n  return { x };\n}\n\n"
        "const g = (p) => {\n  if (p) {\n    return 1;\n  }\n  return 2;\n};\n"
        "const h = 'a { b';\n"
    )
    names = [(s.name, s.start, s.end) for s in chunk_source("x.js", src)]
    assert ("f", 2, 4) in names and ("g", 6, 11) in names


def test_python_chunker_uses_ast():
    src = "import os\n\n@deco\ndef a():\n    return 1\n\nclass B:\n    def m(self):\n        pass\n"
    got = {s.name: (s.start, s.end) for s in chunk_source("m.py", src)}
    assert got["a"] == (3, 5) and got["B"][0] == 7 and got["m"] == (8, 9)


def test_fallback_windows_for_unknown_files():
    text = "\n".join(f"line {i}" for i in range(100))
    chunks = chunk_source("notes.txt", text)
    assert len(chunks) >= 3 and chunks[0].start == 1


def test_sample_repo_chunks_every_version():
    counts = [len(chunk_repo(SAMPLE / v)) for v in ("v1", "v2", "v3")]
    assert counts == sorted(counts) and counts[0] >= 30


def test_incremental_versions_embed_only_changes(tmp_path):
    r = HybridRetriever(PipelineConfig(model="hashing", cache_path=str(tmp_path / "c.sqlite")))
    vi = VersionedIndex(r)
    stats = []
    for v in ("v1", "v2", "v3"):
        texts, where = repo_to_snippets(SAMPLE / v)
        stats.append(vi.add_version(v, texts, where))
    assert stats[0].new_or_changed == stats[0].snippets
    assert 0 < stats[1].new_or_changed < stats[1].snippets / 2
    assert stats[1].unchanged > stats[1].new_or_changed


def test_search_a_specific_version_sees_that_versions_text(tmp_path):
    r = HybridRetriever(PipelineConfig(model="hashing", cache_path=None))
    vi = VersionedIndex(r)
    for v in ("v1", "v3"):
        texts, where = repo_to_snippets(SAMPLE / v)
        vi.add_version(v, texts, where)
    old = vi.search("mute all streams", "v1", top_k=3)
    assert any("muteAll" in h.text for h in old)
    new = vi.search("night mode display", "v3", top_k=3)
    assert any("night" in h.text.lower() for h in new)


def test_all_versions_groups_by_snippet_and_lists_changes():
    r = HybridRetriever(PipelineConfig(model="hashing", cache_path=None))
    vi = VersionedIndex(r)
    for v in ("v1", "v2", "v3"):
        texts, where = repo_to_snippets(SAMPLE / v)
        vi.add_version(v, texts, where)
    hits = vi.search("open bluetooth settings deeplink", "all", top_k=5)
    ids = [h.id for h in hits]
    assert len(ids) == len(set(ids)), "one hit per snippet identity"
    blue = [h for h in hits if h.id.endswith("openBluetoothSettings")]
    assert blue, "the bluetooth function should be retrieved"
    versions_seen = set(blue[0].same_in_versions) | {v for v, _ in blue[0].changed_in_versions}
    assert len(versions_seen) >= 2


def test_content_hash_ignores_trailing_whitespace():
    assert content_hash("a = 1  \n") == content_hash("a = 1")
