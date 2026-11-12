import json

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.retrieval.api import create_app
from src.retrieval.bm25 import BM25
from src.retrieval.config import Settings
from src.retrieval.embeddings import (CachedEmbedder, ConfigError, EmbeddingCache, GeminiEmbedder,
                              HashingEmbedder, OpenAIEmbedder, make_embedder)
from src.retrieval.golden import LEXICAL, OFF_MATERIAL, SEMANTIC, evaluate
from src.retrieval.rerank import LexicalReranker, make_reranker
from src.retrieval.text import stem, tokenize

from .conftest import make_settings


# ---- text / BM25 ------------------------------------------------------------
def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("What is the chain rule?") == ["chain", "rule"]
    assert stem("derivatives") == stem("derivative")
    assert stem("computing") == "comput" and stem("class") == "class"


def test_bm25_ranks_matching_doc_first():
    docs = ["the chain rule differentiates composed functions", "pasta recipe with tomato", "learning rate step size"]
    scores = BM25(docs).scores("chain rule")
    assert scores.index(max(scores)) == 0 and scores[1] == 0


# ---- hashing embedder -------------------------------------------------------
def test_hashing_embedder_is_deterministic_and_normalised():
    e = HashingEmbedder()
    a, b = e.embed_documents(["gradient descent"]), e.embed_documents(["gradient descent"])
    assert np.allclose(a, b) and np.isclose(np.linalg.norm(a[0]), 1.0)


def test_hashing_embedder_prefers_related_text():
    e = HashingEmbedder()
    q = e.embed_query("learning rate too large overshoots")
    docs = e.embed_documents(["a large learning rate overshoots the minimum", "recipe for tomato pasta"])
    assert docs[0] @ q > docs[1] @ q


# ---- retrieval quality on the mock corpus (built-in fallback backend) --------
def test_lexical_golden_set(retriever):
    h1, _ = evaluate(retriever, LEXICAL, 1)
    h3, mrr = evaluate(retriever, LEXICAL, 3)
    assert h3 >= 0.95 and h1 >= 0.80 and mrr >= 0.85


def test_semantic_golden_set_floor(retriever):
    # the fallback has no semantics; this is only a regression floor, not a quality claim
    h3, _ = evaluate(retriever, SEMANTIC, 3)
    assert h3 >= 0.8


def test_off_topic_with_no_shared_vocabulary_scores_zero(retriever):
    zero = [q for q in OFF_MATERIAL if q != "best way to learn guitar"]
    for q in zero:
        hits = retriever.search(q, 1)
        assert (hits[0].relevance if hits else 0.0) == 0.0, q


def test_known_limit_generic_word_overlap_leaks_past_a_lexical_relevance_score(retriever):
    """'learn' appears in the course, so a guitar question scores > 0 and above the weakest in-scope query.
    A relevance threshold alone cannot separate these on the fallback backend; that is why answering has a
    second, LLM-based gate (see test_step4) and why thresholds are calibrated per backend."""
    in_scope_min = min(retriever.search(q, 1)[0].relevance for q, _ in LEXICAL + SEMANTIC)
    assert retriever.search("best way to learn guitar", 1)[0].relevance > in_scope_min


def test_filters_by_source_type_and_id(retriever):
    assert {h.unit.source_type for h in retriever.search("gradient descent", 8, source_types=["video"])} == {"video"}
    hits = retriever.search("gradient descent", 8, source_ids=["ML_Textbook"])
    assert hits and all(h.unit.source_id == "ML_Textbook" for h in hits)
    assert retriever.search("gradient descent", 5, source_ids=["nope"]) == []


def test_empty_query_returns_nothing(retriever):
    assert retriever.search("   ") == []


def test_results_sorted_by_relevance(retriever):
    rel = [h.relevance for h in retriever.search("gradient descent learning rate", 6)]
    assert rel == sorted(rel, reverse=True)


