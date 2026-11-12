"""
report.py  --  Piece 5: the post-assessment report.

After a quiz, this produces the "you're weak here, and here's why" summary the
rubric asks for. It does three things:

  1. Per-question feedback -- for every answer, the correct answer and a
     citation back to the source (slide / page / timestamp).
  2. Weak topics -- the concepts the student is weakest at, ranked.
  3. Likely misconceptions -- for each wrong answer, the common mistake behind it.

For a demo the misconceptions come from a small curated table below. In the
full system an LLM would write them from the student's actual wrong answer --
the function `llm_misconception()` is the hook for that.

--- Run it ---
    python report.py
"""

from src.mock_data import get_concepts, get_questions, get_question_concept_id
from src.learner_model.bkt import LearnerModel
from src.learner_model.adaptive import (
    build_quiz,
    select_next_concept,
    choose_difficulty,
)

WEAK_THRESHOLD = 0.50   # mastery below this counts as a weak topic

# Curated misconceptions for the demo concepts (an LLM writes these in production).
COMMON_MISCONCEPTIONS = {
    "derivatives": "Confusing the derivative with the function's value instead of seeing it as a rate of change.",
    "chain_rule": "Applying the chain rule as a plain product, forgetting to multiply by the inner derivative.",
    "loss_function": "Thinking the loss measures accuracy, rather than the size of the error.",
    "gradient_descent": "Moving along the gradient instead of opposite to it (thinking we climb, not descend).",
    "learning_rate": "Assuming a bigger learning rate is always faster or better.",
    "neural_networks": "Believing more layers alone help, without non-linear activation functions.",
}


def format_location(loc):
    if not loc:
        return "(no source)"
    if hasattr(loc, "model_dump"):
        loc = loc.model_dump(exclude_none=True)
    if "timestamp" in loc:
        return f"Lecture {loc.get('lecture', '?')} @ {loc['timestamp']}"
    if "slide" in loc:
        return f"Slide {loc['slide']}"
    if "page" in loc:
        return f"Page {loc['page']}"
    return str(loc)


def llm_misconception(concept_id, wrong_answer, client=None):
    """Hook for the LLM version. Falls back to the curated table for now."""
    if client is not None:
        try:
            reply = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content":
                           f"A student answered '{wrong_answer}' to a question about {concept_id}. "
                           f"In one sentence, what is the likely misconception?"}],
                temperature=0.3,
            )
            return reply.choices[0].message.content.strip()
        except Exception:
            pass
    return COMMON_MISCONCEPTIONS.get(concept_id, "Review this concept from the source.")


def build_report(session, student, concepts):
    """session: list of (question, student_answer, correct)."""
    correct_count = sum(1 for _, _, ok in session if ok)
    total = len(session)

    # weak topics, ranked
    ranked = sorted(concepts, key=lambda c: student.mastery(c.concept_id))
    weak = [c for c in ranked if student.mastery(c.concept_id) < WEAK_THRESHOLD]

    lines = []
    lines.append("=" * 60)
    lines.append("POST-ASSESSMENT REPORT")
    lines.append("=" * 60)
    lines.append(f"Score: {correct_count}/{total} correct")
    lines.append("-" * 60)

    lines.append("Weak topics:")
    if weak:
        for c in weak:
            lines.append(f"  {c.name:<18} {student.mastery(c.concept_id)*100:5.1f}%   <-- focus here")
    else:
        lines.append("  (none below the weak threshold -- good going)")
    lines.append("-" * 60)

    lines.append("Per-question feedback:")
    for i, (q, ans, ok) in enumerate(session, 1):
        tag = "CORRECT" if ok else "WRONG  "
        concept_id = get_question_concept_id(q)
        lines.append(f"  Q{i} [{concept_id}] {tag}")
        if not ok:
            lines.append(f"       you answered : {ans}")
            lines.append(f"       correct      : {q.answer}")
            lines.append(f"       source       : {format_location(q.source_location)}")
            lines.append(f"       likely issue : {llm_misconception(concept_id, ans)}")
    lines.append("-" * 60)

    nxt = select_next_concept(concepts, student.all_masteries())
    lines.append(f"Recommended next : {nxt} (difficulty {choose_difficulty(student.mastery(nxt))})")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    concepts = get_concepts()
    questions = get_questions()

    # a student who is weak at Chain Rule
    student = LearnerModel([c.concept_id for c in concepts])
    student.apply_diagnostic({"derivatives": True, "chain_rule": False, "gradient_descent": True})

    quiz = build_quiz(concepts, student.all_masteries(), questions, size=5)

    # simulate answers: wrong only on chain_rule questions
    session = []
    for q in quiz:
        concept_id = get_question_concept_id(q)
        ok = concept_id != "chain_rule"
        student.observe(concept_id, ok)
        answer = q.answer if ok else "(a wrong answer)"
        session.append((q, answer, ok))

    print(build_report(session, student, concepts))


if __name__ == "__main__":
    main()
