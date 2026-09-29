# AI usage disclosure

Most of this repository was written by an AI assistant (Claude (Anthropic), used through the Claude desktop app (Cowork)) at the direction of the team. The team chose the theme and scope and runs the benchmark on its own machine. The embedding model is a third party pretrained model and was not trained by us.

| Purpose | Used | Notes |
| --- | --- | --- |
| Idea generation | Yes | Choice of the hybrid design (dense + keyword + topic bonus), the versioned index, and the list of limits. |
| Code generation or assistance | Yes | All source code, tests, Dockerfile and scripts were written by the AI at the team's direction. |
| UI/UX design | No | There is no UI. The demo is a command line tool. |
| Content creation | Yes | README, presentation text and this disclosure were drafted by the AI. |
| Data analysis | No | No analysis was done by the AI. Benchmark numbers come from running the code on the team's own machine. |
| Testing and debugging | Yes | The AI wrote the tests and fixed bugs it found while running them. |
| Other | Yes | The team picked the theme and ran the benchmark themselves. |

## Feature origin

| Feature | Origin | Where |
| --- | --- | --- |
| Query preprocessing and views | AI-Generated | codeprism/preprocess.py |
| Topic lexicon (query and snippet categories) | AI-Generated | codeprism/categories.py |
| BM25 keyword search over code words | AI-Generated | codeprism/lexical.py |
| Dense retrieval and score fusion | AI-Generated | codeprism/embedders.py, codeprism/retriever.py |
| MTEB adapter and evaluation script | AI-Generated | codeprism/mteb_model.py, scripts/run_eval.py |
| Embedding cache and versioned index (P1, bonus) | AI-Generated | codeprism/versioned.py |
| Code chunker | AI-Generated | codeprism/chunker.py |
| Command line demo and sample repo | AI-Generated | codeprism/cli.py, demo/sample_repo/ |
| Tests, Dockerfile, README | AI-Generated | tests/, Dockerfile, README.md |
| Presentation | AI-Generated | Submission .pptx |
| Theme choice and project scope | Both | Decision |

The signed form is submitted separately with the Google Form.
