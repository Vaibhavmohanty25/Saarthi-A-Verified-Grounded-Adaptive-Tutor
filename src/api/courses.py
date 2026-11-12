"""Private uploaded courses, with a persisted build job and a scoped tutor."""

import hashlib
import hmac
import json
import logging
import secrets
import time
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.api.materials import extract_units, stage_upload
from src.assessment.course_bank import build_course_questions
from src.graph.graph import KnowledgeGraph
from src.graph.graph_builder import GraphBuilder
from src.learner_model.adaptive import build_diagnostic, build_quiz
from src.mock_data import get_question_concept_id
from src.retrieval.api import ChatTurn
from src.retrieval.runtime import MAX_UNITS_PER_INGEST, build_bundle
from src.retrieval.schemas import ContentUnit, make_citation
from src.retrieval.security import make_admin_guard
from src.retrieval.store import CorpusStore
from src.schemas.models import Question

log = logging.getLogger(__name__)
BUILD_LEASE_SECONDS = 1800
bearer = HTTPBearer(auto_error=False)


class TutorRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=10)


class PracticeRequest(BaseModel):
    size: int = Field(default=5, ge=1, le=12)
    concept_id: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)


class Submission(BaseModel):
    q_id: str = Field(min_length=1, max_length=200)
    attempt_id: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=1, max_length=4000)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _status(row) -> dict:
    return {
        "course_id": row["id"], "status": row["status"], "filename": row["original_name"],
        "assessment_status": row["assessment_status"], "error": row["error"],
    }