# ---- provider selection (no network) ---------------------------------------
def test_default_retrieval_starts_without_using_configured_cloud_key(store, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("RERANK_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "rejected-key")
    monkeypatch.setenv("OPENAI_API_KEY", "your_openai_api_key_here")
    monkeypatch.setenv("REPLICATE_API_KEY", "your_replicate_api_key_here")
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    settings = Settings.from_env()
    assert settings.gemini_api_key == "rejected-key"
    assert not settings.openai_api_key and not settings.replicate_api_key
    app = create_app(store=store, settings=settings, persist=False)
    assert app.state.runtime.bundle.retriever.backend_key() == "hash:512|lexical"


def test_auto_picks_openai_then_gemini_then_fallback():
    assert make_embedder(make_settings(openai_api_key="sk-x"))[0].name.startswith("openai:")
    assert make_embedder(make_settings(gemini_api_key="g-x"))[0].name.startswith("gemini:")
    both = make_embedder(make_settings(openai_api_key="a", gemini_api_key="b"))[0]
    assert both.name.startswith("openai:")  # documented precedence
    assert make_embedder(make_settings(embedding_provider="hash"))[0].name.startswith("hash:")


def test_explicit_provider_without_key_fails_clearly():
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        make_embedder(make_settings(embedding_provider="openai"))
    with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
        make_embedder(make_settings(embedding_provider="gemini"))
    with pytest.raises(ConfigError, match="unknown"):
        make_embedder(make_settings(embedding_provider="bogus"))


def test_model_override_is_respected():
    e, _ = make_embedder(make_settings(openai_api_key="k", embedding_model="text-embedding-3-large"))
    assert e.name == "openai:text-embedding-3-large"


def test_rerank_factory_lexical_and_errors():
    assert make_reranker(make_settings(rerank_provider="lexical"))[0].name == "lexical"
    with pytest.raises(ConfigError):
        make_reranker(make_settings(rerank_provider="bogus"))


# ---- hosted embedders: request shape / parsing via a fake transport ----------
def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_openai_request_shape_batching_and_ordering():
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append((req.url.path, req.headers["authorization"], len(body["input"])))
        # return out of order to prove we sort by index
        data = [{"index": i, "embedding": [float(i + 1), 0.0]} for i in range(len(body["input"]))][::-1]
        return httpx.Response(200, json={"data": data})

    e = OpenAIEmbedder("sk-test", client=_client(handler), sleep=lambda s: None)
    out = e.embed_documents([f"t{i}" for i in range(100)])  # 96 + 4
    assert [s[2] for s in seen] == [96, 4] and seen[0][0] == "/v1/embeddings"
    assert seen[0][1] == "Bearer sk-test"
    assert out.shape == (100, 2) and np.allclose(np.linalg.norm(out, axis=1), 1.0)
    assert out[0, 0] == pytest.approx(1.0) and out[1, 0] == pytest.approx(1.0)  # normalised [i+1, 0]


def test_gemini_request_shape_and_task_types():
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append((req.url.path, req.headers["x-goog-api-key"], {r["taskType"] for r in body["requests"]}))
        return httpx.Response(200, json={"embeddings": [{"values": [3.0, 4.0]} for _ in body["requests"]]})

    e = GeminiEmbedder("g-test", client=_client(handler), sleep=lambda s: None)
    docs = e.embed_documents(["a", "b"])
    q = e.embed_query("c")
    assert seen[0][2] == {"RETRIEVAL_DOCUMENT"} and seen[1][2] == {"RETRIEVAL_QUERY"}
    assert seen[0][0].endswith(":batchEmbedContents") and seen[0][1] == "g-test"
    assert np.allclose(docs[0], [0.6, 0.8]) and np.allclose(q, [0.6, 0.8])


def test_retry_on_429_then_success():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0]}]})

    sleeps = []
    e = OpenAIEmbedder("k", client=_client(handler), sleep=sleeps.append)
    assert e.embed_query("x").shape == (2,) and calls["n"] == 3 and sleeps == [1, 2]


def test_api_error_does_not_leak_key():
    e = OpenAIEmbedder("sk-secret", client=_client(lambda r: httpx.Response(401, text="bad key")), sleep=lambda s: None)
    with pytest.raises(RuntimeError) as ei:
        e.embed_query("x")
    assert "401" in str(ei.value) and "sk-secret" not in str(ei.value)


# ---- caching: paid APIs are only called once per unit ----------------------
def test_cache_prevents_repeat_backend_calls(tmp_path):
    inner = HashingEmbedder()
    cached = CachedEmbedder(inner, EmbeddingCache(tmp_path / "c.sqlite"))
    a = cached.embed_documents(["alpha", "beta"])
    assert cached.api_calls == 2
    b = cached.embed_documents(["alpha", "beta", "gamma"])
    assert cached.api_calls == 3 and np.allclose(a, b[:2])
    # new process: still cached
    again = CachedEmbedder(inner, EmbeddingCache(tmp_path / "c.sqlite"))
    again.embed_documents(["alpha", "gamma"])
    assert again.api_calls == 0


def test_cache_is_keyed_by_embedder_name(tmp_path):
    cache = EmbeddingCache(tmp_path / "c.sqlite")
    assert cache.key("openai:a", "x") != cache.key("openai:b", "x")


# ---- API --------------------------------------------------------------------
@pytest.fixture(scope="module")
def client(store, retriever):
    from src.graph.graph import KnowledgeGraph
    from src.retrieval.store import DEFAULT_GRAPH
    return TestClient(create_app(store, retriever, KnowledgeGraph.load(DEFAULT_GRAPH)))


def test_search_endpoint_returns_deep_linked_citation(client):
    r = client.get("/pod-b/search", params={"q": "loss surface diagram", "k": 3})
    assert r.status_code == 200
    top = r.json()[0]
    assert top["unit_id"] == "sl-14"
    assert top["citation"]["label"] == "Slide 14"
    assert top["citation"]["open_url"] == "/sources/ML_Slides_L2#slide=14"


def test_search_endpoint_filters_and_validates(client):
    r = client.get("/pod-b/search", params={"q": "gradient descent", "k": 8, "source_type": "video"})
    assert r.status_code == 200 and r.json()
    assert all(h["citation"]["open_url"].startswith("/sources/ML_Lecture_2?t=") for h in r.json())
    assert client.get("/pod-b/search", params={"q": "x", "source_type": "audio"}).status_code == 422
    assert client.get("/pod-b/search").status_code == 422


def test_retrieval_info_endpoint(client):
    body = client.get("/pod-b/retrieval/info").json()
    assert body["embedder"].startswith("hash:") and body["units"] == 28
