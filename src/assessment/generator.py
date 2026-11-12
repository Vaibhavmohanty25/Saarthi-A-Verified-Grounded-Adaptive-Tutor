"""
generator.py  --  Piece 2: Groq writes ONE question for ONE concept.

This is the "generator" half of the assessment pipeline. It reads the source
text for a concept and asks Groq to write a single exam question, grounded
ONLY in that source text.

It returns a `Question` object with verified=False -- the verifier (piece 3,
Gemini) will flip that to True later.

--- Run it ---
    python generator.py

If GROQ_API_KEY is set, it calls the real model.
If not, it runs in DRY-RUN mode with a canned reply, so you can still see the
whole flow and check that the parsing works.

Keys come from the environment (never typed into this file):
    set GROQ_API_KEY=your_key_here       (Command Prompt)
    $env:GROQ_API_KEY="your_key_here"    (PowerShell)
    $env:GROQ_MODEL="openai/gpt-oss-20b" (optional model override)
"""

import os
import re
import json

import env_loader  # noqa: F401
from src.mock_data import get_concepts, get_content_units
from src.schemas.models import Question

# Groq model availability depends on the account and changes over time. The
# optional GROQ_MODEL environment variable takes precedence.
GROQ_MODEL = os.environ.get("GROQ_MODEL")
GROQ_MODEL_PREFERENCES = (
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
)


def select_groq_model(client):
    """Return an explicitly configured or preferred model available to this key."""
    available_models = {model.id for model in client.models.list().data}
    if GROQ_MODEL:
        if GROQ_MODEL not in available_models:
            raise ValueError(
                f"GROQ_MODEL={GROQ_MODEL!r} is not available for this key."
            )
        return GROQ_MODEL
    model_name = next(
        (model for model in GROQ_MODEL_PREFERENCES if model in available_models),
        None,
    )
    if model_name is None:
        raise ValueError(
            "No supported text model is available for this Groq key. "
            "Set GROQ_MODEL to an accessible model ID."
        )
    return model_name

# Used only when there is no API key, so the flow can still be demonstrated.
DRY_RUN_RESPONSE = """{
  "type": "mcq",
  "stem": "In which direction does gradient descent move the parameters?",
  "options": ["Opposite to the gradient", "Along the gradient", "A random direction", "Toward the maximum of the loss"],
  "answer": "Opposite to the gradient",
  "difficulty": 2
}"""


def build_source_text(concept, units):
    """Gather the source text that belongs to this concept."""
    ids = set(concept.evidence_units)
    parts = [u.text for u in units if u.unit_id in ids]
    return "\n".join(parts) if parts else "(no source text found for this concept)"


def source_location(concept, units):
    """The slide/page/timestamp to tag the question with."""
    for u in units:
        if u.unit_id in concept.evidence_units:
            return u.location
    return {}


def build_prompt(concept, source_text, *, mcq_only=False):
    prompt = (
        "You are writing ONE exam question for a student.\n"
        "Use ONLY the source text below. Do not use any outside knowledge.\n\n"
        f"Concept: {concept.name}\n\n"
        f"Source text:\n{source_text}\n\n"
        'Write ONE question about this concept. Choose a type: "mcq" (4 options), '
        '"short" (free text answer), or "numeric" (a calculation with one number answer).\n'
        "Return ONLY a JSON object, with no other text, using exactly these keys:\n"
        '  "type": one of "mcq", "short", "numeric"\n'
        '  "stem": the question text\n'
        '  "options": an array of 4 strings (ONLY for mcq; otherwise null)\n'
        '  "answer": the correct answer as a string\n'
        '  "difficulty": an integer from 1 to 5\n'
    )
    if mcq_only:
        prompt += 'Use only the "mcq" type with four distinct choices. Use the exact correct option as the answer.\n'
    return prompt


def parse_question_json(raw, concept, location):
    """Turn the model's raw text into a Question object."""
    text = raw.strip()
    # remove ```json ... ``` fences if the model added them
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    # grab the first { ... last }
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in the model's reply:\n" + raw)
    obj = json.loads(text[start:end + 1])

    qtype = obj.get("type", "short")
    options = obj.get("options")
    if qtype != "mcq":
        options = None

    return Question(
        q_id="gen_" + concept.concept_id,
        topic=concept.topic,
        source_location=location,
        difficulty=int(obj.get("difficulty", 3)),
        type=qtype,
        stem=obj.get("stem", ""),
        options=options,
        answer=str(obj.get("answer", "")),
        verified=False,          # the verifier sets this to True in piece 3
        verifier_agreement=0.0,
    )


def generate_question(concept, source_text, location, client=None, model=None, *, mcq_only=False):
    """Return (Question, source_used). client=None means dry-run."""
    prompt = build_prompt(concept, source_text, mcq_only=mcq_only)
    if client is None:
        raw, used = DRY_RUN_RESPONSE, "dry-run (no API key)"
    else:
        reply = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        raw, used = reply.choices[0].message.content, "Groq"
    return parse_question_json(raw, concept, location), used


def main():
    concepts = get_concepts()
    units = get_content_units()

    concept_id = "gradient_descent"     # pick one concept for this test
    concept = next(c for c in concepts if c.concept_id == concept_id)
    src = build_source_text(concept, units)
    loc = source_location(concept, units)

    key = os.environ.get("GROQ_API_KEY")
    client = None
    model_name = None
    if key:
        try:
            from groq import APIConnectionError, APIStatusError, Groq
            client = Groq(api_key=key)
            model_name = select_groq_model(client)
        except ImportError:
            print("The 'groq' package is missing. Run:  pip install groq")
            return
        except (APIStatusError, APIConnectionError) as error:
            print("Groq model lookup failed:", error)
            return
        except ValueError as error:
            print(error)
            return

    print("=" * 60)
    print("PIECE 2  --  Generator (Groq writes one question)")
    print("=" * 60)
    print(f"Concept        : {concept.name}  ({concept.concept_id})")
    print(f"Source location: {loc}")
    print(f"Source text    : {src[:80]}...")
    print("-" * 60)

    question, used = generate_question(concept, src, loc, client, model_name)

    print(f"Answered by    : {used}")
    print("Generated question object:")
    print(f"  q_id        : {question.q_id}")
    print(f"  topic       : {question.topic}")
    print(f"  type        : {question.type}")
    print(f"  difficulty  : {question.difficulty}")
    print(f"  stem        : {question.stem}")
    if question.options:
        for i, opt in enumerate(question.options, 1):
            print(f"    {i}. {opt}")
    print(f"  answer      : {question.answer}")
    print(f"  source      : {question.source_location}")
    print(f"  verified    : {question.verified}   <- piece 3 (Gemini) will set this")
    print("-" * 60)
    print("Done. Next: piece 3 -- Gemini checks this question independently.")


if __name__ == "__main__":
    main()
