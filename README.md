# Hybrid code retrieval for Samsung PRISM Gen AI Hackathon 3.0, Theme 1

Given a question in plain English and a large pile of code, return the code snippets that answer it, best first. This is Theme 1 (Agentic Code Intelligence). Following the problem statement, we only do the retrieval step. Generating answers is out of scope.

It runs on CPU. No GPU is needed.

## What it does

A query goes through three steps.

1. Preprocess. The query is cleaned and split into two views: the whole text, and just the narrative part without the input/output boilerplate and the sample data (numbers hurt embeddings). The code side is cleaned, split into function sized snippets when it comes from a repo, and capped in length so the head and tail both survive truncation.
2. First pass. Two scorers run over the whole corpus. A dense scorer compares embeddings from a small sentence-transformers model. A keyword scorer (BM25) works over words taken from the code: identifiers split into their parts (`getUserID` becomes get, user, id), comments, and strings. Query words are also mapped to the words they usually turn into in code (maximum to max, sorted to sort, and so on).
3. Second pass. The scores are standardised per query and added: dense, plus BM25, plus a small bonus when the query and the snippet look like the same kind of problem (graph, dp, string, math and so on, detected with a keyword lexicon on both sides). The weights live in a config file.

That covers four of the five improvement ideas in the problem statement: categorizing the query, preprocessing the query, categorizing snippets, pre and post processing of snippets, and multiple retrieval passes.

## Retrieval across versions (P1 and the bonus)

`codeprism/versioned.py`. A snippet's embedding depends only on its text, so text is hashed and each unique text is embedded once and kept in a small sqlite cache. When a new version arrives, only changed functions are embedded. Building a searchable index for a version is then a cache lookup plus refitting BM25.

On the bundled sample repo (three versions of a small JavaScript voice assistant, `demo/sample_repo`) the first version embeds all 33 functions, the second embeds only the 8 that changed and reuses 28, the third embeds 7 and reuses 31.

You can search one version, or all of them at once. In the all-versions mode, results are grouped by function. Versions where the function's text is identical are folded into one hit, and versions where it changed are listed with their own scores, so near duplicates across versions do not fill the top ten.

## Setup

Python 3.10 or newer.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The first run downloads the embedding model and the CoIR apps dataset from Hugging Face.

## Reproduce the submission file

```
python scripts/run_eval.py
```

This runs the `AppsRetrieval` task (CoIR apps, test split) through MTEB, using our `PrePostPipelineEncoder`, and writes:

- `appsretrieval_results.json`, the results file for the screening stage
- `run_summary.json`, with the scores, timings and the exact config used

The config comes from `configs/tuned.json` if it exists, otherwise `configs/default.json`. Pass `--config` to choose another one.

A note on saving the file. The sample code in the problem statement writes the result with `json.dump(task_result.to_dict(), ...)`. On recent MTEB versions (we tested 2.21.9) that fails, because `to_dict()` contains a datetime. `run_eval.py` uses MTEB's own `task_result.to_disk(...)` instead, which writes the same content with the date stored as a timestamp.

## Optional: tune on a sample first

A full run on a laptop CPU takes a while, so `scripts/tune.py` compares models and fusion weights on a sample of queries (all their relevant documents plus random distractors):

```
python scripts/tune.py --models gte-modernbert-base,bge-small --queries 300 --docs 3000 --write-config configs/tuned.json
```

Embeddings are cached in `.cache/embeddings.sqlite`, so every text is embedded once per model and the weight grid afterwards is nearly free. The full run reuses that cache.

Be aware of what this does. The sample comes from the test split, since that is the only labelled split we know the organizers score on. Only four numbers are tuned (BM25 weight, topic weight, view weights, fusion type), but the reported final score should be read with that in mind.

## Demo

```
python -m codeprism.cli demo
```

This indexes the three versions of the sample repo, answers a set of questions against the latest version, asks the same question against the oldest version, and then searches across all versions, printing file and line locations and latency for each query.

Search any folder of Python or JavaScript:

```
python -m codeprism.cli search --repo path/to/repo "where is the bluetooth deeplink built?"
python -m codeprism.cli history --versions v1=path/one v2=path/two "how are utterances cleaned?"
```

