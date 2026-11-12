import pytest
from fastapi.testclient import TestClient

from src.retrieval.answer import GroundedAnswerer
from src.retrieval.api import create_app
from src.retrieval.bm25 import BM25
from src.retrieval.calibration import PROVISIONAL, calibrate, load_threshold, save_calibration, top_relevances
from src.retrieval.embeddings import HashingEmbedder
from src.retrieval.golden import LEXICAL, NEAR_MISS, OFF_MATERIAL, SEMANTIC, evaluate
from src.graph.graph import KnowledgeGraph
from src.retrieval.llm import LLMError
from src.retrieval.rerank import LexicalReranker
from src.retrieval.retriever import CONCEPT_BOOST, HybridRetriever
from src.retrieval.schemas import AnswerStatus, ContentUnit, Location
from src.retrieval.store import DEFAULT_GRAPH, CorpusStore

from .fakes import ScriptedLLM

STRICT, PERM = PROVISIONAL["hash:512|lexical"]


@pytest.fixture(scope="module")
def store4():
    return CorpusStore.from_json()


@pytest.fixture(scope="module")
def graph4():
    return KnowledgeGraph.load(DEFAULT_GRAPH)


def _retriever(store, graph=None, pool=20):
    idf = BM25([u.searchable_text() for u in store.all()])._idf
    return HybridRetriever(store, HashingEmbedder(), LexicalReranker(idf), pool, graph=graph)


@pytest.fixture(scope="module")
def rg(store4, graph4):
    return _retriever(store4, graph4)


def answerer(rg, graph, llm=None, **kw):
    return GroundedAnswerer(rg, graph, llm, threshold_strict=STRICT, threshold_permissive=PERM, **kw)


def good_answer(prompt):
    return {"answerable": True, "claims": [
        {"text": "The chain rule differentiates a composition: dy/dx = f'(g(x)) * g'(x).", "unit_ids": ["sl-08"]},
        {"text": "Differentiate the outside function and multiply by the derivative of the inside.", "unit_ids": ["vd-0440"]},
    ], "outside_knowledge": []}


# ---- concept boost -------------------------------------------------------------
def test_concept_boost_puts_definition_chunks_first(store4, graph4, rg):
    plain = _retriever(store4, None).search("what is the chain rule", 1)[0].unit.unit_id
    boosted = rg.search("what is the chain rule", 3)
    assert plain == "vd-0035"  # the documented problem: a passing mention outranks the definition
    assert {h.unit.unit_id for h in boosted} <= {"sl-08", "sl-09", "tb-0118", "vd-0440"}


def test_boost_changes_ordering_score_but_not_relevance(rg):
    h = rg.search("what is the chain rule", 1)[0]
    assert h.score == pytest.approx(h.relevance + CONCEPT_BOOST) and h.relevance <= 1.0


def test_boosted_evidence_enters_candidate_pool_even_when_pool_is_tiny(store4, graph4):
    r = _retriever(store4, graph4, pool=1)
    assert {"sl-08", "tb-0118", "vd-0440"} & {h.unit.unit_id for h in r.search("what is the chain rule", 3)}


def test_boost_respects_source_filters(rg):
    hits = rg.search("what is the chain rule", 5, source_types=["video"])
    assert hits and all(h.unit.source_type == "video" for h in hits)


def test_boost_lifts_golden_top1_to_perfect_on_lexical_set(rg):
    # NB: graph and queries were both hand-written by the same author on this corpus - optimistic by construction
    assert evaluate(rg, LEXICAL, 1)[0] == 1.0


# ---- calibration ------------------------------------------------------------------
def test_calibrate_separable_groups():
    r = calibrate([0.6, 0.7, 0.9], [0.0, 0.1, 0.2])
    assert 0.2 < r["threshold"] < 0.6 and r["balanced_accuracy"] == 1.0
    assert r["threshold_permissive"] == pytest.approx(0.48)  # 0.8 x lowest in-scope


def test_calibrate_overlapping_groups_reports_the_tradeoff():
    r = calibrate([0.27, 0.5, 0.6, 0.8], [0.0, 0.0, 0.38])
    assert r["balanced_accuracy"] < 1.0 and r["in_scope_min"] == 0.27 and r["off_scope_max"] == 0.38


