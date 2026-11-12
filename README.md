# Saarthi: A Verified-Grounded Adaptive Tutor
> **Multimodal AI Study Companion · Grounded Retrieval · Prerequisite DAGs · Bayesian Knowledge Tracing**

Saarthi is an AI study companion that ingests multimodal course materials (textbooks, slides, lecture videos), constructs an evidence-grounded prerequisite knowledge graph, generates independently-verified assessment items, and personalizes the student's learning journey using Bayesian Knowledge Tracing (BKT).

---

## 🌟 What is Saarthi?

Traditional educational chatbots frequently suffer from hallucinations, lack pedagogical structure, and cannot verify whether a student has truly mastered foundational concepts before introducing advanced topics.

**Saarthi solves this through a 4-pod verified architecture:**
1. **Multimodal Grounding**: Ingests lecture slides (PPTX), textbooks (PDF), and video lectures, indexing each concept with verifiable slide numbers and timestamps.
2. **Prerequisite Knowledge Graph**: Mimes dependencies between topics into a NetworkX Directed Acyclic Graph (DAG) to enforce pedagogical ordering.
3. **Independent Question Verification**: Uploaded-course MCQs are drafted by Groq and checked independently by Gemini against a specific source excerpt.
4. **Bayesian Knowledge Tracing (BKT)**: Dynamically maintains each student's mastery probability $P(L_t)$, adjusting question difficulty and initiating **pedagogical backward-walks** to remediate root misconceptions.

---

## 🏛️ Architecture & Pod Division

To ensure clean isolation and zero merge conflicts, the repository is structured into decoupled pods governed by frozen data contracts in `src/schemas/`:

```
Saarthi/
├── src/
│   ├── schemas/           # Single Source of Truth (Frozen Data Contracts)
│   │   ├── models.py      # ContentUnit, ConceptNode, Question, LearnerState
│   ├── ingestion/         # [Pod A] PPTX/PDF Parsers, Whisper Transcription, Vision Captioning
│   ├── graph/             # [Pod B] Concept Graph DAG (NetworkX), Topological Order, Prerequisite Mining
│   ├── retrieval/         # [Pod B] Hybrid Search (BM25 + Dense Vectors), Reranker, Citations, Refusal
│   ├── assessment/        # [Pod C] Dual-LLM Verifier, SymPy Validation, Semantic Deduplication
│   ├── learner_model/     # [Pod C] BKT Engine, Adaptive Question Builder, Diagnostic Report
│   ├── api/               # [Pod D] Unified FastAPI Integration Service Layer
│   ├── ui/                # [Pod D] Production Next.js App (Chat, Graph DAG, Quiz, Benchmark)
│   └── eval/              # [Pod D] RAGAS Evaluation Harness & Monte Carlo Ablation Bench
```

### Pod Ownership Matrix
| Pod | Core Responsibilities | Input Contract | Output Contract |
| :--- | :--- | :--- | :--- |
| **Pod A (Ingestion)** | Multimodal extraction (PPTX fallback parser, PDF, video audio alignment). | Raw Documents | `ContentUnit` |
| **Pod B (Graph & Retrieval)** | Prerequisite DAG topology, hybrid BM25 + dense search, calibrated refusal gate, citation chips. | `ContentUnit` | `ConceptNode` + Grounded Context |
| **Pod C (Learner Model)** | Dual-LLM verification, SymPy math check, BKT engine ($P(L_t)$), adaptive backward-walk. | `ConceptNode` | `Question` + `LearnerState` |
| **Pod D (Frontend & Eval)** | Next.js UI dashboard & grounded chat, FastAPI endpoints, Monte Carlo ablation bench, RAGAS harness. | All Schemas | Full Web Application |

---

## 🚀 Key Features

### 1. Grounded Tutor Chatbot (`/chat`)
- **Verifiable Citations**: Every claim is anchored to exact slide, page, or timestamp references with clickable citation inspection drawers.
- **Confidence-Gated Refusal**: Questions outside the uploaded course curriculum are strictly flagged or refused to eliminate hallucinations.
- **Multimodal Uploads**: Ingest PowerPoint lectures and PDFs dynamically into active vector retrieval.
- **Session Persistence**: Chat sessions and message histories persist locally in SQLite.

### 2. Interactive Prerequisite Knowledge Graph (`/graph`)
- **NetworkX Topology**: Visualizes curriculum concepts as a validated Directed Acyclic Graph (DAG).
- **Pedagogical Backward-Walk Principle**: If a student struggles on an advanced concept (e.g., *Linear Discriminant Analysis*), the tutor walks backward along prerequisite edges to verify upstream foundations (*Eigenvalues* and *Least Squares*) instead of repeating failure nodes.
- **Evidence Drawer**: Shows exact lecture excerpts and slides linked to each concept node.

### 3. Customizable Assessment Arena (`/quiz`)
- **Configurable Quizzes**: Students can configure their assessment by:
  - **Question Count**: 3, 5, 8, 10, or 15 questions.
  - **Difficulty Level**: Level 1 (Introductory & Axioms) through Level 5 (Proofs & Derivations), or Dynamic BKT.
  - **Topic Target**: Focus on a single concept or all topics curriculum-wide.
