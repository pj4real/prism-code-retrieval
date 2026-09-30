# AI usage disclosure

Most of this repository was written by an AI assistant (Claude (Anthropic), used through the Claude desktop app (Cowork and Claude Code)) at the direction of the team. The team chose the theme and scope. The benchmark ran on the team's own laptop, launched through Claude Code at the team's direction. The embedding model is a third party pretrained model and was not trained by us.

| Purpose | Used | Notes |
| --- | --- | --- |
| Idea generation | Yes | Choice of the hybrid design (dense + keyword + topic bonus), the versioned index, and the list of limits. |
| Code generation or assistance | Yes | All source code, tests, Dockerfile and scripts were written by the AI at the team's direction. |
| UI/UX design | No | There is no UI. The demo is a command line tool. |
| Content creation | Yes | README, presentation text, this disclosure, and the demo video and its script were made with the AI. |
| Data analysis | Yes | The AI launched the benchmark on the team's own laptop at the team's direction and copied the scores from run_summary.json. It did not change or estimate any score. |
| Testing and debugging | Yes | The AI wrote the tests and fixed bugs it found while running them. |
| Other | Yes | The team picked the theme, chose the model and approved each benchmark run. |

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
| Demo video and voiceover script | AI-Generated | Demo video (link in the README and the deck) |
| Theme choice and project scope | Both | Decision |

The signed form is submitted separately with the Google Form.
