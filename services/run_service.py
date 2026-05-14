"""Application service for creating and executing analysis runs."""

from __future__ import annotations

import json
from typing import Any

from models.schema import CompetitorInput, RunRecord
from storage.run_store import SQLiteRunStore
from services.source_indexer import extract_source_references


STAGE_AGENT = {
    "collect": "Collector",
    "analyze": "Analyzer",
    "write": "Writer",
    "verify": "Verifier",
    "rewrite": "Writer",
    "final": "Coordinator",
}


class RunService:
    def __init__(self, store: SQLiteRunStore) -> None:
        self.store = store

    def create_run(self, input_data: CompetitorInput, *, allow_retry: bool = True) -> RunRecord:
        run = self.store.create_run(input_data.model_dump())
        self.store.append_event(
            run.run_id,
            "run.created",
            "分析任务已创建",
            agent="Coordinator",
            payload={"allow_retry": allow_retry},
        )
        return run

    def execute_run(self, run_id: str, *, allow_retry: bool = True) -> None:
        run = self.store.get_run(run_id)
        self.store.update_run_status(run_id, "running")
        self.store.append_event(run_id, "run.started", "分析任务开始执行", agent="Coordinator")

        def progress_callback(stage: str, message: str) -> None:
            self.store.append_event(
                run_id,
                "agent.progress",
                message,
                agent=STAGE_AGENT.get(stage, "Agent"),
                stage=stage,
            )

        try:
            from runner import run_analysis

            result = run_analysis(
                run.input.model_dump(),
                allow_retry=allow_retry,
                progress_callback=progress_callback,
            )
            status = "passed" if result.passed else "needs_review"
            self.store.create_artifact(run_id, "brief_json", json.dumps(run.input.model_dump(), ensure_ascii=False, indent=2))
            self.store.create_artifact(run_id, "report_markdown", result.report)
            self.store.create_artifact(run_id, "verifier_json", result.verifier_result)
            sources = extract_source_references(result.report)
            self.store.create_sources(run_id, sources)
            self.store.create_artifact(
                run_id,
                "provenance_index",
                json.dumps([source.model_dump() for source in sources], ensure_ascii=False, indent=2),
            )
            self.store.append_event(
                run_id,
                "artifact.ready",
                "报告、质检结果和输入 brief 已生成",
                agent="Coordinator",
                payload={"passed": result.passed, "retried": result.retried, "source_count": len(sources)},
            )
            self.store.update_run_status(run_id, status, completed=True)
            self.store.append_event(
                run_id,
                "run.completed",
                "分析任务已完成" if result.passed else "分析任务完成，但需要复核",
                agent="Coordinator",
                payload={"status": status},
            )
        except Exception as exc:
            self.store.update_run_status(run_id, "failed", error=str(exc), completed=True)
            self.store.append_event(
                run_id,
                "run.failed",
                f"分析任务执行失败：{exc}",
                agent="Coordinator",
                payload={"error_type": type(exc).__name__},
            )

    def retry_run(self, run_id: str) -> RunRecord:
        previous = self.store.get_run(run_id)
        retry = self.store.create_run(previous.input.model_dump(), parent_run_id=run_id)
        self.store.append_event(
            retry.run_id,
            "run.created",
            "重试任务已创建",
            agent="Coordinator",
            payload={"parent_run_id": run_id},
        )
        return retry

    def cancel_run(self, run_id: str) -> RunRecord:
        run = self.store.update_run_status(run_id, "cancelled", completed=True)
        self.store.append_event(run_id, "run.cancelled", "分析任务已标记为取消", agent="Coordinator")
        return run

    def empty_extension_payload(self, run_id: str, kind: str) -> dict[str, Any]:
        self.store.get_run(run_id)
        return {"run_id": run_id, "kind": kind, "items": []}
