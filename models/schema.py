from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Dimension(BaseModel):
    name: Literal["定价", "功能", "用户体验", "市场策略", "性能"]
    indicators: List[str]


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
