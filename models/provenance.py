from pydantic import BaseModel
from pydantic import Field
from typing import List, Optional
import uuid


class SourceRef(BaseModel):
    uri: str
    snippet: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class Provenance(BaseModel):
    conclusion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    source_references: List[SourceRef] = Field(default_factory=list)
    confidence: float = 1.0
    generated_by: str
    parent_trace_id: Optional[str] = None
