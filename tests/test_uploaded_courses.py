import importlib
import re
import sys
from io import BytesIO

import fitz
import pytest
from fastapi.testclient import TestClient
from pptx import Presentation

from src.graph.graph_builder import SYSTEM_A
from src.ingestion.processing.chunker import chunk_text
from src.schemas.models import Question, SourceLocation


class CourseGraphModel:
    name = "test-course-graph"

    def generate_json(self, system, prompt):
        if system == SYSTEM_A:
            unit_id = re.search(r"^\[([^\]]+)\]", prompt, re.MULTILINE).group(1)
            name = "evaporation" if "evaporation" in prompt.lower() else "methane"
            return {
                "concepts": [{"name": name, "definition": name, "aliases": [], "unit_ids": [unit_id]}],
            }
        return {}


def test_ingestion_chunker_stops_after_the_final_window():
    assert chunk_text("Evaporation changes a liquid to vapour.") == ["Evaporation changes a liquid to vapour."]
    text = "abcdefghijklmnopqrstuvwxyz"
    assert chunk_text(text, chunk_size=12, overlap=4) == ["abcdefghijkl", "ijklmnopqrst", "qrstuvwxyz"]


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hash")
    monkeypatch.setenv("RERANK_PROVIDER", "lexical")
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("POD_B_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAARTHI_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("POD_B_ADMIN_TOKEN", "test-admin")
    monkeypatch.delenv("SAARTHI_LEGACY_TOKEN", raising=False)
    name = "src.api.service"
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return importlib.import_module(name)


def _pdf(text):
    with fitz.open() as doc:
        doc.new_page().insert_text((60, 60), text)
        return doc.tobytes()


def test_shared_chat_refuses_missing_definition_and_preserves_source_scope(service):
    client = TestClient(service.app)
    headers = {"X-Admin-Token": "test-admin"}

    def upload(name, text):
        result = client.post("/ingest/upload", files={"file": (name, text)}, headers=headers)
        assert result.status_code == 200, result.text
        return result.json()["filename"]

    nlp = upload("NLP.txt", "The language model is conditioned on the retrieved passages.")
    session = client.post("/sessions", json={"student_id": "s1"}).json()
    path = f"/sessions/{session['id']}/chat"
    request = {"student_id": "s1", "question": "What is a race condition?"}
    unavailable = client.post(path, json=request).json()
    assert unavailable["status"] == "refused" and not unavailable["citations"]

    os_material = upload("Operating Systems.txt", "A race condition occurs when the outcome depends on the order of concurrent operations.")
    answer = client.post(path, json={**request, "source_ids": [os_material]}).json()
    assert answer["status"] == "grounded" and answer["mode"] == "extractive"
    assert [citation["source"] for citation in answer["citations"]] == [os_material]
    assert "Showing matching excerpts" in answer["text"]

    same_question_wrong_source = client.post("/chat", json={**request, "source_ids": [nlp]}).json()
    assert same_question_wrong_source["status"] == "refused" and not same_question_wrong_source["citations"]
    assert client.post("/chat", json={"question": "   "}).status_code == 422

    history = client.get(f"/sessions/{session['id']}", params={"student_id": "s1"}).json()
    assert history["session"]["message_count"] == 4
    assert [item["role"] for item in history["messages"]] == ["user", "assistant", "user", "assistant"]
    assert history["messages"][-1]["citations"] == answer["citations"]
    assert client.post(path, json={**request, "student_id": "s2"}).status_code == 404


def test_powerpoint_upload_populates_the_graph_with_cited_headings(service, monkeypatch):
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "REPLICATE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    presentation = Presentation()
    for title, body in [
        ("Agenda", "What we will cover"),
        ("Critical Section", "Only one process may execute this section at a time."),
        ("Semaphores", "A semaphore controls access to shared resources."),
        ("Critical Section", "Mutual exclusion protects the shared state."),
    ]:
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = body
    deck = BytesIO()
    presentation.save(deck)

    client = TestClient(service.app)
    headers = {"X-Admin-Token": "test-admin"}
    legacy = client.post("/ingest/upload", files={"file": ("legacy.ppt", b"legacy")}, headers=headers)
    assert legacy.status_code == 415
    assert "PowerPoint Presentation (.pptx)" in legacy.json()["detail"]

    # Older versions could leave unsupported uploads on disk.
    legacy_filename = "Legacy slides #3.ppt"
    (service.UPLOAD_DIR / legacy_filename).write_bytes(b"legacy")
    response = client.post("/ingest/upload", files={"file": ("Operating Systems.pptx", deck.getvalue())}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["presentation_concepts_created"] == 2

    restarted = TestClient(importlib.reload(service).app)
    materials = {item["filename"]: item for item in restarted.get("/ingest/materials").json()["materials"]}
    legacy_material = materials[legacy_filename]
    assert legacy_material["file_type"] == "ppt"
    assert legacy_material["units_count"] == 0
    assert legacy_material["linked_concepts"] == []
    assert restarted.get(legacy_material["download_url"]).content == b"legacy"
    assert materials[response.json()["filename"]]["file_type"] == "pptx"
    graph = restarted.get("/graph").json()
    nodes = {node["name"]: node for node in graph["nodes"] if node["topic"] == "Uploaded presentations"}
    assert set(nodes) == {"Critical Section", "Semaphores"}
    assert {item["location"]["slide"] for item in nodes["Critical Section"]["evidence_details"]} == {2, 4}
    assert not nodes["Semaphores"]["prerequisites"]
    assert not nodes["Semaphores"]["assessment_available"]
    assert nodes["Semaphores"]["id"] in graph["integrity"]["topological_order"]
    answer = restarted.post("/chat", json={
        "question": "What is a critical section?",
        "source_ids": [response.json()["filename"]],
    }).json()
    assert answer["status"] == "grounded"
    assert answer["citations"][0]["location"]["slide"] in {2, 4}


def _verified_fixture_question(bundle, settings):
    concept = next(iter(bundle.graph.concepts.values()))
    evidence = bundle.store.get(concept.evidence_units[0])
    return [Question(
        q_id="q-test",
        concept_id=concept.concept_id,
        topic=concept.topic,
        source_unit_id=evidence.unit_id,
        source_location=SourceLocation(page=1),
        difficulty=2,
        type="mcq",
        stem=f"Which concept is covered? ({concept.name})",
        options=[concept.name, "snow", "coal", "iron"],
        answer=concept.name,
        explanation=evidence.text,
        verified=True,
        verifier_agreement=1,
    )]


def _create_course(client, filename, text):
    response = client.post(
        "/courses",
        files={"file": (filename, _pdf(text), "application/pdf")},
        headers={"X-Admin-Token": "test-admin"},
    )
    assert response.status_code == 202, response.text
    data = response.json()
    return f"/courses/{data['course_id']}", {"Authorization": f"Bearer {data['access_token']}"}


def test_upload_powers_chat_graph_verified_quiz_and_durable_mastery(service, monkeypatch):
    monkeypatch.setattr("src.retrieval.llm.make_llm", lambda settings: (CourseGraphModel(), "test"))
    monkeypatch.setattr("src.api.courses.build_course_questions", _verified_fixture_question)
    client = TestClient(service.app)
    path, headers = _create_course(
        client, "water.pdf", "Evaporation is the process where liquid water becomes water vapour.",
    )
    other_path, other_headers = _create_course(client, "water.pdf", "Methane is an alkane and a greenhouse gas.")

    assert client.get(path).status_code == 401
    assert client.get(path, headers=other_headers).status_code == 404
    assert client.get(other_path, headers=headers).status_code == 404
    status = client.get(path, headers=headers).json()
    assert status["status"] == status["assessment_status"] == "ready"
    assert status["filename"] == "water.pdf"

    graph = client.get(f"{path}/graph", headers=headers).json()
    concept = graph["concepts"][0]
    assert graph["topological_order"] == ["c-evaporation"]
    evidence_id = concept["evidence_units"][0]
    chat = client.post(f"{path}/chat", headers=headers, json={"question": "What is evaporation?"}).json()
    assert chat["status"] == "grounded"
    assert chat["sources"][0]["unit_id"] == evidence_id
    assert chat["sources"][0]["open_url"] == f"{path}/source#page=1"

    quiz = client.post(f"{path}/quiz", headers=headers, json={"size": 5}).json()
    assert len(quiz["questions"]) == 1
    question = quiz["questions"][0]
    assert question["verified"] and "answer" not in question
    assert question["source_unit_id"] == evidence_id
    citation = client.get(question["evidence_url"], headers=headers).json()
    assert citation["location"]["page"] == 1 and "water vapour" in citation["text"]
    assert client.get(f"{path}/evidence/unknown", headers=headers).status_code == 404

    submission = {"q_id": question["q_id"], "attempt_id": question["attempt_id"], "answer": "evaporation"}
    grade = client.post(f"{path}/answer", headers=headers, json=submission).json()
    assert grade["correct"] and grade["new_mastery"] > 0.3
    assert client.post(f"{path}/answer", headers=headers, json=submission).json() == grade
    assert client.post(f"{path}/answer", headers=headers, json={**submission, "answer": "snow"}).status_code == 409
    assert client.post(f"{other_path}/answer", headers=other_headers, json=submission).status_code == 404

    restarted = TestClient(importlib.reload(service).app)
    persisted = restarted.get(f"{path}/mastery", headers=headers).json()["mastery"]
    assert persisted["c-evaporation"] == pytest.approx(grade["new_mastery"], abs=0.00005)
    assert restarted.get(f"{other_path}/mastery", headers=other_headers).json()["mastery"] == {"c-methane": 0.3}
    assert restarted.post(f"{path}/answer", headers=headers, json=submission).json() == grade


def test_upload_validation_and_recoverable_failed_build(service, monkeypatch):
    client = TestClient(service.app)
    admin = {"X-Admin-Token": "test-admin"}
    bad = {"file": ("fake.pdf", b"not a pdf", "application/pdf")}
    assert client.post("/courses", files=bad).status_code == 401
    assert client.post("/courses", files=bad, headers=admin).status_code == 415
    monkeypatch.setenv("SAARTHI_MAX_UPLOAD_BYTES", "4")
    assert client.post("/courses", files=bad, headers=admin).status_code == 413
    assert list((service.UPLOAD_DIR / "courses").iterdir()) == []
    monkeypatch.delenv("SAARTHI_MAX_UPLOAD_BYTES")

    path, headers = _create_course(client, "../lecture.pdf", "Evaporation happens at the surface of a liquid.")
    status = client.get(path, headers=headers).json()
    assert status["status"] == "failed"
    assert status["filename"] == "lecture.pdf"
    assert not (service.UPLOAD_DIR.parent / "lecture.pdf").exists()
    assert client.get(f"{path}/graph", headers=headers).status_code == 409
    monkeypatch.setattr("src.retrieval.llm.make_llm", lambda settings: (CourseGraphModel(), "test"))
    assert client.post(f"{path}/retry", headers=headers).status_code == 202
    assert client.get(path, headers=headers).json()["status"] == "ready"
    assert client.post(f"{path}/quiz", headers=headers, json={}).status_code == 409


def test_demo_diagnostic_uses_observed_answers_and_reports_recorded_metrics(service):
    client = TestClient(service.app)
    data = client.post("/diagnostic", params={"student_id": "demo-learner"}).json()
    assert data["status"] == "diagnostic_ready"
    item = data["questions"][0]
    answer = service.QUESTION_BANK[item["q_id"]].answer
    submission = {"student_id": "demo-learner", "q_id": item["q_id"], "attempt_id": item["attempt_id"], "answer": answer}
    grade = client.post("/answer", json=submission).json()
    assert grade["correct"] and grade["new_mastery"] == pytest.approx(0.6585, abs=0.0001)
    assert client.post("/answer", json=submission).json() == grade
    assert "1/1 correct" in client.get("/report/demo-learner").json()["report"]
    assert client.get("/evidence/missing").status_code == 404
    result = client.get("/eval/grounding").json()
    assert result["evaluation"] == "grounding_dev"
    assert result["results"][0]["n_in_scope"] > 0
