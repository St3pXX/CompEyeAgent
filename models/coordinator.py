from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


NodeStatus = Literal["pending", "running", "completed", "failed", "skipped"]
ScratchpadKind = Literal["json", "markdown", "text"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


class DAGNode(BaseModel):
    node_id: str = Field(default_factory=new_id)
    run_id: str
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    agent: str = ""
    status: NodeStatus = "pending"
    depends_on: list[str] = Field(default_factory=list)
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class DAGEdge(BaseModel):
    source: str
    target: str


class DAGView(BaseModel):
    run_id: str
    nodes: list[DAGNode]
    edges: list[DAGEdge]


class ScratchpadItem(BaseModel):
    item_id: str = Field(default_factory=new_id)
    run_id: str
    path: str = Field(min_length=1)
    kind: ScratchpadKind = "json"
    content: str
    content_preview: str = ""
    producer_node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class ScratchpadWriteRequest(BaseModel):
    path: str = Field(min_length=1)
    kind: ScratchpadKind = "json"
    content: str
    producer_node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