def test_provisional_thresholds_match_what_calibration_measures_today(rg):
    ins = top_relevances(rg, [q for q, _ in LEXICAL + SEMANTIC])
    r = calibrate(ins, top_relevances(rg, OFF_MATERIAL))
    assert r["threshold"] == pytest.approx(STRICT, abs=0.03) and r["threshold_permissive"] == pytest.approx(PERM, abs=0.03)


def test_threshold_load_save_roundtrip_and_flags(tmp_path):
    f = tmp_path / "cal.json"
    assert load_threshold(f, "hash:512|lexical") == (*PROVISIONAL["hash:512|lexical"], False)
    assert load_threshold(f, "openai:x|lexical")[2] is False
    save_calibration(f, "openai:x|lexical", calibrate([0.5, 0.9], [0.1, 0.2]))
    s, p, cal = load_threshold(f, "openai:x|lexical")
    assert cal and 0.2 < s < 0.5 and p == pytest.approx(0.4)


# ---- extractive mode (no LLM) ---------------------------------------------------------
def test_extractive_answer_is_grounded_cited_and_deep_linked(rg, graph4):
    r = answerer(rg, graph4).answer("what is the chain rule")
    assert r.status == AnswerStatus.GROUNDED and r.mode == "extractive"
    assert r.sources and all(s.open_url.startswith("/sources/") for s in r.sources)
    assert "[1]" in r.answer and all(c.supported and c.citations for c in r.claims)
    assert set(s.unit_id for s in r.sources) <= set(r.retrieved)


def test_off_topic_is_refused_with_course_topics(rg, graph4):
    for q in OFF_MATERIAL:
        if q == "best way to learn guitar":
            continue  # known limit of the lexical fallback; see test below
        r = answerer(rg, graph4).answer(q)
        assert r.status == AnswerStatus.REFUSED and r.mode == "refusal" and r.claims == [] and r.sources == [], q
        assert "course material" in r.message and "Calculus" in r.message


def test_strict_gate_catches_the_generic_word_overlap_case(rg, graph4):
    assert answerer(rg, graph4).answer("best way to learn guitar").status == AnswerStatus.REFUSED  # strict threshold 0.42


def test_extractive_definition_rejects_one_word_overlap_and_old_topic():
    snippets = [
        ("nlp", "The language model is conditioned on each retrieved passage."),
        ("other", "A transistor controls an electrical signal."),
        ("algebra", "The chain rule differentiates a composition of functions."),
        ("biology", "Cells carry genetic information."),
    ]
    store = CorpusStore(ContentUnit(
        unit_id=name, source_id=name, source_type="pdf", location=Location(page=1), text=text,
    ) for name, text in snippets)
    retriever = _retriever(store)
    query = "What is race condition?"
    assert retriever.search(query, 1)[0].relevance >= STRICT
    result = answerer(retriever, None).answer(query, history=[
        {"role": "user", "content": "What is the chain rule?"},
    ])
    assert result.status == AnswerStatus.REFUSED and not result.sources
    assert result.standalone_question is None


def test_extractive_definition_ignores_filename_and_quotes_matching_sentence():
    wrong = ContentUnit(
        unit_id="filename", source_id="filename", source_type="pdf", location=Location(page=1),
        text="Page 1 (Race condition): The language model is conditioned on each retrieved passage.",
    )
    right = ContentUnit(
        unit_id="os", source_id="os", source_type="slides", location=Location(slide=6),
        text="Slide 6 (Operating Systems): Chapter overview. Review last week's material. "
             "A race condition occurs when the outcome depends on the timing of concurrent operations.",
    )
    a = answerer(_retriever(CorpusStore([wrong, right])), None)
    result = a.answer("What is a race condition?")
    assert result.status == AnswerStatus.GROUNDED
    assert [citation.unit_id for citation in result.sources] == ["os"]
    assert result.sources[0].excerpt.startswith("A race condition occurs")
    assert "Chapter overview" not in result.answer
    assert a.answer("What is a race condition?", source_ids=["filename"]).status == AnswerStatus.REFUSED


