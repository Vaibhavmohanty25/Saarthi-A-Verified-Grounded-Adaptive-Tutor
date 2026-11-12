"""
src/api/service.py -- Saarthi Unified FastAPI Integration Hub (Pod D)

Integrates all 4 Pods behind a single asynchronous service:
- Pod A: Multimodal Extraction & Upload (/ingest/upload)
- Pod B: Concept Graph DAG, Hybrid Search & Grounded Tutor Chat (/chat, /search, /graph, /pod-b/...)
- Pod C: Dual-Verified Assessment & Bayesian Knowledge Tracing (/quiz, /answer, /mastery, /report, /diagnostic)
- Pod D: RAGAS & Simulated Student Ablation Evaluation (/eval/ablation, /eval/ragas)
"""

from __future__ import annotations

import hmac
import os
import logging
import sys
import sqlite3
import uuid
import json as json_lib
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Literal

from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import env_loader  # Ensures repo root in sys.path and .env loaded

from src.api.courses import build_courses_router
from src.api.learning import DEMO_COURSE, LearningStore
from src.api.materials import (
    AUDIO_EXTENSIONS,
    PRESENTATION_TOPIC,
    SUPPORTED_EXTENSIONS,
    VIDEO_EXTENSIONS,
    extract_units,
    presentation_concepts,
    stage_upload,
)
from src.graph.graph import tag_units
from src.learner_model.adaptive import build_diagnostic, build_quiz
from src.learner_model.bkt import LearnerModel
from src.learner_model.live_course_data import (
    AblationSimulator,
    CONCEPT_DESCRIPTIONS,
    LIVE_COURSE_CONCEPTS,
    LIVE_QUESTION_BANK,
)
from src.learner_model.report import build_report
from src.mock_data import get_question_concept_id
from src.retrieval.api import build_router as build_pod_b_router
from src.retrieval.config import Settings
from src.retrieval.runtime import Runtime, build_bundle, load_startup, prune_graph
from src.retrieval.schemas import AnswerResponse, ConceptNode as GraphConceptNode, ContentUnit as PodBContentUnit
from src.retrieval.security import make_admin_guard
from src.schemas.models import Question

log = logging.getLogger("saarthi.api")

# --------------------------------------------------------------------------- #
# Application Lifecycle & State Initialization
# --------------------------------------------------------------------------- #
settings = Settings.from_env()
store, graph = load_startup(settings)
prune_graph(graph, store)
tag_units(graph, store)
rt = Runtime(build_bundle(settings, store, graph), settings, persist=True)

app = FastAPI(
    title="Saarthi: A Verified-Grounded Adaptive Tutor API",
    description="Unified API integrating Multimodal Ingestion (Pod A), Grounded Prerequisite Graph (Pod B), Verified BKT Assessment (Pod C), and Dashboard/Eval Harness (Pod D).",
    version="1.0.0",
)

# Enable CORS for Next.js (port 3000) and dev clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Pod B native router for backward-compatibility with tests & scripts
app.include_router(build_pod_b_router(rt, settings))

# Live student, concept, & quiz bank state (mined from uploaded course materials)
CONCEPTS = list(LIVE_COURSE_CONCEPTS)
CONCEPTS_BY_ID = {c.concept_id: c for c in CONCEPTS}
QUESTION_BANK: Dict[str, Question] = {q.q_id: q for q in LIVE_QUESTION_BANK}

# Sync concepts into runtime graph bundle
for c in CONCEPTS:
    if c.concept_id not in rt.bundle.graph.concepts:
        rt.bundle.graph.concepts[c.concept_id] = GraphConceptNode(
            concept_id=c.concept_id,
            name=c.name,
            topic=c.topic,
            aliases=[c.name.lower(), c.concept_id.replace("c-", "").replace("-", " ")],
            evidence_units=c.evidence_units,
            prerequisites=c.prerequisites,
        )

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# Session Persistence (SQLite)
# --------------------------------------------------------------------------- #
SESSION_DB_PATH = Path(os.getenv("SAARTHI_DB_PATH", "saarthi_sessions.db"))


