"""Run the pipeline through the real mteb.evaluate on a tiny local task (no downloads)."""
import json

import mteb
from datasets import Dataset
from mteb.abstasks.retrieval import AbsTaskRetrieval

from codeprism import PipelineConfig
from codeprism.mteb_model import PrePostPipelineEncoder
from tests.toy_data import QUERIES, SNIPPETS


class TinyLocalRetrieval(AbsTaskRetrieval):
    metadata = mteb.get_task("AppsRetrieval").metadata.model_copy(
        update={"name": "TinyLocalRetrieval", "dataset": {"path": "local/none", "revision": "0"}}
    )

    def load_data(self, num_proc=None, **kwargs):
        corpus = Dataset.from_dict(
            {"id": list(SNIPPETS), "title": [""] * len(SNIPPETS), "text": list(SNIPPETS.values())}
        )
        queries = Dataset.from_dict(
            {"id": list(QUERIES), "text": [v[0] for v in QUERIES.values()]}
        )
        qrels = {q: {v[1]: 1} for q, v in QUERIES.items()}
        self.dataset = {"default": {"test": {
            "corpus": corpus, "queries": queries, "relevant_docs": qrels, "top_ranked": None,
        }}}
        self.data_loaded = True


def test_mteb_evaluate_runs_and_writes_json(tmp_path):
    model = PrePostPipelineEncoder(PipelineConfig(model="hashing", cache_path=None))
    task = TinyLocalRetrieval()
    result = mteb.evaluate(model, [task], encode_kwargs={"batch_size": 8}, cache=None)
    tr = list(result.task_results)[0]
    out = tmp_path / "appsretrieval_results.json"
    tr.to_disk(out)
    data = json.loads(out.read_text())
    score = data["scores"]["test"][0]
    assert "ndcg_at_10" in score and "mrr_at_10" in score, list(score)
    assert score["ndcg_at_10"] > 0.5
    print({k: score[k] for k in ("ndcg_at_10", "mrr_at_10")}, model.stats)
