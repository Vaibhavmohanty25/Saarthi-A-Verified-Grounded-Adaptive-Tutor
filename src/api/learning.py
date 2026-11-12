"""SQLite-backed mastery and grading for demo and uploaded courses."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from src.assessment.verifier import answers_match
from src.learner_model.adaptive import choose_difficulty, select_next_concept
from src.learner_model.bkt import LearnerModel
from src.mock_data import get_question_concept_id

DEMO_COURSE = "demo"


class LearningStore:
    def __init__(self, path: Path):
        self.path = path
        with closing(self.connect()) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS concept_mastery (
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    concept_id TEXT NOT NULL,
                    probability REAL NOT NULL,
                    PRIMARY KEY (course_id, student_id, concept_id)
                );
                CREATE TABLE IF NOT EXISTS learning_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    q_id TEXT NOT NULL,
                    diagnostic INTEGER NOT NULL,
                    submitted_answer TEXT,
                    result_json TEXT
                );
                CREATE INDEX IF NOT EXISTS learning_attempts_by_learner
                    ON learning_attempts (course_id, student_id);
            """)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _load(self, conn, course_id, student_id, concepts):
        model = LearnerModel(c.concept_id for c in concepts)
        for row in conn.execute(
            "SELECT concept_id, probability FROM concept_mastery WHERE course_id = ? AND student_id = ?",
            (course_id, student_id),
        ):
            if row["concept_id"] in model.concepts:
                model.concepts[row["concept_id"]].mastery = row["probability"]
        return model

    def learner(self, course_id, student_id, concepts):
        with closing(self.connect()) as conn:
            return self._load(conn, course_id, student_id, concepts)

    def issued_questions(self, course_id, student_id):
        with closing(self.connect()) as conn:
            return {
                row["q_id"] for row in conn.execute(
                    "SELECT DISTINCT q_id FROM learning_attempts WHERE course_id = ? AND student_id = ?",
                    (course_id, student_id),
                )
            }

    def issue(self, course_id, student_id, questions, *, diagnostic=False):
        pairs = [(q, uuid4().hex) for q in questions]
        with closing(self.connect()) as conn, conn:
            conn.executemany(
                "INSERT INTO learning_attempts (attempt_id, course_id, student_id, q_id, diagnostic) VALUES (?, ?, ?, ?, ?)",
                ((attempt, course_id, student_id, q.q_id, diagnostic) for q, attempt in pairs),
            )
        return pairs

    def grade(self, course_id, student_id, concepts, question, answer, attempt_id, *, legacy_summary=False):
        with closing(self.connect()) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            diagnostic = False
            if attempt_id:
                row = conn.execute(
                    """SELECT * FROM learning_attempts
                       WHERE attempt_id = ? AND course_id = ? AND student_id = ? AND q_id = ?""",
                    (attempt_id, course_id, student_id, question.q_id),
                ).fetchone()
                if row is None:
                    raise HTTPException(404, "Question attempt not found.")
                if row["result_json"] is not None:
                    if row["submitted_answer"] != answer:
                        raise HTTPException(409, "This attempt already has a different submitted answer.")
                    return json.loads(row["result_json"])
                diagnostic = bool(row["diagnostic"])
            else:
                attempt_id = uuid4().hex
                conn.execute(
                    "INSERT INTO learning_attempts (attempt_id, course_id, student_id, q_id, diagnostic) VALUES (?, ?, ?, ?, 0)",
                    (attempt_id, course_id, student_id, question.q_id),
                )

            student = self._load(conn, course_id, student_id, concepts)
            concept_id = get_question_concept_id(question)
            correct = answers_match(answer, question.answer, question.type)
            probability = student.concepts[concept_id].update(correct, learning_opportunity=not diagnostic)
            next_concept = select_next_concept(concepts, student.all_masteries())
            result = {
                "attempt_id": attempt_id,
                "correct": correct,
                "correct_answer": question.answer,
                "explanation": question.explanation,
                "concept_id": concept_id,
                "new_mastery": round(probability, 4),
                "next_concept": next_concept,
                "next_difficulty": choose_difficulty(student.mastery(next_concept)),
                "source_unit_id": question.source_unit_id,
                "source_location": question.source_location.model_dump(exclude_none=True),
            }
            conn.execute(
                """INSERT INTO concept_mastery VALUES (?, ?, ?, ?)
                   ON CONFLICT (course_id, student_id, concept_id)
                   DO UPDATE SET probability = excluded.probability""",
                (course_id, student_id, concept_id, probability),
            )
            conn.execute(
                "UPDATE learning_attempts SET submitted_answer = ?, result_json = ? WHERE attempt_id = ?",
                (answer, json.dumps(result), attempt_id),
            )
            if legacy_summary and not diagnostic:
                conn.execute(
                    "INSERT INTO completed_quizzes (id, student_id, topic, score, total, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (attempt_id, student_id, question.topic, float(correct), 1, datetime.now(timezone.utc).isoformat()),
                )
            return result

    def history(self, course_id, student_id, bank):
        with closing(self.connect()) as conn:
            rows = conn.execute(
                """SELECT q_id, submitted_answer, result_json FROM learning_attempts
                   WHERE course_id = ? AND student_id = ? AND result_json IS NOT NULL ORDER BY rowid""",
                (course_id, student_id),
            )
            return [
                (bank[row["q_id"]], row["submitted_answer"], json.loads(row["result_json"])["correct"])
                for row in rows if row["q_id"] in bank
            ]
