"""Grounded answering: retrieve -> gate -> generate cited claims -> verify -> compose.

Guarantees (each is tested):
  * Nothing is shown as source-backed unless it cites a retrieved unit whose text supports it.
  * Questions the material does not cover are refused (or answered ONLY as clearly-labelled outside knowledge
    if the caller opts in) - never silently answered from the model's memory.
  * Without an LLM the tutor still works in 'extractive' mode (verbatim source excerpts, strict gate).
  * An LLM failure degrades to extractive mode instead of an error.

Gates, cheapest first:
  1. retrieval gate  - top reranker relevance >= threshold, or the question names a known concept
  2. LLM judgement   - the model must cite units for every claim, or say the material doesn't cover it
  3. claim check     - lexical support of each claim by its cited units (+ optional LLM fact-check)
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Optional

from .llm import LLM, LLMError

if TYPE_CHECKING:
    from src.graph.graph import KnowledgeGraph
from .retriever import HybridRetriever, SearchHit
from .schemas import AnswerResponse, AnswerStatus, Citation, Claim, ContentUnit, SourceType, make_citation
from .text import _WORD, STOPWORDS, stem, tokenize

SYSTEM_ANSWER = """You are a course tutor. Answer the student's question using ONLY the numbered course excerpts provided.
Reply with a single JSON object. Never use outside knowledge inside "claims"."""

PROMPT_ANSWER = """Question: {question}
{context}{coverage_note}
Excerpts (each starts with [unit_id]):

{excerpts}

Return JSON: {{"answerable": bool, "claims": [{{"text": str, "unit_ids": [str]}}], "outside_knowledge": [str]}}
Rules:
- "claims": short, self-contained statements that together answer the question. Each claim must be fully supported
  by the excerpts it cites in "unit_ids" (ids from the list above only). A claim with no supporting excerpt is forbidden.
- If the excerpts do not contain the answer, set "answerable": false and "claims": [].
- If a brief piece of general background would help but is NOT in the excerpts, put it in "outside_knowledge"
  (max 2 short items). Never mix it into "claims".
- Explain clearly for a student; keep it concise. Plain text; write maths inline."""

SYSTEM_VERIFY = "You are a strict fact checker. Reply with a single JSON object."
PROMPT_VERIFY = """For each numbered claim, decide whether the cited excerpt text fully supports it.

{items}

Return JSON: {{"verdicts": [{{"i": int, "supported": bool}}]}}"""

SYSTEM_STANDALONE = "You rewrite follow-up questions. Reply with a single JSON object."
PROMPT_STANDALONE = """Conversation so far:
{history}

Follow-up question: {question}