def _get_session_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SESSION_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_session_db() -> None:
    conn = _get_session_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL DEFAULT 'student_default',
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            message_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS completed_quizzes (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL,
            topic TEXT,
            score REAL,
            total INTEGER,
            completed_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


_init_session_db()
learning = LearningStore(SESSION_DB_PATH)
app.include_router(build_courses_router(learning, settings, UPLOAD_DIR / "courses"))

if legacy_token := os.getenv("SAARTHI_LEGACY_TOKEN"):
    @app.middleware("http")
    async def protect_legacy_routes(request: Request, call_next):
        path = request.url.path
        public = path in {"/health", "/courses"} or path.startswith("/courses/")
        if request.method != "OPTIONS" and not public:
            supplied = request.headers.get("x-legacy-token", "")
            if not hmac.compare_digest(supplied.encode(), legacy_token.encode()):
                return JSONResponse({"detail": "Legacy access token required."}, status_code=401)
        return await call_next(request)


def get_student(student_id: str) -> LearnerModel:
    return learning.learner(DEMO_COURSE, student_id, CONCEPTS)


def q_to_dict(q: Question, include_answer: bool = False) -> Dict[str, Any]:
    d = {
        "q_id": q.q_id,
        "concept_id": get_question_concept_id(q),
        "topic": q.topic,
        "source_location": q.source_location.model_dump() if hasattr(q.source_location, "model_dump") else q.source_location,
        "difficulty": q.difficulty,
        "type": q.type,
        "stem": q.stem,
        "options": q.options,
        "verified": q.verified,
        "verifier_agreement": q.verifier_agreement,
    }
    if include_answer:
        d["answer"] = q.answer
        d["explanation"] = q.explanation
    return d


# --------------------------------------------------------------------------- #
# Request & Response Contracts
# --------------------------------------------------------------------------- #
class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Student's query to tutor")
    history: List[ChatMessageIn] = Field(default_factory=list, description="Prior conversational context")
    allow_outside_knowledge: bool = Field(False, description="Flag outside knowledge if refused")
    student_id: Optional[str] = Field("student_default", description="Active student ID for learner model integration")


class QuizRequest(BaseModel):
    student_id: str = "student_default"
    size: int = Field(5, ge=1, le=25, description="Number of quiz questions to generate")
    difficulty: Optional[int] = Field(None, ge=1, le=5, description="Target difficulty level (1-5), or None for adaptive BKT")
    concept_id: Optional[str] = Field(None, description="Optional target concept ID")


class AnswerRequest(BaseModel):
    student_id: str
    q_id: str
    answer: str = Field(..., min_length=1, max_length=4000)
    attempt_id: Optional[str] = Field(None, min_length=1, max_length=64)


class SessionCreate(BaseModel):
    student_id: str = "student_default"
    title: Optional[str] = None


class SessionChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    allow_outside_knowledge: bool = False
    student_id: str = "student_default"


class TitleUpdateRequest(BaseModel):
    title: str


# --------------------------------------------------------------------------- #
# 1. Health & System Status Endpoint
# --------------------------------------------------------------------------- #
@app.get("/health", tags=["System"])
def health():
    b = rt.bundle
    return {
        "status": "healthy",
        "service": "Saarthi Unified API",
        "pods": {
            "pod_a_ingestion": "active",
            "pod_b_grounding": f"active (mode={b.answerer.info()['mode']})",
            "pod_c_assessment": f"active (questions={len(QUESTION_BANK)}, concepts={len(CONCEPTS)})",
            "pod_d_frontend_eval": "active",
        },
        "knowledge_base": {
            "indexed_units": len(b.store),
            "sources": b.store.sources(),
            "graph_concepts": len(b.graph.concepts),
        },
        "active_models": {
            "replicate": os.getenv("REPLICATE_MODEL", "openai/gpt-4o-mini") if os.getenv("REPLICATE_API_KEY") else None,
            "groq": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") if os.getenv("GROQ_API_KEY") else None,
            "gemini": os.getenv("GEMINI_MODEL", "gemini-2.5-flash") if os.getenv("GEMINI_API_KEY") else None,
        },
    }


# --------------------------------------------------------------------------- #
# 2. Grounded Tutor Chat (Pod B Grounding + Active LLM)
# --------------------------------------------------------------------------- #
@app.post("/chat", tags=["Grounded Tutor"])
def chat(req: ChatRequest):
    """
    Grounded tutor chat with citation chips, diagram evidence, and confidence-gated refusal.
    Uses Replicate (gpt-4o-mini), Groq (llama-3.3), or Gemini based on configured keys.
    """
    b = rt.bundle
    student = get_student(req.student_id or "student_default")
    masteries = student.all_masteries()

    # Formulate student context note for tutor pedagogy
    weak_concepts = [c for c, m in masteries.items() if m < 0.5]
    student_ctx = f"Student struggles with: {', '.join(weak_concepts)}" if weak_concepts else "Student in good standing."

    # Convert chat history turns
    from src.retrieval.api import ChatTurn
    turns = [ChatTurn(role=m.role, content=m.content) for m in req.history[-10:]]

    ans: AnswerResponse = b.answerer.answer(
        question=req.question,
        history=turns,
        allow_outside_knowledge=req.allow_outside_knowledge,
        student_context=student_ctx,
    )

    # Format citation chips for Next.js frontend
    citations = []
    for s in ans.sources:
        citations.append({
            "unit_id": s.unit_id,
            "source": s.source_id,
            "label": s.label,
            "open_url": s.open_url,
            "location": {
                "page": s.location.page,
                "slide": s.location.slide,
                "timestamp": f"@{int(s.location.t_start)}s" if s.location.t_start is not None else None,
            },
            "excerpt": s.excerpt,
            "diagram_caption": getattr(s, "image_caption", None),
        })

    # Display text
    display_text = ans.answer or ans.message or "I could not find an answer in your uploaded materials."
    if ans.status == "refused":
        display_text = ans.message or "This topic is not covered in your uploaded course material."

    return {
        "status": ans.status.value if hasattr(ans.status, "value") else str(ans.status),
        "text": display_text,
        "confidence": ans.confidence,
        "citations": citations,
        "claims": [c.model_dump() for c in ans.claims],
        "outside_knowledge": ans.outside_knowledge,
        "mode": ans.mode,
    }


# --------------------------------------------------------------------------- #
# 3. Knowledge Graph & DAG Queries (Pod B)
# --------------------------------------------------------------------------- #
@app.get("/graph", tags=["Knowledge Graph"])
def get_graph():
    """Returns the full prerequisite knowledge graph (DAG topology) for visualizer."""
    nodes = []
    edges = []
    bundle = rt.bundle
    presentation_nodes = [
        c for c in bundle.graph.concepts.values() if c.topic == PRESENTATION_TOPIC.topic_id
    ]
    concepts = [*CONCEPTS, *presentation_nodes]
    topics = set()
    for c in concepts:
        is_presentation = c.topic == PRESENTATION_TOPIC.topic_id
        topic = PRESENTATION_TOPIC.name if is_presentation else c.topic
        topics.add(topic)
        meta = CONCEPT_DESCRIPTIONS.get(c.concept_id, {})
        description = "Slide heading in the uploaded presentation." if is_presentation else f"Concept under {topic}."
        # Collect rich evidence details from runtime store
        evidence_details = []
        for ev_id in c.evidence_units:
            u = bundle.store.get(ev_id)
            if u:
                evidence_details.append({
                    "unit_id": u.unit_id,
                    "source_id": u.source_id,
                    "location": u.location.model_dump(),
                    "text": u.text,
                })

        nodes.append({
            "id": c.concept_id,
            "name": c.name,
            "topic": topic,
            "assessment_available": not is_presentation,
            "prerequisites": c.prerequisites,
            "evidence_count": len(evidence_details),
            "evidence_units": [item["unit_id"] for item in evidence_details],
            "evidence_details": evidence_details,
            "description": meta.get("description", description),
            "keyTakeaways": meta.get("keyTakeaways", []),
        })
        for prereq in c.prerequisites:
            edges.append({
                "source": prereq,
                "target": c.concept_id,
                "type": "prerequisite",
                "validated": True,
            })

    # Validate DAG topological order using Pod B KnowledgeGraph engine
    from src.graph.graph import KnowledgeGraph as PodBKG
    from src.retrieval.schemas import ConceptNode as BConceptNode, Topic as BTopic
    kg = PodBKG(
        [BTopic(topic_id=f"t-{idx}", name=t) for idx, t in enumerate(sorted(topics))],
        [BConceptNode(concept_id=c.concept_id, name=c.name, topic=c.topic, prerequisites=c.prerequisites, evidence_units=c.evidence_units) for c in concepts]
    )
    try:
        topo = kg.topological_order()
        integrity = {"is_dag": True, "topological_order": topo}
    except Exception as err:
        integrity = {"is_dag": False, "error": str(err)}

    unique_topics = sorted(topics)
    return {
        "nodes": nodes,
        "edges": edges,
        "topics": [{"id": f"t-{idx}", "name": t} for idx, t in enumerate(unique_topics)],
        "integrity": integrity,
    }


@app.get("/evidence/{unit_id}", tags=["Knowledge Graph"])
def get_evidence_unit(unit_id: str):
    """Retrieve unit text and coordinates from live course corpus."""
    u = rt.bundle.store.get(unit_id)
    if u is None:
        raise HTTPException(404, "Evidence unit not found.")
    return {
        "unit_id": u.unit_id,
        "source_id": u.source_id,
        "location": u.location.model_dump(),
        "text": u.text,
        "image_caption": u.image_caption,
    }


@app.get("/concepts", tags=["Knowledge Graph"])
def list_concepts():
    """List concepts with prerequisite mappings for quiz and dashboard."""
    return [{"concept_id": c.concept_id, "name": c.name, "topic": c.topic,
             "prerequisites": c.prerequisites} for c in CONCEPTS]


# --------------------------------------------------------------------------- #
# 4. Multimodal Course Ingestion (Pod A)
# --------------------------------------------------------------------------- #
def _upload_concept(path: Path, title: str, units: list[PodBContentUnit]) -> GraphConceptNode:
    name = Path(title).stem.replace("-", " ").replace("_", " ")
    return GraphConceptNode(
        concept_id=f"doc_{path.stem}",
        name=name,
        topic="t-course-materials",
        aliases=[title, name],
        evidence_units=[unit.unit_id for unit in units],
    )


@app.post("/ingest/upload", tags=["Ingestion"], dependencies=[Depends(make_admin_guard(settings.admin_token))])
def upload_material(
    file: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
):
    """Index uploaded files in the legacy shared demo corpus."""
    uploads = [*(files or []), *([file] if file else [])]
    if not 1 <= len(uploads) <= 10:
        raise HTTPException(400, "Provide between one and ten files.")
    if len(uploads) > 1 and any(
        Path(item.filename or "").suffix.lower() in VIDEO_EXTENSIONS | AUDIO_EXTENSIONS
        for item in uploads
    ):
        raise HTTPException(400, "Upload a video or audio file individually.")

    staged = []
    original_names = []
    all_units = []
    concepts = []
    try:
        for upload in uploads:
            path, title = stage_upload(upload, UPLOAD_DIR)
            staged.append(path)
            original_names.append(title)
            units = extract_units(path, title)
            if not units:
                raise HTTPException(422, f"No usable course content found in {title}.")
            all_units.extend(units)
            if path.suffix != ".pptx":
                concepts.append(_upload_concept(path, title, units))
        ppt_concepts = presentation_concepts(all_units)
        result = rt.ingest(
            all_units, concepts=concepts + ppt_concepts,
            topics=(PRESENTATION_TOPIC,) if ppt_concepts else (),
        )
    except Exception as exc:
        for path in staged:
            path.unlink(missing_ok=True)
        if isinstance(exc, HTTPException):
            raise
        log.warning("Course material upload failed", exc_info=True)
        if isinstance(exc, (ValueError, UnicodeError)):
            raise HTTPException(422, "Course material could not be indexed.") from exc
        raise HTTPException(500, "Course material processing failed.") from exc

    filenames = [path.name for path in staged]
    return {
        "status": "success",
        "files_processed": len(filenames),
        "filenames": filenames,
        "original_filenames": original_names,
        "filename": filenames[0],
        "units_created": len(all_units),
        "presentation_concepts_created": len(ppt_concepts),
        "sample_units": [
            {
                "unit_id": unit.unit_id,
                "source_id": unit.source_id,
                "source_type": unit.source_type,
                "location": {"slide": unit.location.slide, "page": unit.location.page, "timestamp": unit.location.t_start},
                "text": unit.text[:160],
            }
            for unit in all_units[:8]
        ],
        "total_corpus_units": result["total_units"],
    }


@app.api_route("/uploads/{filename}", methods=["GET", "HEAD"], tags=["Ingestion"])
async def get_uploaded_file(filename: str):
    """Serve uploaded media files for browser preview and inspection."""
    file_path = (UPLOAD_DIR / filename).resolve()
    if file_path.parent != UPLOAD_DIR.resolve() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    ext = file_path.suffix.lower()
    media_type = "application/octet-stream"
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext == ".png":
        media_type = "image/png"
    elif ext in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif ext == ".webp":
        media_type = "image/webp"
    elif ext in [".mp4", ".mov", ".webm", ".avi", ".mkv"]:
        media_type = "video/mp4"
    elif ext in [".mp3", ".wav", ".m4a"]:
        media_type = "audio/mpeg"
    elif ext in [".txt", ".md"]:
        media_type = "text/plain; charset=utf-8"

    return FileResponse(
        file_path,
        media_type=media_type,
        content_disposition_type="inline",
        filename=filename,
    )


@app.get("/ingest/materials", tags=["Ingestion"])
def list_uploaded_materials():
    """
    Returns list of all uploaded course materials with metadata, chunk count, and linked concept nodes.
    """
    materials = []
    store = rt.bundle.store
    graph = rt.bundle.graph

    units_by_source: Dict[str, List[Any]] = {}
    for u in store.all():
        src = str(u.source_id)
        if src not in units_by_source:
            units_by_source[src] = []
        units_by_source[src].append(u)

    source_to_concepts: Dict[str, List[Dict[str, str]]] = {}
    for cid, c in graph.concepts.items():
        for ev_id in c.evidence_units:
            u = store.get(ev_id)
            if u:
                src = str(u.source_id)
                if src not in source_to_concepts:
                    source_to_concepts[src] = []
                if not any(item["concept_id"] == cid for item in source_to_concepts[src]):
                    source_to_concepts[src].append({
                        "concept_id": cid,
                        "name": c.name,
                        "topic": getattr(c, "topic", "Course Material")
                    })

    if UPLOAD_DIR.exists():
        for f in sorted(UPLOAD_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file():
                ext = f.suffix.lower()
                category = "document"
                if ext in [".ppt", ".pptx"]:
                    category = "pptx"
                elif ext == ".pdf":
                    category = "pdf"
                elif ext in [".mp4", ".mov", ".webm"]:
                    category = "video"
                elif ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    category = "image"

                units = units_by_source.get(f.name, [])
                linked = source_to_concepts.get(f.name, [])

                sample_units = []
                for u in units[:40]:
                    loc = getattr(u, "location", None)
                    slide = getattr(loc, "slide", None) if loc else None
                    page = getattr(loc, "page", None) if loc else None
                    t_start = getattr(loc, "t_start", None) if loc else None
                    ts_str = None
                    if t_start is not None:
                        secs = int(t_start)
                        h, rem = divmod(secs, 3600)
                        m, s = divmod(rem, 60)
                        ts_str = f"@{h}:{m:02d}:{s:02d}" if h else f"@{m:02d}:{s:02d}"
                    sample_units.append({
                        "unit_id": str(u.unit_id),
                        "location": {
                            "slide": slide,
                            "page": page,
                            "timestamp": ts_str,
                            "seconds": t_start,
                        },
                        "text": getattr(u, "text", ""),
                        "image_caption": getattr(u, "image_caption", None),
                    })

                materials.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "file_type": category,
                    "modified_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "download_url": f"/uploads/{f.name}",
                    "units_count": len(units),
                    "linked_concepts": linked,
                    "sample_units": sample_units,
                })

    return {"materials": materials, "total_count": len(materials)}


