"""Assemble the CompEye analysis StateGraph.

Edges:  collect -> analyze -> write -> verify
verify --(issues & not yet retried)--> rewrite -> verify
verify --(passed OR already retried)--> END

An optional SqliteSaver checkpointer gives durable, resumable runs (thread_id =
run_id) and backs single-node retry.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from langgraph.graph import END, START, StateGraph

from graph.nodes import (
    analyze_node,
    collect_node,
    rewrite_node,
    verify_node,
    write_node,
)
from graph.state import AnalysisState

# Max number of automatic rewrite passes (matches legacy "rewrite once").
MAX_RETRIES = 1

DEFAULT_CHECKPOINT_PATH = os.getenv(
    "COMPETEYE_CHECKPOINT_PATH", "data/graph_checkpoints.sqlite3"
)


def _route_after_verify(state: AnalysisState) -> str:
    """Route to rewrite when verification failed and we haven't retried yet."""
    issues = state.get("issues", [])
    allow_retry = state.get("allow_retry", True)
    retry_count = state.get("retry_count", 0)
    if issues and allow_retry and retry_count < MAX_RETRIES:
        return "rewrite"
    return END


def build_graph(*, checkpointer: Any | None = None):
    """Build and compile the analysis graph.

    Pass ``checkpointer`` to enable durable/resumable runs; omit for a plain
    in-memory compile (useful in tests).
    """
    builder = StateGraph(AnalysisState)

    builder.add_node("collect", collect_node)
    builder.add_node("analyze", analyze_node)
    builder.add_node("write", write_node)
    builder.add_node("verify", verify_node)
    builder.add_node("rewrite", rewrite_node)

    builder.add_edge(START, "collect")
    builder.add_edge("collect", "analyze")
    builder.add_edge("analyze", "write")
    builder.add_edge("write", "verify")
    builder.add_conditional_edges("verify", _route_after_verify, ["rewrite", END])
    builder.add_edge("rewrite", "verify")

    return builder.compile(checkpointer=checkpointer)


def create_sqlite_checkpointer(path: str | None = None):
    """Create a long-lived SqliteSaver checkpointer at *path*.

    Returns the SqliteSaver instance.  Uses a single shared connection with
    ``check_same_thread=False`` since LangGraph may touch it across threads.
    """
    from langgraph.checkpoint.sqlite import SqliteSaver

    db_path = path or DEFAULT_CHECKPOINT_PATH
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)