def test_gate_refuses_before_spending_an_llm_call(rg, graph4):
    llm = ScriptedLLM()  # any call raises AssertionError
    assert answerer(rg, graph4, llm).answer("who won the football world cup").status == AnswerStatus.REFUSED
    assert llm.calls == []


# ---- generative mode -------------------------------------------------------------------
def test_generative_grounded_answer(rg, graph4):
    llm = ScriptedLLM(answer=good_answer)
    r = answerer(rg, graph4, llm).answer("what is the chain rule")
    assert r.status == AnswerStatus.GROUNDED and r.mode == "generative" and r.confidence == 1.0
    assert [s.unit_id for s in r.sources] == ["sl-08", "vd-0440"]
    assert r.answer.endswith("[2]") and "[1]" in r.answer
    assert r.sources[1].label == "@7:20" and r.sources[1].open_url == "/sources/ML_Lecture_2?t=440"
    assert r.outside_knowledge == []


def test_invented_unit_ids_are_dropped_and_unsupported_claim_is_flagged(rg, graph4):
    def ans(prompt):
        return {"answerable": True, "claims": [
            {"text": "The chain rule differentiates a composition of functions.", "unit_ids": ["sl-08", "zz-999"]},
            {"text": "It was invented by Leibniz in 1676.", "unit_ids": ["zz-999"]},
        ]}
    r = answerer(rg, graph4, ScriptedLLM(answer=ans)).answer("what is the chain rule")
    assert r.status == AnswerStatus.PARTIAL
    assert [c.supported for c in r.claims] == [True]  # unsupported claim is not presented as a claim
    assert r.outside_knowledge == ["It was invented by Leibniz in 1676."]
    assert [s.unit_id for s in r.sources] == ["sl-08"] and "Leibniz" not in r.answer
    assert r.confidence == 0.5


def test_claim_not_supported_by_its_cited_unit_is_flagged(rg, graph4):
    def ans(prompt):
        return {"answerable": True, "claims": [
            {"text": "The chain rule differentiates a composition of functions.", "unit_ids": ["sl-08"]},
            {"text": "Quantum entanglement violates Bell inequalities.", "unit_ids": ["sl-08"]},  # cites a real but irrelevant unit
        ]}
    r = answerer(rg, graph4, ScriptedLLM(answer=ans)).answer("what is the chain rule")
    assert r.status == AnswerStatus.PARTIAL and r.outside_knowledge == ["Quantum entanglement violates Bell inequalities."]


def test_llm_fact_check_can_veto_a_lexically_plausible_claim(rg, graph4):
    def ans(prompt):
        return {"answerable": True, "claims": [
            {"text": "The chain rule differentiates a composition of functions.", "unit_ids": ["sl-08"]},
            {"text": "The chain rule means the derivative of a sum is the sum of derivatives.", "unit_ids": ["sl-08"]},
        ]}
    llm = ScriptedLLM(answer=ans, verify=lambda p: {"verdicts": [{"i": 0, "supported": True}, {"i": 1, "supported": False}]})
    r = answerer(rg, graph4, llm, verify_with_llm=True).answer("what is the chain rule")
    assert llm.calls == ["answer", "verify"] and r.status == AnswerStatus.PARTIAL
    assert [c.supported for c in r.claims] == [True] and len(r.outside_knowledge) == 1


def test_fact_check_needs_an_affirmative_verdict(rg, graph4):
    llm = ScriptedLLM(answer=good_answer, verify=lambda _: {"verdicts": []})
    result = answerer(rg, graph4, llm, verify_with_llm=True).answer("what is the chain rule")
    assert result.status == AnswerStatus.REFUSED and not result.sources


def test_near_miss_passes_the_gate_but_the_llm_refuses(rg, graph4):
    llm = ScriptedLLM(answer=lambda p: {"answerable": False, "claims": [], "outside_knowledge": []})
    r = answerer(rg, graph4, llm).answer("what is a convolutional neural network")
    assert llm.calls == ["answer"] and r.status == AnswerStatus.REFUSED and r.sources == []