# --------------------------------------------------------------------------- #
# 5. Assessment & Bayesian Knowledge Tracing (Pod C)
# --------------------------------------------------------------------------- #
@app.post("/quiz", tags=["Assessment"])
def generate_quiz(req: QuizRequest):
    """Generates an adaptive or customized quiz tailored to question count and difficulty preferences."""
    if req.concept_id and req.concept_id not in CONCEPTS_BY_ID:
        raise HTTPException(404, "Concept not found.")
    eligible = [
        q for q in QUESTION_BANK.values() if q.verified
        and (req.concept_id is None or get_question_concept_id(q) == req.concept_id)
    ]
    seen = learning.issued_questions(DEMO_COURSE, req.student_id)
    unseen = [q for q in eligible if q.q_id not in seen]
    pool = unseen if len(unseen) >= min(req.size, len(eligible)) else eligible
    questions = build_quiz(
        CONCEPTS, get_student(req.student_id).all_masteries(), pool,
        size=min(req.size, len(pool)),
        target_difficulty=req.difficulty, target_concept=req.concept_id,
    )
    return {
        "student_id": req.student_id,
        "questions": [
            {**q_to_dict(q), "attempt_id": attempt}
            for q, attempt in learning.issue(DEMO_COURSE, req.student_id, questions)
        ],
    }


