"""
Saarthi Shared Data Contracts (Frozen Schema)
Single Source of Truth for all 4 Pods:
- Pod A: Ingestion & Multimodal Extraction
- Pod B: Concept Graph, Retrieval & Grounding
- Pod C: Assessment & Learner Model
- Pod D: Frontend, Evaluation & Integration
"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


class SourceLocation(BaseModel):
    page: Optional[int] = Field(None, description="Page number for PDF documents")
    slide: Optional[int] = Field(None, description="Slide number for presentation decks")
    timestamp: Optional[str] = Field(None, description="MM:SS or HH:MM:SS timestamp for lecture videos")


class ContentUnit(BaseModel):
    """
    Atomic chunk of ingested multimodal course material (produced by Pod A).
    """
    unit_id: str = Field(..., description="Unique content unit identifier")
    source_id: str = Field(..., description="Source identifier e.g. filename or video title")
    source_type: Literal["video", "pdf", "slides"] = Field(..., description="Modality of origin")
    location: SourceLocation = Field(..., description="Exact location within source material")
    text: str = Field(..., description="Extracted text or transcription segment")
    image_caption: Optional[str] = Field(None, description="Structured description of diagrams/figures via vision model")
    embedding: Optional[List[float]] = Field(None, description="Dense embedding vector")
    topic_ids: List[str] = Field(default_factory=list, description="Associated high-level topic tags")


class ConceptNode(BaseModel):
    """
    Pedagogical concept node within the prerequisite knowledge graph (produced by Pod B).
    """
    concept_id: str = Field(..., description="Unique concept identifier e.g. 'concept_gradient_descent'")
    name: str = Field(..., description="Human-readable concept name e.g. 'Gradient Descent'")
    topic: str = Field(..., description="Parent topic category e.g. 'Optimization'")
    prerequisites: List[str] = Field(
        default_factory=list,
        description="IDs of concepts that must be mastered before this concept"
    )
    evidence_units: List[str] = Field(
        default_factory=list,
        description="List of ContentUnit IDs supporting/teaching this concept"
    )


class Question(BaseModel):
    """
    Verified assessment item (produced by Pod C).
    """
    q_id: str = Field(..., description="Unique question identifier")
    concept_id: Optional[str] = Field(None, description="Concept identifier for uploaded courses")
    source_unit_id: Optional[str] = Field(None, description="Exact evidence unit for uploaded courses")
    topic: str = Field(..., description="Topic or concept identifier")
    source_location: SourceLocation = Field(..., description="Exact origin in course material")
    difficulty: int = Field(..., ge=1, le=5, description="Difficulty level rated 1 to 5")
    type: Literal["mcq", "short", "numeric"] = Field(..., description="Format of the question")
    stem: str = Field(..., description="Question stem / prompt")
    options: Optional[List[str]] = Field(None, description="List of choices for MCQ questions")
    answer: str = Field(..., description="Verified correct answer string or formula")
    explanation: Optional[str] = Field(None, description="Cited explanation for pedagogical feedback")
    verified: bool = Field(False, description="Whether question passed dual-LLM + Python calculation checks")
    verifier_agreement: float = Field(0.0, ge=0.0, le=1.0, description="Verification confidence score")
    embedding: Optional[List[float]] = Field(None, description="Embedding vector for deduplication checks")


class LearnerState(BaseModel):
    """
    Student mastery model maintained via Bayesian Knowledge Tracing (maintained by Pod C).
    """
    student_id: str = Field(..., description="Unique student ID")
    concept_mastery: Dict[str, float] = Field(
        default_factory=dict,
        description="Map of concept_id -> P(Mastery) bounded in [0.0, 1.0]"
    )
    history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Sequential list of assessment interactions"
    )
    diagnostic_completed: bool = Field(False, description="Whether cold-start diagnostic quiz was finished")