def test_outside_knowledge_only_when_opted_in_and_always_labelled(rg, graph4):
    refuse = lambda p: {"answerable": False, "claims": []}  # noqa: E731
    off = ScriptedLLM(answer=refuse)
    r0 = answerer(rg, graph4, off).answer("what is a convolutional neural network")
    assert r0.outside_knowledge == [] and "outside" not in off.calls
    on = ScriptedLLM(answer=refuse, outside=lambda p: {"answer": "A CNN uses learned convolution filters."})
    r1 = answerer(rg, graph4, on).answer("what is a convolutional neural network", allow_outside_knowledge=True)
    assert r1.status == AnswerStatus.REFUSED and r1.claims == [] and r1.sources == []
    assert r1.outside_knowledge == ["A CNN uses learned convolution filters."] and "NOT from your material" in r1.message


def test_llm_failure_degrades_to_extractive_not_an_error(rg, graph4):
    def boom(prompt):
        raise LLMError("quota exceeded")
    r = answerer(rg, graph4, ScriptedLLM(answer=boom)).answer("what is the chain rule")
    assert r.status == AnswerStatus.GROUNDED and r.mode == "extractive" and "unavailable" in r.message


def test_malformed_llm_answer_degrades_too(rg, graph4):
    r = answerer(rg, graph4, ScriptedLLM(answer=lambda p: ["not", "an", "object"])).answer("what is the chain rule")
    assert r.mode == "extractive"


def test_malformed_claims_field_degrades_to_source_excerpts(rg, graph4):
    llm = ScriptedLLM(answer=lambda _: {"answerable": True, "claims": 1})
    r = answerer(rg, graph4, llm).answer("what is the chain rule")
    assert r.mode == "extractive" and r.sources


def test_all_claims_unsupported_means_refusal_not_a_confident_answer(rg, graph4):
    bad = lambda p: {"answerable": True, "claims": [{"text": "Bananas are yellow.", "unit_ids": ["sl-08"]}]}  # noqa: E731
    r = answerer(rg, graph4, ScriptedLLM(answer=bad)).answer("what is the chain rule")
    assert r.status == AnswerStatus.REFUSED and r.claims == []


def test_student_context_reaches_prompt_but_not_claims(rg, graph4):
    seen = {}
    def ans(prompt):
        seen["p"] = prompt
        return good_answer(prompt)
    answerer(rg, graph4, ScriptedLLM(answer=ans)).answer("what is the chain rule", student_context="weak on derivatives")
    assert "weak on derivatives" in seen["p"] and "add no facts" in seen["p"]


# ---- follow-ups ------------------------------------------------------------------------------
def test_followup_is_rewritten_with_llm(rg, graph4):
    llm = ScriptedLLM(answer=good_answer, standalone=lambda p: {"question": "what is the chain rule"})
    hist = [{"role": "user", "content": "what is the chain rule"}, {"role": "assistant", "content": "It differentiates compositions."}]
    r = answerer(rg, graph4, llm).answer("why is it useful?", history=hist)
    assert r.standalone_question == "what is the chain rule" and r.status == AnswerStatus.GROUNDED


def test_followup_without_llm_keeps_topic_words(rg, graph4):
    hist = [{"role": "user", "content": "explain gradient descent"}, {"role": "assistant", "content": "ok"}]
    r = answerer(rg, graph4).answer("and the learning rate?", history=hist)
    assert "gradient descent" in r.standalone_question and r.status == AnswerStatus.GROUNDED


def test_source_filter_applies_to_citations(rg, graph4):
    r = answerer(rg, graph4).answer("what is gradient descent", source_types=["pdf"])
    assert r.sources and all(s.location.page is not None for s in r.sources)


# ---- API ----------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client(rg, graph4):
    store = CorpusStore.from_json()
    return TestClient(create_app(store, rg, KnowledgeGraph.load(DEFAULT_GRAPH), answerer(rg, graph4)))


