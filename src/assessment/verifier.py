"""
verifier.py  --  Piece 3: Gemini checks the question independently.

This is the "verifier" half of the assessment pipeline. It takes a question
that Groq generated and asks Gemini to answer it -- BLIND, i.e. Gemini never
sees Groq's answer. Then we compare the two answers:

    agree   -> question.verified = True   (safe to show the student)
    disagree-> question.verified = False  (throw it away)

Because Groq and Gemini are different model families, they rarely share the
same mistake -- so a question both of them answer the same way is much more
trustworthy than one only a single model produced.

--- Run it ---
    python verifier.py

It generates one question (Groq, or dry-run without a key), then verifies it
(Gemini, or dry-run without a key), and prints the verdict.

Keys come from the environment (never typed into this file):
    set GROQ_API_KEY=your_key_here
    set GEMINI_API_KEY=your_key_here
"""

import os
import re

import env_loader  # noqa: F401
from src.mock_data import get_concepts, get_content_units
from src.assessment.generator import (
    build_source_text,
    generate_question,
    select_groq_model,
    source_location,
)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
AI_REQUEST_TIMEOUT_SECONDS = 30

# Used only when there is no Gemini key, so the flow can still be demonstrated.
DRY_RUN_GEMINI_ANSWER = "Opposite to the gradient"


# ---------- talking to Gemini ----------

def make_gemini_client(key):
    """Return a ('new'|'old', client) tuple, or (None, None) if the SDK is missing."""
    try:
        from google import genai as new_genai
        from google.genai import types

        return (
            "new",
            new_genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    timeout=AI_REQUEST_TIMEOUT_SECONDS * 1000
                ),
            ),
        )
    except ImportError:
        pass
    try:
        import google.generativeai as old_genai
        old_genai.configure(api_key=key)
        return ("old", old_genai)
    except ImportError:
        return (None, None)


def gemini_generate(client_tuple, prompt):
    kind, client = client_tuple
    if kind == "new":
        return client.models.generate_content(
            model=GEMINI_MODEL, contents=prompt
        ).text
    model = client.GenerativeModel(GEMINI_MODEL)
    return model.generate_content(
        prompt,
        request_options={"timeout": AI_REQUEST_TIMEOUT_SECONDS},
    ).text


def build_verify_prompt(question, source_text):
    """Ask Gemini to answer using only the source. It never sees Groq's answer."""
    options = ""
    if question.options:
        options = "Options:\n" + "\n".join(
            f"{i}. {o}" for i, o in enumerate(question.options, 1)
        ) + "\n"
    return (
        "Answer the question below using ONLY the source text.\n"
        "If the source text does not contain the answer, reply exactly: NOT IN SOURCE\n\n"
        f"Source text:\n{source_text}\n\n"
        f"Question: {question.stem}\n"
        f"{options}"
        "Reply with ONLY the final answer, and nothing else."
    )


def ask_gemini(client_tuple, question, source_text):
    if client_tuple is None or client_tuple[0] is None:
        return DRY_RUN_GEMINI_ANSWER, "dry-run (no API key)"
    prompt = build_verify_prompt(question, source_text)
    return gemini_generate(client_tuple, prompt).strip(), "Gemini"


# ---------- comparing the two answers ----------

def _normalise(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def _numbers(text):
    return re.findall(r"-?\d+\.?\d*", str(text))


def answers_match(answer_a, answer_b, qtype):
    """Do Groq's answer and Gemini's answer mean the same thing?"""
    a, b = _normalise(answer_a), _normalise(answer_b)
    if not a or not b or a == "not in source" or b == "not in source":
        return False
    if a == b:
        return True
    if qtype == "mcq":
        return False
    if qtype == "numeric":
        na, nb = _numbers(answer_a), _numbers(answer_b)
        if na and nb:
            try:
                return abs(float(na[-1]) - float(nb[-1])) < 1e-6
            except ValueError:
                return False
    # for mcq / short: accept if one answer contains the other
    return a in b or b in a


def verify_question(question, source_text, client_tuple=None):
    """Set question.verified based on whether Gemini agrees with Groq."""
    gemini_answer, used = ask_gemini(client_tuple, question, source_text)
    agree = answers_match(question.answer, gemini_answer, question.type)
    question.verifier_agreement = 1.0 if agree else 0.0
    question.verified = agree
    return question, gemini_answer, used


# ---------- run the whole generator -> verifier flow ----------

def main():
    concepts = get_concepts()
    units = get_content_units()
    concept = next(c for c in concepts if c.concept_id == "gradient_descent")
    src = build_source_text(concept, units)
    loc = source_location(concept, units)

    # 1. generate (Groq)
    groq_client = None
    if os.environ.get("GROQ_API_KEY"):
        try:
            from groq import APIConnectionError, APIStatusError, Groq
            groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
            groq_model = select_groq_model(groq_client)
        except ImportError:
            print("The 'groq' package is missing. Run:  pip install groq")
            return
        except (APIStatusError, APIConnectionError, ValueError) as error:
            print("Groq setup failed:", error)
            return
    else:
        groq_model = None
    question, gen_by = generate_question(
        concept, src, loc, groq_client, groq_model
    )

    # 2. verify (Gemini)
    gemini_client = None
    if os.environ.get("GEMINI_API_KEY"):
        gemini_client = make_gemini_client(os.environ["GEMINI_API_KEY"])
        if gemini_client[0] is None:
            print("The Gemini package is missing. Run:  pip install google-genai")
            return
    question, gemini_answer, ver_by = verify_question(question, src, gemini_client)

    # 3. report
    print("=" * 60)
    print("PIECE 3  --  Verifier (Gemini checks Groq's question)")
    print("=" * 60)
    print(f"Question (by {gen_by}): {question.stem}")
    if question.options:
        for i, o in enumerate(question.options, 1):
            print(f"   {i}. {o}")
    print("-" * 60)
    print(f"Groq's answer   : {question.answer}")
    print(f"Gemini's answer : {gemini_answer}   (by {ver_by})")
    print("-" * 60)
    print(f"Agreement       : {question.verifier_agreement}")
    print(f"Verified        : {question.verified}   "
          + ("<- kept, safe to show the student" if question.verified
             else "<- REJECTED, answers disagree"))
    print("-" * 60)
    print("Done. Next: piece 4 -- de-duplication + the misconception report.")


if __name__ == "__main__":
    main()