- **Dual-LLM + SymPy Audit**: Each card exposes the verification audit trail (Generator Model, Independent Verifier Model agreement, SymPy validation status).
- **Live Bayesian Updates**: Submitting an answer instantly recalculates concept mastery with guess/slip weighting.

### 4. Monte Carlo Ablation Bench (`/benchmark`)
- **Empirical Personalization Benchmark**: Simulates 30 synthetic learners over 5 consecutive sessions comparing **Adaptive BKT** (prerequisite-first) vs. a **Random Question Baseline**.
- **Demonstrated Mastery Gain**: +5.6% to +27% higher mastery acceleration ($p < 0.001$).
- **Recorded grounding evaluation** reports retrieval hits, citation precision, and refusal rates on the labeled development corpus. Run `python scripts/eval_grounding.py` and read the results at `GET /eval/grounding`.
- **Interactive Re-run**: Recalculates Monte Carlo simulations live on demand.

---

## 🛠️ Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ and `npm`

### 1. Clone & Configure Environment
```bash
git clone https://github.com/NansKong/Saarthi-A-Verified-Grounded-Adaptive-Tutor.git
cd Saarthi

# Copy environment template
cp .env.example .env
```
The demo starts with local hashing and lexical reranking. Add API keys in `.env` when you want
provider-backed generation or course builds. To use Gemini embeddings, set `EMBEDDING_PROVIDER=gemini`
and provide a valid `GEMINI_API_KEY`. You can also choose `auto` for key-based provider selection.

### 2. Backend Setup & Startup (FastAPI)
```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the unified backend server
python -m uvicorn src.api.service:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be live at: `http://127.0.0.1:8000/docs`

If startup fails with `API_KEY_INVALID` from the embedding endpoint, check `EMBEDDING_PROVIDER`
in `.env`. Select `hash` to run retrieval offline or replace the rejected key for the hosted provider.
Set `LLM_PROVIDER=none` for a demo that also skips hosted text generation.

### 3. Frontend Setup & Startup (Next.js)
```bash
# In a separate terminal
cd src/ui

# Install dependencies
npm install

# Start the Next.js development server
npm run dev
```
Open your browser at: `http://localhost:3000`

---

## 🧪 Testing & Verification

Run the full automated test suite:
```bash
# Run Pod B retrieval and graph test suites (128 tests)
pytest tests/ -v

# Verify Next.js production build and TypeScript contracts
cd src/ui
npm run build
```

---

## 📋 API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/chat` | Grounded conversational tutor Q&A with citations |
| `GET` | `/graph` | Prerequisite DAG topology and evidence details |
| `POST` | `/quiz` | Custom or adaptive quiz generation (size, difficulty, concept) |
| `POST` | `/answer` | Grades answer, updates BKT mastery, and provides explanation |
| `GET` | `/mastery/{student_id}` | Student mastery board across all course concepts |
| `POST` | `/diagnostic` | Issues diagnostic questions. Submit their attempt IDs to `/answer` to update mastery from observed answers |
| `GET` | `/report/{student_id}` | Generates misconception report and backward-walk recommendation |
| `GET` | `/eval/ablation` | Monte Carlo simulated learning curves |
| `GET` | `/eval/grounding` | Recorded development-set retrieval, citation, and refusal metrics |
| `POST` | `/ingest/upload` | Multimodal ingestion endpoint for PPTX, PDF, and video |

## Tutoring from an uploaded course

Create a private course with a single PDF, PPTX, image, lecture recording, or text file.
The API stages the file and returns a `course_id` and an `access_token` while FastAPI processes it in the background.
Keep the token and use it as `Authorization: Bearer <access_token>` for every course request.
The token grants access to one private course and its learner state.

```bash
curl -F 'file=@lecture.pdf' http://127.0.0.1:8000/courses
```

| Method | Path | Use |
| --- | --- | --- |
| GET | `/courses/{course_id}` | Check build and assessment status |
| POST | `/courses/{course_id}/retry` | Resume a queued or failed build, or retry assessment generation |
| POST | `/courses/{course_id}/chat` | Ask a question grounded in the uploaded course |
| GET | `/courses/{course_id}/graph` | Read concepts, prerequisites, and evidence IDs |
| POST | `/courses/{course_id}/quiz` | Issue verified practice questions using the learner's mastery |
| POST | `/courses/{course_id}/diagnostic` | Issue a diagnostic across course topics |
| POST | `/courses/{course_id}/answer` | Submit `q_id`, `attempt_id`, and `answer`. An identical retry returns the original grade |
| GET | `/courses/{course_id}/mastery` | Read persisted concept mastery |
| GET | `/courses/{course_id}/evidence/{unit_id}` | Open the exact source excerpt and its page, slide, or timestamp |

The course graph requires a configured text model. Verified course quizzes require both `GROQ_API_KEY`
and `GEMINI_API_KEY`. Check `assessment_status` when the course build is ready.
Retain the SQLite file and `uploads/` directory across restarts. For a shared server, configure
`POD_B_ADMIN_TOKEN` and send it as `X-Admin-Token` when creating courses. Set `SAARTHI_LEGACY_TOKEN`
to restrict the legacy demo routes to trusted callers using `X-Legacy-Token`.

---

## 📜 License
MIT License. Developed for the Multimodal AI Hackathon 2026.
