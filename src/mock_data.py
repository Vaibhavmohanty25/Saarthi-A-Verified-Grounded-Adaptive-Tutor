"""
mock_data.py  --  Fake data so Pod C can build before Pod B is ready.

Decision 1 (scope): one topic chain from a machine-learning lecture series --
Derivatives -> Chain Rule -> Gradient Descent -> Neural Networks, with a
Loss Function branch. Six concepts, enough to show a real prerequisite graph.

Decision 3 (mock data): 6 concepts and 12 questions (MCQ, short, numeric),
so every code path has something to run against. When Pod B ships the real
graph, swap these functions out; nothing else changes.
"""

from src.schemas.models import ConceptNode, ContentUnit, Question


def _concept(concept_id, name, topic, prerequisites=None, evidence_units=None):
    return ConceptNode(
        concept_id=concept_id,
        name=name,
        topic=topic,
        prerequisites=prerequisites or [],
        evidence_units=evidence_units or [],
    )


def _unit(unit_id, source_id, source_type, location, text):
    return ContentUnit(
        unit_id=unit_id,
        source_id=source_id,
        source_type=source_type,
        location=location,
        text=text,
    )


def _question(
    q_id,
    concept_id,
    topic,
    source_location,
    difficulty,
    question_type,
    stem,
    options=None,
    answer="",
    verified=False,
    verifier_agreement=None,
):
    return Question(
        q_id=q_id,
        topic=topic,
        source_location=source_location,
        difficulty=difficulty,
        type=question_type,
        stem=stem,
        options=options,
        answer=answer,
        verified=verified,
        verifier_agreement=1.0 if verifier_agreement else 0.0,
    )


def get_question_concept_id(question):
    """Resolve the concept carried by a canonical Question record."""
    if concept_id := getattr(question, "concept_id", None):
        return concept_id
    qid = getattr(question, "q_id", str(question))
    if qid.startswith("gen_"):
        return qid.removeprefix("gen_")
    if qid.startswith("sim_"):
        return qid.removeprefix("sim_").rsplit("_", 2)[0]
    try:
        from src.learner_model.live_course_data import LIVE_QUESTION_CONCEPTS
        if qid in LIVE_QUESTION_CONCEPTS:
            return LIVE_QUESTION_CONCEPTS[qid]
    except ImportError:
        pass
    return QUESTION_CONCEPTS.get(qid, qid)


# --- Decision 1: the scope -- six concepts with prerequisite links ---
CONCEPTS = [
    _concept("derivatives",     "Derivatives",     "Calculus",
                prerequisites=[],                       evidence_units=["u1"]),
    _concept("chain_rule",      "Chain Rule",      "Calculus",
                prerequisites=["derivatives"],          evidence_units=["u2"]),
    _concept("loss_function",   "Loss Function",   "Optimization",
                prerequisites=["derivatives"],          evidence_units=["u3"]),
    _concept("gradient_descent","Gradient Descent","Optimization",
                prerequisites=["chain_rule", "loss_function"], evidence_units=["u4"]),
    _concept("learning_rate",   "Learning Rate",   "Optimization",
                prerequisites=["gradient_descent"],     evidence_units=["u5"]),
    _concept("neural_networks", "Neural Networks", "Deep Learning",
                prerequisites=["gradient_descent"],     evidence_units=["u6"]),
]

CONTENT_UNITS = [
    _unit(
        "u1", "ML_Lecture_1.pdf", "pdf", {"slide": 4},
        "A derivative measures the rate at which a function changes as its input changes.",
    ),
    _unit(
        "u2", "ML_Lecture_1.pdf", "pdf", {"slide": 9},
        "The chain rule differentiates a composite function by multiplying the derivative of the outer function by the derivative of the inner function.",
    ),
    _unit(
        "u3", "ML_Lecture_2.pdf", "pdf", {"slide": 13},
        "A loss function measures the error between a model's predictions and the target values.",
    ),
    _unit(
        "u4", "ML_Lecture_2.pdf", "pdf", {"slide": 14},
        "Gradient descent updates parameters in the direction opposite to the gradient, reducing the loss.",
    ),
    _unit(
        "u5", "ML_Lecture_2.pdf", "pdf", {"slide": 18},
        "The learning rate controls the size of each gradient descent update; a rate that is too large can cause divergence.",
    ),
    _unit(
        "u6", "ML_Lecture_3.pdf", "pdf", {"slide": 24},
        "Neural networks use the chain rule during backpropagation to calculate how the loss changes with respect to parameters.",
    ),
]