def build_courses_router(learning, settings, uploads: Path):
    router = APIRouter(prefix="/courses", tags=["Uploaded Courses"])
    with closing(learning.connect()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS uploaded_courses (
                id TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                original_name TEXT NOT NULL,
                status TEXT NOT NULL,
                assessment_status TEXT,
                error TEXT,
                run_id TEXT,
                started REAL,
                snapshot TEXT
            )
        """)

    def find_course(course_id):
        with closing(learning.connect()) as conn:
            return conn.execute(
                """SELECT id, token_hash, stored_name, original_name, status, assessment_status, error, run_id, started
                   FROM uploaded_courses WHERE id = ?""",
                (course_id,),
            ).fetchone()

    def authorized(course_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise HTTPException(401, "Course bearer token required.", headers={"WWW-Authenticate": "Bearer"})
        row = find_course(course_id)
        if row is None or not hmac.compare_digest(row["token_hash"], _digest(credentials.credentials)):
            raise HTTPException(404, "Course not found.")
        return row

    @lru_cache(maxsize=8)
    def load_snapshot(course_id, run_id):
        with closing(learning.connect()) as conn:
            row = conn.execute(
                "SELECT snapshot FROM uploaded_courses WHERE id = ? AND run_id = ? AND status = 'ready'",
                (course_id, run_id),
            ).fetchone()
        if row is None:
            raise HTTPException(409, "Course is being rebuilt.")
        data = json.loads(row["snapshot"])
        store = CorpusStore(ContentUnit.model_validate(unit) for unit in data["units"])
        graph = KnowledgeGraph.from_dict(data["graph"])
        bank = {item["q_id"]: Question.model_validate(item) for item in data["questions"]}
        return build_bundle(settings, store, graph), bank

    def ready(row=Depends(authorized)):
        if row["status"] != "ready":
            raise HTTPException(409, "Course material has not finished building.")
        bundle, bank = load_snapshot(row["id"], row["run_id"])
        return row, bundle, bank

    def run_build(course_id):
        run_id = uuid4().hex
        with closing(learning.connect()) as conn, conn:
            updated = conn.execute(
                """UPDATE uploaded_courses SET status = 'running', run_id = ?, started = ?
                   WHERE id = ? AND status = 'queued'""",
                (run_id, time.time(), course_id),
            )
            if updated.rowcount == 0:
                return
        row = find_course(course_id)
        try:
            units = extract_units(uploads / row["stored_name"], row["original_name"])
            if not 1 <= len(units) <= MAX_UNITS_PER_INGEST:
                raise ValueError("Course material must have between 1 and 2000 usable content units.")
            store = CorpusStore(units)
            from src.retrieval.llm import make_llm

            llm, _ = make_llm(settings)
            if llm is None:
                raise ValueError("Configure a text model provider for course graph construction.")
            graph = GraphBuilder(llm).build(store).graph
            bundle = build_bundle(settings, store, graph)
            try:
                questions = build_course_questions(bundle, settings)
                assessment_status = "ready" if questions else "no_verified_questions"
            except Exception:
                log.warning("Question verification failed for course %s", course_id, exc_info=True)
                questions, assessment_status = [], "provider_error"
            snapshot = json.dumps({
                "units": [unit.model_dump(exclude={"embedding"}) for unit in units],
                "graph": graph.to_dict(),
                "questions": [question.model_dump() for question in questions],
            })
            with closing(learning.connect()) as conn, conn:
                conn.execute(
                    """UPDATE uploaded_courses
                       SET status = 'ready', assessment_status = ?, snapshot = ?, error = NULL
                       WHERE id = ? AND run_id = ? AND status = 'running'""",
                    (assessment_status, snapshot, course_id, run_id),
                )
        except Exception:
            log.exception("Course build failed for %s", course_id)
            with closing(learning.connect()) as conn, conn:
                conn.execute(
                    """UPDATE uploaded_courses SET status = 'failed', error = ?
                       WHERE id = ? AND run_id = ? AND status = 'running'""",
                    ("Course build failed. Check the material and server provider configuration.", course_id, run_id),
                )

    @router.post("", status_code=202, dependencies=[Depends(make_admin_guard(settings.admin_token))])
    def create(background: BackgroundTasks, file: UploadFile = File(...)):
        path, name = stage_upload(file, uploads)
        course_id, token = uuid4().hex, secrets.token_urlsafe(32)
        try:
            with closing(learning.connect()) as conn, conn:
                conn.execute(
                    """INSERT INTO uploaded_courses (id, token_hash, stored_name, original_name, status)
                       VALUES (?, ?, ?, ?, 'queued')""",
                    (course_id, _digest(token), path.name, name),
                )
        except Exception:
            path.unlink(missing_ok=True)
            raise
        background.add_task(run_build, course_id)
        return {"course_id": course_id, "access_token": token, "status": "queued", "filename": name}

    @router.get("/{course_id}")
    def status(row=Depends(authorized)):
        return _status(row)

    @router.post("/{course_id}/retry", status_code=202)
    def retry(background: BackgroundTasks, row=Depends(authorized)):
        course_id = row["id"]
        with closing(learning.connect()) as conn, conn:
            updated = conn.execute(
                """UPDATE uploaded_courses SET status = 'queued', error = NULL, assessment_status = NULL
                   WHERE id = ? AND (
                       status IN ('failed', 'queued')
                       OR (status = 'running' AND started < ?)
                       OR (status = 'ready' AND assessment_status != 'ready')
                   )""",
                (course_id, time.time() - BUILD_LEASE_SECONDS),
            )
            if updated.rowcount == 0:
                raise HTTPException(409, "The course is ready or already being built.")
        background.add_task(run_build, course_id)
        return {"course_id": course_id, "status": "queued"}

    def citation(unit, course_id):
        source = make_citation(unit).model_dump()
        source["open_url"] = f"/courses/{course_id}/source" + (
            f"#page={unit.location.page}" if unit.location.page else
            f"#slide={unit.location.slide}" if unit.location.slide else
            f"#t={unit.location.t_start}"
        )
        return source

    @router.get("/{course_id}/source")
    def source(row=Depends(authorized)):
        path = uploads / row["stored_name"]
        if not path.is_file():
            raise HTTPException(404, "Course file not found.")
        return FileResponse(path, filename=row["original_name"], headers={"Cache-Control": "private, no-store"})

    @router.get("/{course_id}/evidence/{unit_id}")
    def evidence(unit_id: str, data=Depends(ready)):
        row, bundle, _ = data
        unit = bundle.store.get(unit_id)
        if unit is None:
            raise HTTPException(404, "Evidence unit not found.")
        return {**citation(unit, row["id"]), "text": unit.text, "image_caption": unit.image_caption}

    @router.post("/{course_id}/chat")
    def chat(request: TutorRequest, data=Depends(ready)):
        row, bundle, _ = data
        course_id = row["id"]
        student = learning.learner(course_id, course_id, bundle.graph.concepts.values())
        weak = [node.name for node in bundle.graph.concepts.values() if student.mastery(node.concept_id) < 0.5]
        answer = bundle.answerer.answer(
            question=request.question,
            history=request.history,
            student_context=f"Concepts to review: {', '.join(weak)}" if weak else "",
        )
        result = answer.model_dump()
        for source in result["sources"] + [
            source for claim in result["claims"] for source in claim["citations"]
        ]:
            source["open_url"] = citation(bundle.store.get(source["unit_id"]), course_id)["open_url"]
        return result

    @router.get("/{course_id}/graph")
    def graph(data=Depends(ready)):
        _, bundle, _ = data
        return {**bundle.graph.to_dict(), "topological_order": bundle.graph.topological_order()}

    def issue_questions(row, bundle, bank, request, *, diagnostic=False):
        course_id = row["id"]
        concepts = list(bundle.graph.concepts.values())
        if request.concept_id and request.concept_id not in bundle.graph.concepts:
            raise HTTPException(404, "Concept not found.")
        eligible = [
            question for question in bank.values()
            if request.concept_id is None or get_question_concept_id(question) == request.concept_id
        ]
        if not eligible:
            raise HTTPException(409, "No independently verified questions are available.")
        if diagnostic:
            questions = build_diagnostic(concepts, eligible, size=request.size)
        else:
            student = learning.learner(course_id, course_id, concepts)
            questions = build_quiz(
                concepts, student.all_masteries(), eligible, size=min(request.size, len(eligible)),
                target_concept=request.concept_id, target_difficulty=request.difficulty,
            )
        return {
            "course_id": course_id,
            "questions": [
                {
                    **question.model_dump(exclude={"answer", "explanation", "embedding"}),
                    "attempt_id": attempt,
                    "evidence_url": f"/courses/{course_id}/evidence/{question.source_unit_id}",
                }
                for question, attempt in learning.issue(course_id, course_id, questions, diagnostic=diagnostic)
            ],
        }

    @router.post("/{course_id}/quiz")
    def quiz(request: PracticeRequest, data=Depends(ready)):
        row, bundle, bank = data
        return issue_questions(row, bundle, bank, request)

    @router.post("/{course_id}/diagnostic")
    def diagnostic(data=Depends(ready)):
        row, bundle, bank = data
        return issue_questions(row, bundle, bank, PracticeRequest(size=8), diagnostic=True)

    @router.post("/{course_id}/answer")
    def answer(request: Submission, data=Depends(ready)):
        row, bundle, bank = data
        course_id = row["id"]
        question = bank.get(request.q_id)
        if question is None:
            raise HTTPException(404, "Question not found.")
        result = learning.grade(
            course_id, course_id, bundle.graph.concepts.values(), question, request.answer, request.attempt_id,
        )
        return {**result, "evidence_url": f"/courses/{course_id}/evidence/{question.source_unit_id}"}

    @router.get("/{course_id}/mastery")
    def mastery(data=Depends(ready)):
        row, bundle, _ = data
        course_id = row["id"]
        student = learning.learner(course_id, course_id, bundle.graph.concepts.values())
        return {"course_id": course_id, "mastery": student.all_masteries()}

    return router