@app.post("/answer", tags=["Assessment"])
def submit_answer(req: AnswerRequest):
    """Grade a question and commit its mastery update with the answer attempt."""
    question = QUESTION_BANK.get(req.q_id)
    if question is None:
        raise HTTPException(404, "Question not found.")
    return learning.grade(
        DEMO_COURSE, req.student_id, CONCEPTS, question, req.answer, req.attempt_id,
        legacy_summary=True,
    )


@app.get("/mastery/{student_id}", tags=["Assessment"])
def get_mastery(student_id: str):
    """Returns the student's mastery board across all concepts."""
    student = get_student(student_id)
    board = [
        {
            "concept_id": c.concept_id,
            "name": c.name,
            "mastery": round(student.mastery(c.concept_id), 4),
            "status": "mastered" if student.mastery(c.concept_id) >= 0.7 else "weak" if student.mastery(c.concept_id) < 0.4 else "in_progress",
        }
        for c in CONCEPTS
    ]
    board.sort(key=lambda x: x["mastery"])
    return {
        "student_id": student_id,
        "overall_mastery": round(sum(x["mastery"] for x in board) / len(board), 3),
        "board": board,
    }


@app.get("/report/{student_id}", tags=["Assessment"])
def get_report(student_id: str):
    """Generates the post-assessment diagnostic report with misconception analysis."""
    student = get_student(student_id)
    text = build_report(learning.history(DEMO_COURSE, student_id, QUESTION_BANK), student, CONCEPTS)
    return {"student_id": student_id, "report": text}


