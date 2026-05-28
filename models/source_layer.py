from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


Confidence = Literal["high", "medium", "low"]


class SourceProvider(StrEnum):
    OFFICIAL = "official"
    NEWS = "news"
    BLOG = "blog"
    GITHUB = "github"
    SOCIAL = "social"
    FINANCE = "finance"
    PATENT = "patent"


class RefreshCadence(StrEnum):
    REALTIME = "realtime"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    MANUAL = "manual"


class FetchStatus(StrEnum):
    FETCHED = "fetched"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    DISABLED = "disabled"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class SourceSeed(BaseModel):
    seed_id: str = Field(default_factory=new_id)
    provider: SourceProvider
    competitor: str = Field(min_length=1)
    url: str = Field(min_length=1)
    label: str = ""
    cadence: RefreshCadence = RefreshCadence.DAILY
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class RawDocument(BaseModel):
    document_id: str = Field(default_factory=new_id)
    provider: SourceProvider
    competitor: str = Field(min_length=1)
    url: str = Field(min_length=1)
    title: str = ""
    content: str = ""
    content_hash: str = ""
    fetched_at: str = Field(default_factory=utc_now)
    published_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def fill_content_hash(self) -> "RawDocument":
        if not self.content_hash:
            self.content_hash = hash_content(self.content)
        return self


class EvidenceItem(BaseModel):
    evidence_id: str = Field(default_factory=new_id)
    document_id: str
    provider: SourceProvider
    competitor: str
    dimension: str
    indicator: str = ""
    claim: str
    snippet: str
    url: str
    confidence: Confidence = "medium"
    observed_at: str = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceFetchEvent(BaseModel):
    event_id: int | None = None
    seed_id: str | None = None
    provider: SourceProvider
    url: str
    status: FetchStatus
    message: str = ""
    created_at: str = Field(default_factory=utc_now)
