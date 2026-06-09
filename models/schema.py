from pydantic import BaseModel, Field
from typing import Any, List, Literal, Optional


class Dimension(BaseModel):
    name: str = Field(min_length=1)
    indicators: List[str] = Field(default_factory=list)


class CompetitorInput(BaseModel):
    productName: str
    competitors: List[str]
    dimensions: List[Dimension]
    analysisType: Literal["SWOT", "对比表格", "综合报告"] = "SWOT"


class SourceReference(BaseModel):
    uri: str
    snippet: str
    retrieved_at: Optional[str] = None


class Evidence(BaseModel):
    competitor: str
    dimension: str
    indicator: str
    summary: str
    source_references: List[SourceReference] = Field(default_factory=list)


class Claim(BaseModel):
    text: str
    competitor: Optional[str] = None
    dimension: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    source_references: List[SourceReference] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"


class AnalysisFinding(BaseModel):
    section: Literal["strengths", "weaknesses", "opportunities", "threats", "comparison"]
    claim: Claim


class VerificationIssue(BaseModel):
    type: Literal["missing_evidence", "logic_conflict", "hallucination", "missing_dimension", "format_issue"]
    description: str
    suggested_action: str


class ReportArtifact(BaseModel):
    markdown: str
    claims: List[Claim] = Field(default_factory=list)
    verification_issues: List[VerificationIssue] = Field(default_factory=list)


RunStatus = Literal["queued", "running", "passed", "needs_review", "failed", "cancelled"]
ReviewStatus = Literal["pending", "in_review", "approved", "rejected"]
EventType = Literal[
    "run.created",
    "run.started",
    "agent.started",
    "agent.progress",
    "agent.completed",
    "agent.retrying",
    "verifier.issue",
    "artifact.ready",
    "run.completed",
    "run.failed",
    "run.cancelled",
]
ArtifactKind = Literal["report_markdown", "verifier_json", "brief_json", "provenance_index"]


class RunRecord(BaseModel):
    run_id: str
    input: CompetitorInput
    status: RunStatus
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    parent_run_id: Optional[str] = None


class AgentEvent(BaseModel):
    event_id: int
    run_id: str
    type: EventType
    agent: Optional[str] = None
    stage: Optional[str] = None
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ArtifactRecord(BaseModel):
    artifact_id: str
    run_id: str
    kind: ArtifactKind
    content: str
    content_preview: str
    created_at: str


class SourceRecord(BaseModel):
    source_id: str
    run_id: str
    conclusion_id: Optional[str] = None
    uri: str
    snippet: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    retrieved_at: Optional[str] = None


class ReviewItem(BaseModel):
    review_id: str
    run_id: str
    status: ReviewStatus = "pending"
    issues: List[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None
    review_notes: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    reviewed_at: Optional[str] = None


class CreateRunRequest(BaseModel):
    input: CompetitorInput
    allow_retry: bool = True


class CreateRunResponse(BaseModel):
    run: RunRecord


class RunDetailResponse(BaseModel):
    run: RunRecord
    events: List[AgentEvent] = Field(default_factory=list)
    artifacts: List[ArtifactRecord] = Field(default_factory=list)
    sources: List[SourceRecord] = Field(default_factory=list)