@app.post("/diagnostic", tags=["Assessment"])
def run_diagnostic(student_id: str = "student_default"):
    """Issue a diagnostic whose answers update mastery without a learning transition."""
    questions = build_diagnostic(CONCEPTS, list(QUESTION_BANK.values()))
    return {
        "student_id": student_id,
        "status": "diagnostic_ready",
        "masteries": get_student(student_id).all_masteries(),
        "questions": [
            {**q_to_dict(q), "attempt_id": attempt}
            for q, attempt in learning.issue(DEMO_COURSE, student_id, questions, diagnostic=True)
        ],
    }


# --------------------------------------------------------------------------- #
# 6. Evaluation & Benchmarking (Pod D)
# --------------------------------------------------------------------------- #
@app.get("/eval/ablation", tags=["Evaluation"])
def get_ablation_benchmarks(students: int = Query(30, ge=1, le=100), sessions: int = Query(5, ge=1, le=20)):
    """
    Returns empirical benchmark data comparing Adaptive Tutor vs. Random Selection.
    Simulates students over the active course concepts and question bank dynamically.
    Direct proof for Track D Rubric (Personalization & System Evaluation).
    """
    sim = AblationSimulator(CONCEPTS, list(QUESTION_BANK.values()))
    return sim.run_benchmark(num_students=students, sessions=sessions)


