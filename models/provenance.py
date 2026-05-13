from pydantic import BaseModel
from typing import List, Optional
import uuid


class SourceRef(BaseModel):
    uri: str
    snippet: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None


class Provenance(BaseModel):
    conclusion_id: str = str(uuid.uuid4())
    text: str
    source_references: List[SourceRef] = []
    confidence: float = 1.0
    generated_by: str
    parent_trace_id: Optional[str] = None