def test_ask_endpoint(client):
    r = client.post("/pod-b/ask", json={"question": "what is the chain rule"}).json()
    assert r["status"] == "grounded" and r["mode"] == "extractive" and r["sources"][0]["open_url"].startswith("/sources/")
    off = client.post("/pod-b/ask", json={"question": "how do vaccines work"}).json()
    assert off["status"] == "refused" and off["sources"] == []


def test_ask_validation(client):
    assert client.post("/pod-b/ask", json={"question": ""}).status_code == 422
    assert client.post("/pod-b/ask", json={"question": "x", "source_types": ["audio"]}).status_code == 422
    assert client.post("/pod-b/ask", json={"question": "x", "history": [{"role": "system", "content": "y"}]}).status_code == 422


def test_ask_info_reports_mode_and_calibration(client):
    i = client.get("/pod-b/ask/info").json()
    assert i["mode"] == "extractive" and i["threshold_in_use"] == STRICT and i["calibrated"] is False


def test_near_miss_constant_is_what_eval_scripts_use():
    assert len(NEAR_MISS) == 4


# ---- near-miss flagging: an unfamiliar term attached to a concept the course does cover --------------
@pytest.mark.parametrize("q,terms", [
    ("what is a convolutional neural network", ["convolutional"]),
    ("what is the derivative of sin x", ["sin"]),
])
def test_unseen_qualifier_detected(rg, graph4, q, terms):
    assert answerer(rg, graph4).unseen_qualifiers(q) == terms


def test_no_in_scope_golden_query_is_flagged(rg, graph4):
    a = answerer(rg, graph4)
    assert [q for q, _ in LEXICAL + SEMANTIC if a.unseen_qualifiers(q)] == []  # tuned on this set: optimistic


def test_free_floating_unfamiliar_words_and_generic_verbs_are_not_flagged(rg, graph4):
    a = answerer(rg, graph4)
    assert a.unseen_qualifiers("why does my training loss blow up") == []  # student's own phrasing
    assert a.unseen_qualifiers("how does learning rate affect convergence") == []  # 'affect' is a generic verb
    assert a.unseen_qualifiers("why do we need activation functions") == []


def test_no_graph_means_no_flags(rg):
    assert answerer(rg, None).unseen_qualifiers("what is a convolutional neural network") == []


def test_extractive_near_miss_is_partial_with_explanation_not_grounded(rg, graph4):
    r = answerer(rg, graph4).answer("what is a convolutional neural network")
    assert r.status == AnswerStatus.PARTIAL and r.mode == "extractive"
    assert "'convolutional'" in r.message and "neural network" in r.message
    assert r.sources and all(c.supported for c in r.claims)  # excerpts are real; only the fit is in doubt


def test_every_near_miss_query_is_not_confidently_grounded_even_without_an_llm(rg, graph4):
    for q in NEAR_MISS:
        assert answerer(rg, graph4).answer(q).status != AnswerStatus.GROUNDED, q


def test_generative_prompt_carries_the_coverage_note_and_status_is_capped_at_partial(rg, graph4):
    seen = {}
    def ans(prompt):
        seen["p"] = prompt
        return {"answerable": True, "claims": [{
            "text": "A neural network is built from layers of neurons computing weighted sums plus a bias.",
            "unit_ids": ["sl-19"]}]}
    r = answerer(rg, graph4, ScriptedLLM(answer=ans)).answer("what is a convolutional neural network")
    assert "Coverage note" in seen["p"] and "'convolutional'" in seen["p"]
    assert r.status == AnswerStatus.PARTIAL and "doesn't appear in your course material" in r.message


def test_unflagged_question_gets_no_coverage_note(rg, graph4):
    seen = {}
    def ans(prompt):
        seen["p"] = prompt
        return good_answer(prompt)
    answerer(rg, graph4, ScriptedLLM(answer=ans)).answer("what is the chain rule")
    assert "Coverage note" not in seen["p"]


def test_llm_outage_on_a_flagged_question_keeps_both_messages(rg, graph4):
    def boom(prompt):
        raise LLMError("quota")
    r = answerer(rg, graph4, ScriptedLLM(answer=boom)).answer("what is a convolutional neural network")
    assert r.status == AnswerStatus.PARTIAL and "unavailable" in r.message and "'convolutional'" in r.message