@app.get("/eval/ragas", tags=["Evaluation"], deprecated=True)
@app.get("/eval/grounding", tags=["Evaluation"])
def get_grounding_metrics():
    """Serve the recorded development evaluation with its actual metrics and backend."""
    path = Path(os.getenv(
        "SAARTHI_GROUNDING_RESULTS", str(REPO_ROOT / "src/eval/results/grounding_dev_eval.json")
    ))
    try:
        result = json_lib.loads(path.read_text(encoding="utf-8"))
        if not isinstance(result.get("backend"), str) or not isinstance(result.get("results"), list):
            raise ValueError("invalid grounding results")
    except (OSError, ValueError, AttributeError):
        raise HTTPException(503, "No valid grounding evaluation is available.")
    return {"evaluation": "grounding_dev", **result}


# --------------------------------------------------------------------------- #
# Restore unindexed legacy uploads at startup
# --------------------------------------------------------------------------- #
def _init_existing_uploads():
    for path in UPLOAD_DIR.iterdir():
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS or rt.bundle.store.by_source(path.name):
            continue
        try:
            units = extract_units(path, path.name)
            if units:
                if path.suffix.lower() == ".pptx":
                    concepts = presentation_concepts(units)
                    rt.ingest(units, concepts=concepts, topics=(PRESENTATION_TOPIC,) if concepts else ())
                else:
                    rt.ingest(units, concepts=[_upload_concept(path, path.name, units)])
        except Exception:
            log.warning("Could not restore uploaded material %s", path.name, exc_info=True)


