# AGENTS.md: handoff for AI coding agents

Read this before changing anything. It is the current state of the project as of 1 Oct 2026.
Human readers can use it too, but it is written for an agent picking up the work cold.

## 1. What this is

CodePrism: CPU only hybrid text to code retrieval, built for Samsung PRISM Gen AI Hackathon 3.0,
Theme 1 (Agentic Code Intelligence), team Procrastinators, VIT Vellore. Given a plain English
question and a corpus of code, return the snippets that answer it, best first. Retrieval only, no
answer generation.

Scored with MTEB task AppsRetrieval (CoIR apps test split: 8765 code documents, 3765 queries).
Goals from the problem statement: P0 accuracy (NDCG@10, MRR@10), P1 fast index rebuild per code
version, bonus search across versions.

## 2. Current state

- Submitted state: commit 4173849, tag `PRISM_GENAI_HACKATHON_Y2026`, GitHub release of the same name
  with `appsretrieval_results.json` attached. Submitted score NDCG@10 0.06959, MRR@10 0.05843,
  model bge-base.
- The organizers extended the deadline after the first submission. The new date is not recorded here
  yet; ask Prakhar. Until a resubmission is decided, treat the tag and release as frozen.
- 19 tests pass offline: `python -m pytest -q tests`.
- Fusion weights have never been tuned. They are hand set guesses (see section 6).

## 3. Hard rules

1. Never invent, estimate, round or "improve" a score. Every number you report or write must be
   copied from a `run_summary.json` produced by a real run. No run, no number: write "pending".
2. Do not move or delete the tag or release, and do not force push, unless Prakhar explicitly says so
   in the current conversation.
3. Work on a branch and open a PR to `main`. Prakhar or a teammate merges.
4. No `Co-Authored-By` lines or any Claude or AI attribution in commit messages or PR bodies. AI use is
   disclosed in `AI_DISCLOSURE.md` instead.
5. Keep the AI disclosure honest and current. If you (or any AI tool) add a feature, write docs, make
   media or run benchmarks, update `AI_DISCLOSURE.md` and the docx in `submission/`. The docx is signed
   by Sudiksha Kathuria; tell the team when it changes.
6. Writing style for anything the team reads: plain and direct, no em dashes, no italics.
7. Never type passwords or tokens. If git, gh or Hugging Face asks for a login, stop and ask the human.
8. Selecting a model or weights by their test split score is a choice made on test data. If you do it,
   the README must say so (it already does for the bge-small vs bge-base choice).

## 4. How it works

A query goes through two passes:

1. Preprocess. Two views of the question: full text, and statement only (input/output sections and
   sample data removed, since numbers hurt embeddings). Code is cleaned, split into function sized
   snippets for repos, and capped with head 65 percent and tail 35 percent kept.
2. First pass, over the whole corpus:
   - dense: sentence-transformers embeddings, both query views (weights `w_full` 0.6, `w_stmt` 0.4)
   - BM25 over code words: identifiers split (`getUserID` to get, user, id), comments, strings; query
     words mapped to code words (maximum to max)
3. Second pass. Per query z-score of each scorer, then add: dense + `bm25_weight` x BM25 +
   `topic_weight` x topic match (13 hand written topics on both sides). RRF is available instead.

Versioned index (P1 and bonus): every snippet text is hashed and embedded once into a sqlite cache
keyed by sha1(model, kind, text). A new version only embeds changed functions. Ids are
`path::functionName`, so a function keeps its identity when lines move. "All versions" search groups
by function, folds identical text, and lists versions where the text changed.

## 5. Repo map

| Path | Purpose |
| --- | --- |
| `codeprism/preprocess.py` | query views, word map, identifier splitting, `clean_code` |
| `codeprism/categories.py` | 13 topic lexicon |
| `codeprism/lexical.py` | BM25 on scipy sparse matrices (k1 1.2, b 0.75) |
| `codeprism/embedders.py` | `PRESETS`, `EmbeddingCache`, sentence-transformers and hashing backends, `CachedEmbedder` (saves in slices, so a stopped run resumes) |
| `codeprism/retriever.py` | `PipelineConfig`, `HybridRetriever` |
| `codeprism/mteb_model.py` | `PrePostPipelineEncoder`: the class name the organizers' harness expects. Do not rename it |
| `codeprism/chunker.py` | Python via ast, JavaScript via brace matcher, line window fallback |
| `codeprism/versioned.py` | `VersionedIndex` |
| `codeprism/cli.py` | `demo`, `search --repo DIR "q"`, `history --versions v1=DIR ... "q"` |
| `scripts/run_eval.py` | full benchmark, writes `appsretrieval_results.json` and `run_summary.json` |
| `scripts/smoke_test.py` | speed check and time estimate before a long run |
| `scripts/tune.py` | model and weight grid on a sample of the test split (never run yet) |
| `scripts/update_results.py` | fills the README results block from `run_summary.json` and `runs/` |
| `configs/default.json` | model `bge-base` and the fusion weights. `configs/tuned.json`, if present, wins over it |
| `runs/<model>/run_summary.json` | one folder per full benchmark run. Add a folder for every new run |
| `demo/sample_repo/v1..v3` | JavaScript voice assistant, 33 / 36 / 38 functions |
| `tests/` | 19 offline tests, including an end to end MTEB run on a toy task |
| `submission/` | final deck, signed AI disclosure, `build_deck.py`, `fill_placeholders.py` |

