"""Coordinator main loop for executing a run through DAG-backed state."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.source_indexer import extract_source_references
from storage.run_store import SQLiteRunStore


STAGE_AGENT = {
    "collect": "Collector",
    "analyze": "Analyzer",
    "write": "Writer",
    "verify": "Verifier",
    "rewrite": "Writer",
    "final": "Coordinator",
}


class CoordinatorLoopService:
    """Owns run execution state while the existing CrewAI chain remains the executor."""

    def __init__(self, run_store: SQLiteRunStore, foundation: CoordinatorFoundationService) -> None:
        self.run_store = run_store
        self.foundation = foundation

    def execute(
        self,
        run_id: str,
        *,
        input_data: CompetitorInput,
        allow_retry: bool,
        evidence_index: str,
        run_analysis: Callable[..., Any],
    ) -> None:
        run = self.run_store.get_run(run_id)
        if run.status == "cancelled":
            return

        self.foundation.ensure_default_dag(run_id, input_data.model_dump())
        self.run_store.update_run_status(run_id, "running")
        self.run_store.append_event(run_id, "run.started", "Coordinator 主循环开始执行", agent="Coordinator")

        def progress_callback(stage: str, message: str) -> None:
            self.foundation.mark_stage_running(run_id, stage)
            self.run_store.append_event(
                run_id,
                "agent.progress",
                message,
                agent=STAGE_AGENT.get(stage, "Agent"),
                stage=stage,
            )

        try:
            run_inputs = input_data.model_dump()
            run_inputs.setdefault("evidenceIndex", evidence_index)
            result = run_analysis(
                run_inputs,
                allow_retry=allow_retry,
                progress_callback=progress_callback,
            )
            self._persist_success(run_id, input_data, result)
        except Exception as exc:
            self.run_store.update_run_status(run_id, "failed", error=str(exc), completed=True)
            self.foundation.mark_run_failed(run_id)
            self.run_store.append_event(
                run_id,
                "run.failed",
                f"Coordinator 主循环执行失败：{exc}",
                agent="Coordinator",
                payload={"error_type": type(exc).__name__},
            )

    def _persist_success(self, run_id: str, input_data: CompetitorInput, result: Any) -> None:
        status = "passed" if result.passed else "needs_review"
        self.run_store.create_artifact(run_id, "brief_json", json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2))
        self.run_store.create_artifact(run_id, "report_markdown", result.report)
        self.run_store.create_artifact(run_id, "verifier_json", result.verifier_result)
        sources = extract_source_references(result.report)
        self.run_store.create_sources(run_id, sources)
        provenance_index = json.dumps([source.model_dump() for source in sources], ensure_ascii=False, indent=2)
        self.run_store.create_artifact(run_id, "provenance_index", provenance_index)
        self.foundation.record_execution_outputs(
            run_id,
            report_markdown=result.report,
            verifier_json=result.verifier_result,
            provenance_json=provenance_index,
            stage_outputs=getattr(result, "scratchpad_outputs", {}),
        )
        self.run_store.append_event(
            run_id,
            "artifact.ready",
            "报告、质检结果和 Scratchpad 产物已生成",
            agent="Coordinator",
            payload={"passed": result.passed, "retried": result.retried, "source_count": len(sources)},
        )
        self.run_store.update_run_status(run_id, status, completed=True)
        self.foundation.mark_run_finished(run_id, passed=result.passed)
        self.run_store.append_event(
            run_id,
            "run.completed",
            "分析任务已完成" if result.passed else "分析任务完成，但需要复核",
            agent="Coordinator",
            payload={"status": status},
        )