# --- Decision 3: a small verified question pool, tagged with topic/source/difficulty ---
QUESTIONS = [
    _question("q1", "derivatives", "Calculus", {"slide": 4}, 1, "mcq",
             "What does the derivative of a function measure?",
             options=["Its rate of change", "Its maximum value", "Its area", "Its length"],
             answer="Its rate of change", verified=True, verifier_agreement=True),
    _question("q2", "derivatives", "Calculus", {"slide": 5}, 2, "numeric",
             "If f(x) = 3x^2, what is f'(2)?", answer="12",
             verified=True, verifier_agreement=True),
    _question("q3", "chain_rule", "Calculus", {"slide": 9}, 2, "mcq",
             "The chain rule is used to differentiate which kind of function?",
             options=["Composite functions", "Constant functions", "Linear functions", "Absolute values"],
             answer="Composite functions", verified=True, verifier_agreement=True),
    _question("q4", "chain_rule", "Calculus", {"slide": 11}, 3, "numeric",
             "If y = (2x + 1)^3, what is dy/dx at x = 0?", answer="6",
             verified=True, verifier_agreement=True),
    _question("q5", "loss_function", "Optimization", {"slide": 13}, 2, "short",
             "What does the loss function measure?", answer="The error between predictions and targets",
             verified=True, verifier_agreement=True),
    _question("q6", "gradient_descent", "Optimization", {"slide": 14}, 2, "mcq",
             "Gradient descent updates parameters by moving in which direction?",
             options=["Opposite to the gradient", "Along the gradient", "Randomly", "Toward the maximum"],
             answer="Opposite to the gradient", verified=True, verifier_agreement=True),
    _question("q7", "gradient_descent", "Optimization", {"timestamp": "12:41"}, 3, "short",
             "Why does gradient descent follow the negative gradient?",
             answer="Because the negative gradient points in the direction of steepest decrease of the loss",
             verified=True, verifier_agreement=True),
    _question("q8", "gradient_descent", "Optimization", {"slide": 16}, 4, "numeric",
             "With learning rate 0.1 and gradient 5, what is the update step size?", answer="0.5",
             verified=True, verifier_agreement=True),
    _question("q9", "learning_rate", "Optimization", {"slide": 18}, 2, "mcq",
             "What happens if the learning rate is too large?",
             options=["Training may diverge", "Training always converges faster", "Nothing changes", "The gradient becomes zero"],
             answer="Training may diverge", verified=True, verifier_agreement=True),
    _question("q10", "learning_rate", "Optimization", {"slide": 19}, 3, "short",
             "What is the trade-off in choosing a learning rate?", answer="Too small converges slowly; too large may diverge",
             verified=True, verifier_agreement=True),
    _question("q11", "neural_networks", "Deep Learning", {"slide": 24}, 2, "mcq",
             "Backpropagation mainly relies on which calculus tool?",
             options=["The chain rule", "Integration by parts", "Taylor series", "Limits"],
             answer="The chain rule", verified=True, verifier_agreement=True),
    _question("q12", "neural_networks", "Deep Learning", {"slide": 26}, 4, "short",
             "Why is a non-linear activation function needed in a neural network?",
             answer="Without it, stacked layers collapse into a single linear transformation",
             verified=True, verifier_agreement=True),
]

QUESTION_CONCEPTS = {
    "q1": "derivatives",
    "q2": "derivatives",
    "q3": "chain_rule",
    "q4": "chain_rule",
    "q5": "loss_function",
    "q6": "gradient_descent",
    "q7": "gradient_descent",
    "q8": "gradient_descent",
    "q9": "learning_rate",
    "q10": "learning_rate",
    "q11": "neural_networks",
    "q12": "neural_networks",
}


def get_concepts():
    return list(CONCEPTS)


def get_content_units():
    return list(CONTENT_UNITS)


def get_questions():
    return list(QUESTIONS)