Not in git on purpose: `appsretrieval_results.json` (release only), `.cache/`, `.venv/`, `results/`,
`CLAUDE.md`.

## 6. Commands

```
python -m venv .venv && source .venv/bin/activate      # Windows: py -m venv .venv, .venv\Scripts\python.exe
pip install -r requirements.txt                         # Python 3.10 to 3.13; tested on 3.13
python -m pytest -q tests                               # 19 tests, no internet needed
python -m codeprism.cli demo                            # real model from configs/default.json
python -m codeprism.cli --model hashing demo            # offline, no download, much weaker
python scripts/smoke_test.py --model bge-base           # time estimate first
caffeinate -i python scripts/run_eval.py --model bge-base   # full run (Mac); drop caffeinate elsewhere
python scripts/update_results.py                        # after a run: refresh README results
```

Model presets in `codeprism/embedders.py`: `bge-small`, `bge-base`, `e5-base`, `minilm`,
`gte-modernbert-base`, `coderank` (needs `einops` and trust_remote_code). Every preset is capped at
512 tokens unless the preset or config sets `max_seq_length`.

After every full run: copy `run_summary.json` and the log into `runs/<model>/`, run
`scripts/update_results.py`, and never overwrite another run's folder.

## 7. Results so far (exact, from runs/)

| Model | NDCG@10 | MRR@10 | Recall@10 | Wall clock | Machine |
| --- | --- | --- | --- | --- | --- |
| bge-base (submitted) | 0.06959 | 0.05843 | 0.10598 | 3051.7 s | Windows laptop, Intel i7-14650HX, 24 logical cores |
| bge-small | 0.06698 | 0.057086 | 0.09934 | 359.3 s | MacBook, 10 cores |

Same code and weights for both. Timings come from different machines and are not comparable.
gte-modernbert-base was never run in full: the smoke test estimated about 254 minutes on the MacBook
and 7 to 13 hours on teammates' laptops.

Demo with bge-base (`demo_output.txt`), 5 sample questions: 3 have the right function first; for
"passwords kept out of the logs" the redacting function `redactPii` is second; for "where is the
Settings deeplink created" the three callers rank above the builder `buildDeeplink`, which is not
in the top 3. Median 18 ms per question on the MacBook, including query embedding.

## 8. Decisions and why

- Hybrid, not dense only: problem statements are long and full of sample I/O, which blurs embeddings;
  BM25 over code words catches exact identifiers. Not yet measured with an ablation.
- Two query views: the narrative alone embeds better than the whole statement with numbers.
- Per query z-score fusion: weights mean the same on every query. RRF exists, never compared.
- bge-base over bge-small: higher score on the test split (disclosed). Bigger models were too slow on
  the team's CPUs before the original deadline.
- Ids are file plus function name, not line ranges: line ranges broke identity when lines moved.
- CPU only is a stated claim. A GPU run would break it; if one is ever used, say so and do not present
  its timing as CPU.

## 9. Known limits and gotchas

- Absolute score is low: about 9 in 10 questions miss the right document in the top 10.
- Callers can outrank the function that defines the behaviour (the deeplink case).
- Topic lexicon is hand written; JavaScript chunker is a brace matcher, not a parser; no call graph.
- `json.dump(task_result.to_dict())` fails on mteb 2.21.9 (datetime). `run_eval.py` uses MTEB's own
  `to_disk` instead. Keep it that way.
- Windows: set `PYTHONUTF8=1` when redirecting output to a file, or the progress bars crash on encoding.
- Hugging Face downloads were blocked in some cloud sandboxes. Never work around an egress block; run on
  a machine that can reach Hugging Face.
- The embedding cache is shared across models (keys include the model), so switching models is safe.
- Logs from teammates' machines can contain home directory paths. Redact usernames before committing.

## 10. Next steps, ranked

1. Measure before changing: run `scripts/tune.py` ablations (dense only, dense both views, hybrid) to
   learn whether BM25 and the topic bonus help at all. It samples the test split, so disclose it.
2. Tune fusion weights on data that is not the scored test split, if a train or dev split exists for
   CoIR apps; otherwise disclose test split tuning.
3. Try stronger or code specific embedders within the CPU budget: `e5-base`, `coderank`. Use
   `smoke_test.py` first.
4. Add a reranker (cross encoder) over the top 20.
5. Boost definitions over callers: give extra weight when a query word matches the snippet's own
   function name or its leading comment.
6. Larger work: tree-sitter chunkers, incremental BM25 for new versions, a call graph for structural
   questions, git history as versions.

## 11. People and links

- Team Procrastinators: Prakhar Joshi (repo owner, jjoshiprakhar@gmail.com), Sudiksha Kathuria (team
  leader, signed the AI disclosure), Navya Ghatta, Nihit Garg.
- Repo: https://github.com/pj4real/prism-code-retrieval
- Release: https://github.com/pj4real/prism-code-retrieval/releases/tag/PRISM_GENAI_HACKATHON_Y2026
- Demo video: https://drive.google.com/file/d/1JIUAlqLvp3eXkVWTokDIGYVLuQ3Ivu-s/view?usp=sharing
- Organizers' deck template: not in the repo; Prakhar has it. Needed only to rebuild the deck from
  scratch with `submission/build_deck.py`.
