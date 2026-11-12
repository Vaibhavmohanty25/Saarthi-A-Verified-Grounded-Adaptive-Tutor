"""Build a source-linked bank from independently verified course questions."""

import logging

from src.assessment.generator import generate_question, select_groq_model
from src.assessment.verifier import answers_match, make_gemini_client, verify_question
from src.schemas.models import Question, SourceLocation

log = logging.getLogger(__name__)
MAX_QUESTIONS = 12


def build_course_questions(bundle, settings) -> list[Question]:
    if not settings.groq_api_key or not settings.gemini_api_key:
        return []

    from groq import Groq

    groq = Groq(api_key=settings.groq_api_key, timeout=30, max_retries=1)
    model = select_groq_model(groq)
    gemini = make_gemini_client(settings.gemini_api_key)
    if not gemini[0]:
        return []

    questions = []
    seen_stems = set()
    for concept in list(bundle.graph.concepts.values())[:MAX_QUESTIONS]:
        evidence = next(
            (unit for unit_id in concept.evidence_units if (unit := bundle.store.get(unit_id))),
            None,
        )
        if evidence is None:
            continue
        source = evidence.searchable_text()
        location = SourceLocation(
            page=evidence.location.page,
            slide=evidence.location.slide,
            timestamp=evidence.location.label().lstrip("@") if evidence.location.t_start is not None else None,
        )
        try:
            question, _ = generate_question(concept, source, location, groq, model, mcq_only=True)
        except (TypeError, ValueError):
            log.info("Discarded malformed generated question for %s", concept.concept_id)
            continue
        stem = " ".join(question.stem.casefold().split())
        choices = question.options or []
        if (
            question.type != "mcq" or not stem or stem in seen_stems or len(choices) != 4
            or len({" ".join(option.casefold().split()) for option in choices if option.strip()}) != 4
        ):
            continue
        correct_choice = next((option for option in choices if answers_match(option, question.answer, "mcq")), None)
        if correct_choice is None:
            continue
        question.answer = correct_choice
        question, _, _ = verify_question(question, source, gemini)
        if question.verified:
            question.concept_id = concept.concept_id
            question.source_unit_id = evidence.unit_id
            question.explanation = evidence.text
            seen_stems.add(stem)
            questions.append(question)
    return questions