Rewrite the follow-up as a single self-contained question (keep it short; do not answer it).
Return JSON: {{"question": str}}"""

SYSTEM_OUTSIDE = "You are a helpful tutor. Reply with a single JSON object."
PROMPT_OUTSIDE = """The student's course material does not cover this question: {question}
Give a brief general-knowledge answer (at most 3 sentences). Return JSON: {{"answer": str}}"""


# Everyday question verbs/nouns that often sit next to a concept name but are not subject-matter terms.
# A short, generic list - a heuristic patch, found by measuring false positives on the labelled queries.
_GENERIC = frozenset("""affect affects need needs use used using make makes work works mean means help helps change changes
happen happens differ differs difference compare comparison define definition describe calculate compute apply applies
relate related matter impact influence cause causes depend depends require requires tell know understand important
different example examples step steps type types kind kinds way ways good bad best better much many
brief briefly upload uploaded uploads ppt pptx pdf presentation document doc file files slide slides video videos clip clips audio recording
rule rules law laws theory theories aspect aspects part parts point points time era role
summarize summary overview main concept concepts core topics topic detail details discuss review intro introduction outline cover covered chapter unit""".split())

_DEFINITION = re.compile(r"^(?:what\s+(?:is|are)\s+|define\s+)(?:(?:a|an|the)\s+)?([^?!.\n]+)[?!.]*$", re.I)
_FOLLOW_UP = re.compile(
    r"^(?:and|also|what about|how about|tell me more)\b|\b(?:it|its|they|their|this|that|these|those|former|latter)\b",
    re.I,
)


def _definition_topic(question: str) -> str:
    match = _DEFINITION.fullmatch(question.strip())
    if not match or not 2 <= len(tokenize(match[1])) <= 5:
        return ""
    return " ".join(tokenize(match[1], keep_stopwords=True))


def _contains_topic(text: str, topic: str) -> bool:
    tokens = " ".join(tokenize(text, keep_stopwords=True))
    return f" {topic} " in f" {tokens} "


def _supports_definition(text: str, topic: str) -> bool:
    return _contains_topic(text, topic) and bool(set(tokenize(text)) - set(tokenize(topic)))


def _evidence_text(unit: ContentUnit) -> str:
    text = unit.text
    prefix = unit.location.label()
    legacy_page = f"Page {unit.location.page} (" if unit.location.page is not None else f"{prefix} ("
    if text.startswith((f"{prefix} (", legacy_page)) and "): " in text:
        text = text.split("): ", 1)[1]
    return f"{text}\n{unit.image_caption}" if unit.image_caption else text


def _sentences(text: str, topic: str = "", n: int = 2, max_chars: int = 260) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    start = next((i for i, part in enumerate(parts) if topic and _contains_topic(part, topic)), 0)
    out = " ".join(parts[start : start + n])
    return out if len(out) <= max_chars else out[: max_chars - 3].rstrip() + "..."


def _fmt_excerpt(u: ContentUnit) -> str:
    fig = f" (figure: {u.image_caption})" if u.image_caption else ""
    return f"[{u.unit_id}] ({u.source_id}, {u.location.label()}) {u.text}{fig}"


class GroundedAnswerer:
    def __init__(self, retriever: HybridRetriever, graph: Optional[KnowledgeGraph], llm: Optional[LLM] = None, *,
                 threshold_strict: float, threshold_permissive: float, calibrated: bool = False,
                 k: int = 6, verify_with_llm: bool = False, min_support: float = 0.5):
        self.retriever, self.graph, self.llm = retriever, graph, llm
        self.t_strict, self.t_perm, self.calibrated = threshold_strict, threshold_permissive, calibrated
        self.k, self.verify_with_llm, self.min_support = k, verify_with_llm, min_support
        self._vocab = {t for u in retriever.units for t in tokenize(u.searchable_text())}  # what the course says

    def with_(self, retriever: HybridRetriever, graph: Optional[KnowledgeGraph]) -> "GroundedAnswerer":
        return GroundedAnswerer(retriever, graph, self.llm, threshold_strict=self.t_strict,
                                threshold_permissive=self.t_perm, calibrated=self.calibrated, k=self.k,
                                verify_with_llm=self.verify_with_llm, min_support=self.min_support)

    # ------------------------------------------------------------------ #
    def answer(self, question: str, *, history: Optional[list[dict]] = None,
               source_types: Optional[list[SourceType]] = None, source_ids: Optional[list[str]] = None,
               allow_outside_knowledge: bool = False, student_context: Optional[str] = None) -> AnswerResponse:
        question = question.strip()
        standalone = self._standalone(question, history or [])
        hits = self.retriever.search(standalone, self.k, source_types=source_types, source_ids=source_ids)
        if standalone != question:
            # Also search original user query so specific terms aren't washed out by standalone rewriting
            raw_hits = self.retriever.search(question, self.k, source_types=source_types, source_ids=source_ids)
            by_id = {h.unit.unit_id: h for h in hits}
            for rh in raw_hits:
                if rh.unit.unit_id not in by_id:
                    by_id[rh.unit.unit_id] = rh
                elif rh.relevance > by_id[rh.unit.unit_id].relevance or rh.score > by_id[rh.unit.unit_id].score:
                    by_id[rh.unit.unit_id] = rh
            hits = sorted(by_id.values(), key=lambda h: (-h.score, -h.relevance))[:self.k]

        retrieved = [h.unit.unit_id for h in hits]
        strength = max((sc for _, sc in self.graph.match_concepts(standalone, k=1)), default=0.0) if self.graph else 0.0
        if standalone != question and self.graph:
            strength = max(strength, max((sc for _, sc in self.graph.match_concepts(question, k=1)), default=0.0))
        top = hits[0].relevance if hits else 0.0
        top_dense = hits[0].dense if hits else 0.0
        top_bm25 = hits[0].bm25 if hits else 0.0
        thr = self.t_perm if self.llm else self.t_strict
        flagged = self.unseen_qualifiers(standalone)
        if standalone != question and not flagged:
            flagged = self.unseen_qualifiers(question)
        base = dict(question=question, retrieved=retrieved,
                    standalone_question=standalone if standalone != question else None)

        # Gate 1: Pass if reranker relevance >= thr, OR concept matched, OR dense/sparse similarity is high (when LLM judge will verify downstream)
        has_pass = bool(hits) and (top >= thr or (self.llm is not None and (top_dense >= 0.38 or top_bm25 >= 2.0)))
        if not hits or (not has_pass and strength < 1.0):  # gate 1
            return self._refuse(base, standalone, allow_outside_knowledge)

        if self.llm is not None:
            try:
                return self._generate(base, standalone, hits, allow_outside_knowledge, student_context, flagged)
            except (LLMError, RuntimeError):  # network/quota/format failure: degrade, don't crash
                resp = self._extractive(base, hits, top, thr=self.t_strict, strength=strength, flagged=flagged,
                                        question=standalone)
                if resp.status != AnswerStatus.REFUSED:  # keep the refusal text intact
                    resp.message = "The language model was unavailable. Showing matching source excerpts."
                    if flagged:
                        resp.message += " " + self._flag_message(flagged, standalone)
                return resp
        return self._extractive(base, hits, top, thr=self.t_strict, strength=strength, flagged=flagged, question=standalone)

    # ------------------------------------------------------------------ #
    def unseen_qualifiers(self, question: str) -> list[str]:
        """Terms the course never uses, sitting right next to a concept it does cover ('convolutional' in
        'convolutional neural network', 'sin' in 'derivative of sin x'). Such a question is about something
        near the material, not in it. Deliberately narrow: free-floating unfamiliar words (a student's own
        phrasing) are NOT flagged, so ordinary paraphrases are not penalised."""
        if not self.graph:
            return []
        words = [(stem(w), w) for w in _WORD.findall(question.lower()) if w not in STOPWORDS and w not in _GENERIC]
        stems = [s_ for s_, _ in words]
        out: list[str] = []
        for concept in self.graph.concepts.values():
            for phrase in [concept.name, *concept.aliases]:
                pt = tokenize(phrase)
                n = len(pt)
                for i in range(len(stems) - n + 1):
                    if n and stems[i:i + n] == pt:
                        for j in (i - 1, i + n):
                            if 0 <= j < len(words) and stems[j] not in self._vocab and words[j][1] not in out:
                                out.append(words[j][1])
        return out

    def _flag_message(self, terms: list[str], q: str) -> str:
        near = ", ".join(c.name for c, _ in self.graph.match_concepts(q, k=2)) if self.graph else ""
        quoted = ", ".join(f"'{t}'" for t in terms)
        return (f"Your question mentions {quoted}, which doesn't appear in your course material. "
                f"What follows is about the related material{f' ({near})' if near else ''} and may not answer your question.")

    def _standalone(self, question: str, history: list) -> str:
        if not history or not _FOLLOW_UP.search(question):
            return question
        turns = []
        for m in history[-6:]:
            r = m.get("role", "user") if isinstance(m, dict) else getattr(m, "role", "user")
            c = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
            turns.append(f"{r}: {str(c)[:400]}")
        if self.llm is not None:
            try:
                q = self.llm.generate_json(SYSTEM_STANDALONE, PROMPT_STANDALONE.format(
                    history="\n".join(turns), question=question)).get("question")
                if isinstance(q, str) and q.strip():
                    return q.strip()
            except (LLMError, RuntimeError, AttributeError):
                pass
        prev = ""
        for m in reversed(history):
            r = m.get("role", "") if isinstance(m, dict) else getattr(m, "role", "")
            c = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
            if r == "user":
                prev = str(c)
                break
        return f"{prev} {question}".strip()  # crude but keeps the topic words for retrieval

    def _refuse(self, base: dict, q: str, allow_outside: bool) -> AnswerResponse:
        hint = ""
        if self.graph:
            near = [c.name for c, _ in self.graph.match_concepts(q, k=3)]
            tops = [t.name for t in self.graph.topics.values() if t.parent_topic_id is None]
            hint = (f" Closest covered concepts: {', '.join(near)}." if near
                    else (f" This course covers: {', '.join(tops)}." if tops else ""))
        outside: list[str] = []
        if allow_outside and self.llm is not None:
            try:
                a = self.llm.generate_json(SYSTEM_OUTSIDE, PROMPT_OUTSIDE.format(question=q)).get("answer")
                outside = [str(a)] if a else []
            except (LLMError, RuntimeError, AttributeError):
                pass
        msg = "I couldn't find this in your course material, so I won't present an answer as if it were covered." + hint
        if outside:
            msg += " The note below is general knowledge, NOT from your material."
        return AnswerResponse(status=AnswerStatus.REFUSED, message=msg, outside_knowledge=outside,
                              mode="refusal", confidence=0.0, **base)

    # ------------------------------------------------------------------ #
    def _extractive(self, base: dict, hits: list[SearchHit], top: float, thr: float, strength: float,
                    flagged: Optional[list[str]] = None, question: str = "") -> AnswerResponse:
        if top < thr and strength < 1.0:  # strict gate (no LLM to catch a bad pass)
            return self._refuse(base, base["question"], False)
        topic = _definition_topic(question or base["question"]) if not flagged else ""
        if topic:
            chosen = [h for h in hits if _supports_definition(_evidence_text(h.unit), topic)][:1]
        else:
            chosen = [h for h in hits if h.relevance > 0 and h.relevance >= min(thr, top)][:3]
        if not chosen:
            return self._refuse(base, base["question"], False)
        claims = []
        for hit in chosen:
            excerpt = _sentences(_evidence_text(hit.unit), topic)
            claims.append(Claim(text=excerpt, citations=[make_citation(hit.unit, excerpt=excerpt)]))
        msg = "Showing matching excerpts from your course material."
        if flagged:  # a near-miss: real excerpts, but they probably don't answer what was asked
            return self._compose(base, claims, [], AnswerStatus.PARTIAL, mode="extractive", confidence=round(top, 3),
                                 message=self._flag_message(flagged, question or base["question"]))
        return self._compose(base, claims, [], AnswerStatus.GROUNDED, mode="extractive", confidence=round(top, 3), message=msg)

    def _generate(self, base: dict, q: str, hits: list[SearchHit], allow_outside: bool,
                  student_context: Optional[str], flagged: Optional[list[str]] = None) -> AnswerResponse:
        by_id = {h.unit.unit_id: h.unit for h in hits}
        ctx = f"Student context (adjust depth only; add no facts): {student_context}\n" if student_context else ""
        note = (f"Coverage note: the question uses {', '.join(repr(t) for t in flagged)}, which never appears in the "
                "course material. Answer only if the excerpts truly address it; otherwise set answerable=false.\n"
                if flagged else "")
        raw = self.llm.generate_json(SYSTEM_ANSWER, PROMPT_ANSWER.format(
            question=q, context=ctx, coverage_note=note, excerpts="\n".join(_fmt_excerpt(h.unit) for h in hits)))
        if not isinstance(raw, dict):
            raise LLMError("answer was not a JSON object")
        if raw.get("answerable") is False:
            return self._refuse(base, q, allow_outside)
        raw_claims = raw.get("claims")
        if not isinstance(raw_claims, list):
            raise LLMError("answer did not include a claims list")
        proposed = []
        for c in raw_claims:
            if isinstance(c, dict) and str(c.get("text", "")).strip():
                unit_ids = c.get("unit_ids")
                ids = [i for i in unit_ids if isinstance(i, str) and i in by_id] if isinstance(unit_ids, list) else []
                proposed.append((str(c["text"]).strip(), list(dict.fromkeys(ids))))
        raw_outside = raw.get("outside_knowledge")
        outside = [x.strip() for x in raw_outside if isinstance(x, str) and x.strip()][:2] if (
            allow_outside and isinstance(raw_outside, list)
        ) else []

        verdicts = self._verify(proposed, by_id)
        claims: list[Claim] = []
        for (text, ids), ok in zip(proposed, verdicts):
            if ok:
                claims.append(Claim(text=text, citations=[make_citation(by_id[i]) for i in ids]))
            else:  # unsupported => flagged, never presented as source-backed
                claims.append(Claim(text=text, citations=[], supported=False))
        supported = [c for c in claims if c.supported]
        if not supported:
            return self._refuse(base, q, allow_outside)
        unsupported = [c.text for c in claims if not c.supported]
        status = AnswerStatus.GROUNDED if not unsupported and not outside and not flagged else AnswerStatus.PARTIAL
        message = None
        if flagged:
            message = self._flag_message(flagged, q)
        elif status == AnswerStatus.PARTIAL:
            message = "Parts of this answer could not be verified against your material and are listed as outside knowledge."
        return self._compose(base, supported, outside + unsupported, status, mode="generative",
                             confidence=round(len(supported) / len(claims), 3), message=message)

    # ------------------------------------------------------------------ #
    def _verify(self, proposed: list[tuple[str, list[str]]], by_id: dict[str, ContentUnit]) -> list[bool]:
        out = []
        for text, ids in proposed:
            if not ids:
                out.append(False)
                continue
            src = set()
            for i in ids:
                src |= set(tokenize(by_id[i].searchable_text()))
            toks = [t for t in tokenize(text)]
            out.append(bool(toks) and sum(t in src for t in toks) / len(toks) >= self.min_support)
        if self.verify_with_llm and self.llm is not None and any(out):
            items = "\n\n".join(f"Claim {n}: {t}\nCited excerpts:\n" + "\n".join(_fmt_excerpt(by_id[i]) for i in ids)
                                for n, (t, ids) in enumerate(proposed) if out[n])
            verdict = self.llm.generate_json(SYSTEM_VERIFY, PROMPT_VERIFY.format(items=items))
            entries = verdict.get("verdicts") if isinstance(verdict, dict) else None
            if not isinstance(entries, list):
                raise LLMError("Invalid claim verification response")
            confirmed = {item["i"] for item in entries if isinstance(item, dict)
                         and type(item.get("i")) is int and item.get("supported") is True}
            rejected = {item["i"] for item in entries if isinstance(item, dict)
                        and type(item.get("i")) is int and item.get("supported") is False}
            out = [ok and n in confirmed and n not in rejected for n, ok in enumerate(out)]
        return out

    def info(self) -> dict:
        return {"mode": "generative" if self.llm else "extractive", "llm": getattr(self.llm, "name", None),
                "threshold_strict": self.t_strict, "threshold_permissive": self.t_perm,
                "threshold_in_use": self.t_perm if self.llm else self.t_strict,
                "calibrated": self.calibrated, "verify_with_llm": self.verify_with_llm}

    @staticmethod
    def _compose(base: dict, claims: list[Claim], outside: list[str], status: AnswerStatus, *, mode: str,
                 confidence: float, message: Optional[str]) -> AnswerResponse:
        sources: list[Citation] = []
        index: dict[str, int] = {}
        parts = []
        for c in claims:
            marks = ""
            for cit in c.citations:
                if cit.unit_id not in index:
                    sources.append(cit)
                    index[cit.unit_id] = len(sources)
                marks += f"[{index[cit.unit_id]}]"
            parts.append(f"{c.text} {marks}".strip())
        return AnswerResponse(status=status, claims=claims, outside_knowledge=outside, answer=" ".join(parts),
                              sources=sources, mode=mode, confidence=confidence, message=message, **base)