Add `--model hashing` to run with no model download. That backend is only feature hashing of code words. It is there for tests and a quick look, and it is much weaker than a real embedding model.

## Docker

```
docker build -t prism-code-retrieval .
docker run --rm -v hf-cache:/root/.cache/huggingface -v "$PWD/out":/app/out prism-code-retrieval
```

The result file appears in `./out`. To run the demo instead: `docker run --rm prism-code-retrieval -m codeprism.cli demo`.

## Tests

```
python -m pytest -q tests
```

The tests need no internet. They cover preprocessing, BM25, the topic lexicon, the chunkers, the embedding cache, version handling, a sentence-transformers path using a tiny random model built on the fly, and a full `mteb.evaluate` run on a small local task that checks the results file has the NDCG@10 and MRR@10 fields.

## Layout

```
codeprism/
  preprocess.py    query views, code cleaning, identifier splitting
  categories.py    topic lexicon for queries and code
  lexical.py       BM25 on scipy sparse matrices
  embedders.py     model presets, sqlite embedding cache
  retriever.py     the two pass pipeline and its config
  mteb_model.py    PrePostPipelineEncoder for MTEB
  chunker.py       Python (ast) and JavaScript (brace matching) chunking
  versioned.py     index across versions
  cli.py           demo, search, history
scripts/           run_eval.py, tune.py, update_results.py
configs/           default.json (and tuned.json after tuning)
demo/sample_repo/  three versions of a small JavaScript voice assistant
tests/
```

## Results

<!-- RESULTS:START -->
Measured on the CoIR apps test split with `scripts/run_eval.py` (full corpus, all queries).

| Metric | Value |
| --- | --- |
| NDCG@10 | 0.06959 |
| MRR@10 | 0.05843 |
| Documents / queries | 8765 / 3765 |
| Recall@10 | 0.10598 |
| Total wall clock | 3051.7 s on 24 CPU cores |

Model: `bge-base`. BM25 weight 0.25, topic weight 0.15, fusion zscore, topic tags in text: False.

Every full run we made, with the same code and weights (`runs/*/run_summary.json`):

| Model | NDCG@10 | MRR@10 | Wall clock | CPU cores |
| --- | --- | --- | --- | --- |
| bge-base | 0.06959 | 0.05843 | 3051.7 s | 24 |
| bge-small | 0.06698 | 0.057086 | 359.3 s | 10 |

We submitted the model with the higher score. Both were scored on the same test split, so picking between them is a choice made on test data, and the submitted number should be read with that in mind. bge-small ran on a MacBook (10 cores), bge-base on a teammate's Windows laptop (Intel Core i7-14650HX, 24 logical cores), so the wall clock times are not comparable. Both runs were CPU only.

These weights were set by hand. They were not tuned.
<!-- RESULTS:END -->

## Limits and honest notes

- The topic lexicon is a hand written list of keywords, not a trained classifier. It gives a small bonus and can be switched off (`topic_weight: 0`).
- The JavaScript chunker is a brace matcher that handles strings, comments and template literals, not a full parser. Unusual syntax can produce a wrong chunk. Files with no detectable functions fall back to overlapping line windows.
- Structural questions such as "which files call tool A before tool B" need a call graph. The Theme 1 guidelines we were given only ask for retrieval, so we did not build that.
- The dense model is a third party pretrained model (`BAAI/bge-base-en-v1.5`, the `bge-base` preset in `configs/default.json`). We did not train or fine tune anything.
- Per query latency in the demo includes embedding the query on CPU.

## Submission materials

- Presentation: [submission/VITV_Procrastinators_Submission.pptx](submission/VITV_Procrastinators_Submission.pptx)
- Demo video: https://drive.google.com/file/d/1JIUAlqLvp3eXkVWTokDIGYVLuQ3Ivu-s/view?usp=sharing
- AI disclosure: [AI_DISCLOSURE.md](AI_DISCLOSURE.md) and [submission/VITV_Procrastinators_AI_Disclosure.docx](submission/VITV_Procrastinators_AI_Disclosure.docx)
- Benchmark output: `appsretrieval_results.json`, attached to the GitHub release `PRISM_GENAI_HACKATHON_Y2026`. The scores above come from `run_summary.json` in this repo.

## AI usage

See `AI_DISCLOSURE.md`.
