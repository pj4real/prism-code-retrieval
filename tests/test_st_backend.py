"""Checks the sentence-transformers code path using a tiny random model built locally."""
import numpy as np
import pytest

from codeprism import HybridRetriever, PipelineConfig
from tests.toy_data import QUERIES, SNIPPETS


@pytest.fixture(scope="module")
def tiny_model_dir(tmp_path_factory):
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers
    from transformers import BertConfig, BertModel, PreTrainedTokenizerFast

    d = tmp_path_factory.mktemp("tiny")
    tok = Tokenizer(models.WordPiece(unk_token="[UNK]"))
    tok.pre_tokenizer = pre_tokenizers.Whitespace()
    trainer = trainers.WordPieceTrainer(
        vocab_size=600, special_tokens=["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
    )
    corpus = list(SNIPPETS.values()) + [v[0] for v in QUERIES.values()]
    tok.train_from_iterator(corpus, trainer)
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="[UNK]", pad_token="[PAD]", cls_token="[CLS]",
        sep_token="[SEP]", mask_token="[MASK]",
    )
    fast.save_pretrained(d)
    cfg = BertConfig(vocab_size=tok.get_vocab_size(), hidden_size=32, num_hidden_layers=1,
                     num_attention_heads=2, intermediate_size=64, max_position_embeddings=512)
    BertModel(cfg).save_pretrained(d)
    return str(d)


def test_sentence_transformer_path(tiny_model_dir, tmp_path):
    cfg = PipelineConfig(model=tiny_model_dir, cache_path=str(tmp_path / "c.sqlite"), max_seq_length=128)
    r = HybridRetriever(cfg)
    ids = list(SNIPPETS)
    idx = r.build_index(ids, [SNIPPETS[i] for i in ids])
    assert idx.dense.shape[0] == len(ids)
    assert np.allclose(np.linalg.norm(idx.dense, axis=1), 1.0, atol=1e-4)
    hits = r.search(idx, [v[0] for v in QUERIES.values()], top_k=3)
    assert all(len(h) == 3 for h in hits)


def test_cache_prevents_reembedding(tiny_model_dir, tmp_path):
    cfg = PipelineConfig(model=tiny_model_dir, cache_path=str(tmp_path / "c.sqlite"), max_seq_length=128)
    r = HybridRetriever(cfg)
    ids = list(SNIPPETS)
    texts = [SNIPPETS[i] for i in ids]
    first = r.build_index(ids, texts)
    second = r.build_index(ids, texts)
    assert first.embedded_new == len(ids)
    assert second.embedded_new == 0 and second.embedded_cached == len(ids)
    # reopen from disk in a new retriever
    r3 = HybridRetriever(cfg)
    third = r3.build_index(ids, texts)
    assert third.embedded_new == 0, "sqlite cache should survive a new process"