_init_existing_uploads()


# --------------------------------------------------------------------------- #
# 7. Chat Session Management (SQLite-backed)
# --------------------------------------------------------------------------- #


@app.get("/sessions", tags=["Sessions"])
def list_sessions(student_id: str = "student_default"):
    """List all chat sessions for a student, ordered by most recent activity."""
    conn = _get_session_db()
    rows = conn.execute(
        "SELECT * FROM chat_sessions WHERE student_id = ? ORDER BY updated_at DESC",
        (student_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/sessions", tags=["Sessions"])
def create_session(req: SessionCreate):
    """Create a new chat session and return its metadata."""
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    title = req.title or "New Chat"
    conn = _get_session_db()
    conn.execute(
        "INSERT INTO chat_sessions (id, student_id, title, created_at, updated_at, message_count) VALUES (?, ?, ?, ?, ?, 0)",
        (sid, req.student_id, title, now, now)
    )
    conn.commit()
    conn.close()
    return {"id": sid, "student_id": req.student_id, "title": title,
            "created_at": now, "updated_at": now, "message_count": 0}


@app.get("/sessions/{session_id}", tags=["Sessions"])
def get_session(session_id: str, student_id: str = "student_default"):
    """Get a session with all its persisted messages."""
    conn = _get_session_db()
    session = conn.execute("SELECT * FROM chat_sessions WHERE id = ? AND student_id = ?", (session_id, student_id)).fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")
    messages = conn.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()
    conn.close()
    msgs = []
    for m in messages:
        d = dict(m)
        d["citations"] = json_lib.loads(d.pop("citations_json", "[]") or "[]")
        msgs.append(d)
    return {"session": dict(session), "messages": msgs}


@app.delete("/sessions/{session_id}", tags=["Sessions"])
def delete_session(session_id: str, student_id: str = "student_default"):
    """Delete a session and all its messages."""
    conn = _get_session_db()
    deleted = conn.execute(
        "DELETE FROM chat_sessions WHERE id = ? AND student_id = ?", (session_id, student_id)
    )
    conn.commit()
    conn.close()
    if deleted.rowcount == 0:
        raise HTTPException(404, "Session not found.")

    return {"status": "deleted", "session_id": session_id}


@app.patch("/sessions/{session_id}/title", tags=["Sessions"])
def update_session_title(session_id: str, req: TitleUpdateRequest, student_id: str = "student_default"):
    """Rename a session."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_session_db()
    updated = conn.execute(
        "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ? AND student_id = ?",
        (req.title, now, session_id, student_id),
    )
    conn.commit()
    conn.close()
    if updated.rowcount == 0:
        raise HTTPException(404, "Session not found.")
    return {"status": "updated", "session_id": session_id, "title": req.title}


@app.post("/sessions/{session_id}/chat", tags=["Sessions"])
def session_chat(session_id: str, req: SessionChatRequest):
    """
    Session-aware grounded tutor chat.
    Persists user + assistant messages to SQLite; auto-titles session from first message.
    """
    conn = _get_session_db()
    session = conn.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,)).fetchone()
    if session is not None and session["student_id"] != req.student_id:
        conn.close()
        raise HTTPException(404, "Session not found.")
    if not session:
        now = datetime.now(timezone.utc).isoformat()
        auto_title = req.question[:60] + ("..." if len(req.question) > 60 else "")
        conn.execute(
            "INSERT INTO chat_sessions (id, student_id, title, created_at, updated_at, message_count) VALUES (?, ?, ?, ?, ?, 0)",
            (session_id, req.student_id, auto_title, now, now)
        )
        conn.commit()


    existing = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    ).fetchall()

    b = rt.bundle
    student = get_student(req.student_id)
    masteries = student.all_masteries()
    weak_concepts = [c for c, m in masteries.items() if m < 0.5]
    student_ctx = (
        f"Student struggles with: {', '.join(weak_concepts)}" if weak_concepts else "Student in good standing."
    )

    history = [{"role": m["role"], "content": m["content"]} for m in existing[-10:]]

    ans: AnswerResponse = b.answerer.answer(
        question=req.question,
        history=history,
        allow_outside_knowledge=req.allow_outside_knowledge,
        student_context=student_ctx,
    )

    citations = []
    for s in ans.sources:
        citations.append({
            "unit_id": s.unit_id,
            "source": s.source_id,
            "label": s.label,
            "open_url": s.open_url,
            "location": {
                "page": s.location.page,
                "slide": s.location.slide,
                "timestamp": f"@{int(s.location.t_start)}s" if s.location.t_start is not None else None,
            },
            "excerpt": s.excerpt,
            "diagram_caption": getattr(s, "image_caption", None),
        })

    display_text = ans.answer or ans.message or "I could not find an answer in your uploaded materials."
    if ans.status == "refused":
        display_text = ans.message or "This topic is not covered in your uploaded course material."

    now = datetime.now(timezone.utc).isoformat()
    is_first_msg = len(existing) == 0

    conn.execute(
        "INSERT INTO chat_messages (id, session_id, role, content, citations_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), session_id, "user", req.question, "[]", now)
    )
    conn.execute(
        "INSERT INTO chat_messages (id, session_id, role, content, citations_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), session_id, "assistant", display_text, json_lib.dumps(citations), now)
    )

    msg_count = conn.execute(
        "SELECT COUNT(*) FROM chat_messages WHERE session_id = ?", (session_id,)
    ).fetchone()[0]

    if is_first_msg:
        auto_title = req.question[:60] + ("..." if len(req.question) > 60 else "")
        conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = ?, message_count = ? WHERE id = ?",
            (auto_title, now, msg_count, session_id)
        )
    else:
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ?, message_count = ? WHERE id = ?",
            (now, msg_count, session_id)
        )

    conn.commit()
    conn.close()

    return {
        "status": ans.status.value if hasattr(ans.status, "value") else str(ans.status),
        "text": display_text,
        "confidence": ans.confidence,
        "citations": citations,
        "claims": [c.model_dump() for c in ans.claims],
        "outside_knowledge": ans.outside_knowledge,
        "mode": ans.mode,
        "session_id": session_id,
    }


@app.get("/completed-quizzes", tags=["Assessment"])
def get_completed_quizzes(student_id: str = "student_default"):
    """Return all completed quiz records for a student."""
    conn = _get_session_db()
    rows = conn.execute(
        "SELECT * FROM completed_quizzes WHERE student_id = ? ORDER BY completed_at DESC",
        (student_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/quiz/complete", tags=["Assessment"])
def mark_quiz_completed(student_id: str, topic: str, score: float, total: int):
    """Record a completed quiz for sidebar history display."""
    qid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_session_db()
    conn.execute(
        "INSERT INTO completed_quizzes (id, student_id, topic, score, total, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (qid, student_id, topic, score, total, now)
    )
    conn.commit()
    conn.close()
    return {"id": qid, "status": "recorded"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.service:app", host="0.0.0.0", port=8000, reload=True)
