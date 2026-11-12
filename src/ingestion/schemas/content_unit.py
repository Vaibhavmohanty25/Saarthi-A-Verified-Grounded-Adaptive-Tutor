from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ContentUnit(BaseModel):

    unit_id: str

    source_id: str
    source_type: str

    location: Dict[str, Any]

    chunk_index: Optional[int] = None

    content_type: str = "text"

    text: str
    slide_title: Optional[str] = None

    visual_description: Optional[str] = None
    image_path: Optional[str] = None

    topic: Optional[str] = None
    subtopic: Optional[str] = None

    concept_ids: List[str] = Field(
        default_factory=list
    )

    embedding: Optional[List[float]] = None
