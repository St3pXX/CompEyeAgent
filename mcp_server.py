#!/usr/bin/env python3
"""MCP Server for CompEye Agent.

Exposes competitive analysis capabilities as MCP tools for Claude Code,
Codex, and other agent workbenches.

Usage:
    # stdio transport (for Claude Desktop / Claude Code)
    python mcp_server.py

    # HTTP transport (for remote access)
    python mcp_server.py --transport http --port 9000

Configuration in Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "compeye": {
          "command": "python",
          "args": ["mcp_server.py"],
          "env": {
            "MIMO_BASE_URL": "https://api.xiaomimimo.com/v1",
            "MIMO_API_KEY": "sk-xxx"
          }
        }
      }
    }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

# Ensure project root is on the path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config.settings  # noqa: F401 — loads .env and strips proxies

from mcp.server.fastmcp import FastMCP

from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.evidence_service import EvidenceService
from storage.coordinator_store import SQLiteCoordinatorStore
from storage.run_store import SQLiteRunStore
from storage.source_store import SQLiteSourceStore


# ---------------------------------------------------------------------------
# Initialize stores (same as api_app.py but standalone)
# ---------------------------------------------------------------------------

store = SQLiteRunStore()
coordinator_store = SQLiteCoordinatorStore()
coordinator_service = CoordinatorFoundationService(coordinator_store)
source_store = SQLiteSourceStore()
evidence_service = EvidenceService(source_store)

# Lazy-init RunService to avoid circular imports at module level.
_run_service = None


def _get_run_service():
    global _run_service
    if _run_service is None:
        from services.run_service import RunService
        _run_service = RunService(
            store,
            evidence_service=evidence_service,
            coordinator_service=coordinator_service,
        )
    # Verify the cached service still points to the current store.
    if _run_service.store is not store:
        _run_service = None
        return _get_run_service()
    return _run_service


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="compeye",
    instructions=(
        "CompEye Agent — AI 竞品分析工作台。"
        "使用 create_run 发起竞品分析，用 get_run 查看状态，用 get_report 获取报告。"
    ),
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="create_run",
    description="发起一次竞品分析任务。返回 run_id，可用于查询状态和获取报告。",
)
def create_run(
    product_name: str,
    competitors: list[str],
    dimensions: list[dict[str, Any]],
    analysis_type: str = "SWOT",
    allow_retry: bool = True,
) -> str:
    """Create a new competitive analysis run.

    Args:
        product_name: 目标产品名称（如 "飞书"）
        competitors: 竞品列表（如 ["钉钉", "企业微信"]）
        dimensions: 分析维度列表，每项含 name 和 indicators（如 [{"name": "定价", "indicators": ["免费套餐"]}]）
        analysis_type: 分析类型，SWOT / 对比表格 / 综合报告
        allow_retry: 是否允许质检失败后自动重写
    """
    input_data = CompetitorInput(
        productName=product_name,
        competitors=competitors,
        dimensions=[{"name": d["name"], "indicators": d.get("indicators", [])} for d in dimensions],
        analysisType=analysis_type,
    )
    svc = _get_run_service()
    run = svc.create_run(input_data, allow_retry=allow_retry)

    # Execute in background thread (MCP tools run synchronously).
    import threading
    thread = threading.Thread(target=svc.execute_run, args=(run.run_id,), kwargs={"allow_retry": allow_retry}, daemon=True)
    thread.start()

    return json.dumps({
        "run_id": run.run_id,
        "status": run.status,
        "message": f"分析任务已创建，run_id: {run.run_id}。使用 get_run 查询状态。",
    }, ensure_ascii=False)


@mcp.tool(
    name="get_run",
    description="查询分析任务的状态和基本信息。",
)
def get_run(run_id: str) -> str:
    """Get the status and details of an analysis run."""
    try:
        run = store.get_run(run_id)
        events = store.list_events(run_id)
        return json.dumps({
            "run_id": run.run_id,
            "status": run.status,
            "product": run.input.productName,
            "competitors": run.input.competitors,
            "created_at": run.created_at,
            "error": run.error,
            "event_count": len(events),
            "latest_events": [
                {"type": e.type, "message": e.message, "created_at": e.created_at}
                for e in events[-5:]
            ],
        }, ensure_ascii=False)
    except KeyError:
        return json.dumps({"error": f"Run {run_id} not found"})


@mcp.tool(
    name="get_report",
    description="获取分析报告的 Markdown 内容。仅在任务完成后可用。",
)
def get_report(run_id: str) -> str:
    """Get the Markdown report for a completed run."""
    try:
        run = store.get_run(run_id)
        artifacts = store.list_artifacts(run_id)
        report = next((a for a in artifacts if a.kind == "report_markdown"), None)
        if report is None:
            return json.dumps({"error": "报告尚未生成", "status": run.status})
        return json.dumps({
            "run_id": run_id,
            "status": run.status,
            "report": report.content,
        }, ensure_ascii=False)
    except KeyError:
        return json.dumps({"error": f"Run {run_id} not found"})


@mcp.tool(
    name="get_verification",
    description="获取质检结果 JSON（passed、confidence、issues）。",
)
def get_verification(run_id: str) -> str:
    """Get the verifier result for a completed run."""
    try:
        artifacts = store.list_artifacts(run_id)
        verifier = next((a for a in artifacts if a.kind == "verifier_json"), None)
        if verifier is None:
            return json.dumps({"error": "质检结果尚未生成"})
        return json.dumps({
            "run_id": run_id,
            "verification": json.loads(verifier.content),
        }, ensure_ascii=False)
    except (KeyError, json.JSONDecodeError) as e:
        return json.dumps({"error": str(e)})


@mcp.tool(
    name="list_runs",
    description="列出最近的分析任务。",
)
def list_runs(limit: int = 10) -> str:
    """List recent analysis runs."""
    runs = store.list_runs(limit=limit)
    return json.dumps({
        "runs": [
            {
                "run_id": r.run_id,
                "product": r.input.productName,
                "competitors": r.input.competitors,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in runs
        ]
    }, ensure_ascii=False)


@mcp.tool(
    name="get_sources",
    description="获取分析报告的来源引用列表。",
)
def get_sources(run_id: str) -> str:
    """Get source references for a completed run."""
    try:
        sources = store.list_sources(run_id)
        return json.dumps({
            "run_id": run_id,
            "sources": [
                {"uri": s.uri, "snippet": s.snippet[:200], "confidence": s.confidence}
                for s in sources
            ],
        }, ensure_ascii=False)
    except KeyError:
        return json.dumps({"error": f"Run {run_id} not found"})


@mcp.tool(
    name="get_scratchpad",
    description="获取中间产物（Scratchpad 内容）。",
)
def get_scratchpad(run_id: str) -> str:
    """Get scratchpad items for a run."""
    try:
        store.get_run(run_id)
        items = coordinator_service.list_scratchpad(run_id)
        return json.dumps({
            "run_id": run_id,
            "items": [
                {"path": i.path, "kind": i.kind, "preview": i.content_preview}
                for i in items
            ],
        }, ensure_ascii=False)
    except KeyError:
        return json.dumps({"error": f"Run {run_id} not found"})


@mcp.tool(
    name="cancel_run",
    description="取消一个正在运行的分析任务。",
)
def cancel_run(run_id: str) -> str:
    """Cancel a running analysis."""
    try:
        run = _get_run_service().cancel_run(run_id)
        return json.dumps({"run_id": run_id, "status": run.status, "message": "任务已取消"})
    except KeyError:
        return json.dumps({"error": f"Run {run_id} not found"})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="CompEye Agent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
