"""Shared data contracts for Saarthi (Pod B's view).

Frozen shapes from the team plan (section 2.23): ContentUnit, ConceptNode, Question.
Pod B adds, non-breakingly:
  * Topic            - topic/subtopic hierarchy (reqs 1b, 1c)
  * PrereqEdge       - detail behind ConceptNode.prerequisites (kept as list[str] for Pod C)
  * Citation/Answer  - what the tutor returns, so Pod D can render chips
Question is owned by Pod C and intentionally not defined here.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

SourceType = Literal["video", "pdf", "slides"]


# --------------------------------------------------------------------------- #
# Location: where in the source a unit lives. Exactly one anchor must be set.
# --------------------------------------------------------------------------- #
class Location(BaseModel):
    page: Optional[int] = Field(None, ge=1, description="PDF/textbook page (1-based)")
    slide: Optional[int] = Field(None, ge=1, description="Slide number (1-based)")
    t_start: Optional[float] = Field(None, ge=0, description="Video start, seconds")
    t_end: Optional[float] = Field(None, ge=0, description="Video end, seconds")
    figure_id: Optional[str] = Field(None, description="Set when the unit is a figure/diagram")

    @model_validator(mode="after")
    def _exactly_one_anchor(self) -> "Location":
        anchors = [self.page is not None, self.slide is not None, self.t_start is not None]
        if sum(anchors) != 1:
            raise ValueError("Location needs exactly one of: page, slide, t_start")
        if self.t_end is not None and self.t_start is None:
            raise ValueError("t_end requires t_start")
        if self.t_end is not None and self.t_start is not None and self.t_end < self.t_start:
            raise ValueError("t_end must be >= t_start")
        return self

    @property
    def kind(self) -> SourceType:
        if self.page is not None:
            return "pdf"
        if self.slide is not None:
            return "slides"
        return "video"

    def label(self) -> str:
        """Human-readable anchor, e.g. 'Slide 14', 'p. 212', '@12:41'."""
        if self.slide is not None:
            return f"Slide {self.slide}"
        if self.page is not None:
            return f"p. {self.page}"
        secs = int(self.t_start or 0)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"@{h}:{m:02d}:{s:02d}" if h else f"@{m}:{s:02d}"

    def open_url(self, source_id: str) -> str:
        """Deep link the frontend (Pod D) resolves to the exact page/slide/timestamp."""
        if self.slide is not None:
            return f"/sources/{source_id}#slide={self.slide}"
        if self.page is not None:
            return f"/sources/{source_id}#page={self.page}"
        return f"/sources/{source_id}?t={int(self.t_start or 0)}"


# --------------------------------------------------------------------------- #
# 1. Content Unit (frozen) - one chunk of source material. Produced by Pod A.
# --------------------------------------------------------------------------- #
class ContentUnit(BaseModel):
    unit_id: str
    source_id: str
    source_type: SourceType
    location: Location
    text: str = Field(..., min_length=1)
    slide_title: Optional[str] = None
    image_caption: Optional[str] = None
    embedding: Optional[list[float]] = None  # filled by Pod A
    topic_ids: list[str] = Field(default_factory=list)  # back-filled by Pod B (concept's topic + ancestors)
    concept_ids: list[str] = Field(default_factory=list)  # back-filled by Pod B (Pod B addition)

    @model_validator(mode="after")
    def _source_type_matches_location(self) -> "ContentUnit":
        if self.location.kind != self.source_type:
            raise ValueError(
                f"source_type={self.source_type!r} but location is a {self.location.kind!r} anchor"
            )
        return self

    def searchable_text(self) -> str:
        """Text that retrieval indexes: body plus any figure caption."""
        return f"{self.text}\n{self.image_caption}" if self.image_caption else self.text


# --------------------------------------------------------------------------- #
# Topic hierarchy (Pod B addition)
# --------------------------------------------------------------------------- #
class Topic(BaseModel):
    topic_id: str
    name: str
    parent_topic_id: Optional[str] = None  # None => major topic


# --------------------------------------------------------------------------- #
# 2. Concept Node (frozen) + edge detail (Pod B addition)
# --------------------------------------------------------------------------- #
class PrereqEdge(BaseModel):
    concept_id: str  # the prerequisite concept
    confidence: float = Field(1.0, ge=0, le=1)
    validated: bool = False  # True only after the evidence check passes
    evidence_units: list[str] = Field(default_factory=list)
    llm_confidence: Optional[float] = Field(None, ge=0, le=1)  # the proposer's own confidence, kept for audit
    signals: list[str] = Field(default_factory=list)  # why it was (not) validated: 'mention', 'order', 'contradicted'


class ConceptNode(BaseModel):
    concept_id: str
    name: str
    topic: str  # topic_id (frozen field name kept)
    prerequisites: list[str] = Field(default_factory=list)  # frozen shape, for Pod C
    evidence_units: list[str] = Field(default_factory=list)
    # --- Pod B additions (all optional, non-breaking) ---
    definition: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    prerequisite_edges: list[PrereqEdge] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Tutor answer contract (Pod B -> Pod D)
# --------------------------------------------------------------------------- #
class AnswerStatus(str, Enum):
    GROUNDED = "grounded"  # fully supported by the course material
    PARTIAL = "partial"  # some claims supported; outside knowledge flagged
    REFUSED = "refused"  # material does not cover the question


class Citation(BaseModel):
    unit_id: str
    source_id: str
    location: Location
    label: str  # e.g. "Slide 14"
    excerpt: str
    open_url: str


class Claim(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)
    supported: bool = True  # False => must be rendered as outside knowledge


class AnswerResponse(BaseModel):
    status: AnswerStatus
    question: str
    claims: list[Claim] = Field(default_factory=list)
    outside_knowledge: list[str] = Field(default_factory=list)
    message: Optional[str] = None  # e.g. the refusal text
    confidence: Optional[float] = Field(None, ge=0, le=1)  # generative: share of claims verified; extractive: top relevance
    # --- additions so Pod D can render and Pod D's eval can score without re-running retrieval ---
    answer: Optional[str] = None  # claims joined, with [n] markers pointing into `sources`
    sources: list[Citation] = Field(default_factory=list)  # de-duplicated, numbered from 1 in `answer`
    mode: Optional[str] = None  # 'generative' | 'extractive' | 'refusal'
    retrieved: list[str] = Field(default_factory=list)  # unit_ids the generator saw (RAGAS 'contexts')
    standalone_question: Optional[str] = None  # follow-up rewritten to stand alone (== question if not needed)


def make_citation(unit: ContentUnit, excerpt: Optional[str] = None) -> Citation:
    """Build a Citation from a unit so label/open_url can never drift from location."""
    return Citation(
        unit_id=unit.unit_id,
        source_id=unit.source_id,
        location=unit.location,
        label=unit.location.label(),
        excerpt=(excerpt or unit.text)[:300],
        open_url=unit.location.open_url(unit.source_id),
    )
