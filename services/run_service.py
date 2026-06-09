"""Application service for creating and executing analysis runs."""

from __future__ import annotations

import json
from typing import Any

from models.schema import CompetitorInput, RunRecord
from services.coordinator_foundation import CoordinatorFoundationService
from services.coordinator_loop import CoordinatorLoopService
from services.evidence_service import DEFAULT_EVIDENCE_INDEX, EvidenceService
from services.event_bus import EventBus
from services.source_indexer import extract_source_references
from storage.protocols import RunStoreProtocol


STAGE_AGENT = {
    "collect": "Collector",
    "analyze": "Analyzer",
    "write": "Writer",
    "verify": "Verifier",
    "rewrite": "Writer",
    "final": "Coordinator",
}


class RunService:
    def __init__(
        self,
        store: RunStoreProtocol,
        evidence_service: EvidenceService | None = None,
        coordinator_service: CoordinatorFoundationService | None = None,
        memory_service: Any | None = None,
    ) -> None:
        self.store = store
        self.evidence_service = evidence_service
        self.coordinator_service = coordinator_service
        self.memory_service = memory_service
        self.coordinator_loop = CoordinatorLoopService(store, coordinator_service) if coordinator_service else None

    def create_run(self, input_data: CompetitorInput, *, allow_retry: bool = True) -> RunRecord:
        run = self.store.create_run(input_data.model_dump())
        if self.coordinator_service is not None:
            self.coordinator_service.ensure_default_dag(run.run_id, input_data.model_dump())
        self.store.append_event(
            run.run_id,
            "run.created",
            "分析任务已创建",
            agent="Coordinator",
            payload={"allow_retry": allow_retry},
        )
        return run

    def execute_run(self, run_id: str, *, allow_retry: bool = True, event_bus: EventBus | None = None) -> None:
        run = self.store.get_run(run_id)
        from runner import run_analysis

        if self.coordinator_loop is not None:
            self._execute_with_coordinator(run_id, run, allow_retry, run_analysis, event_bus=event_bus)
            return

        self._execute_legacy(run_id, allow_retry=allow_retry, run_analysis=run_analysis)

    def _execute_with_coordinator(
        self, run_id: str, run: RunRecord, allow_retry: bool, run_analysis: Any, *, event_bus: EventBus | None = None,
    ) -> None:
        from services.node_executors import per_node_executor

        # Query long-term memory for relevant historical facts.
        memory_context = ""
        if self.memory_service is not None:
            competitors = [run.input.productName, *run.input.competitors]
            dimensions = [d.name for d in run.input.dimensions]
            memory_context = self.memory_service.query_for_run(competitors, dimensions)

        self.coordinator_loop.execute(
            run_id,
            input_data=run.input,
            allow_retry=allow_retry,
            evidence_index=self._evidence_index_for_input(run.input),
            run_analysis=run_analysis,
            node_executor=per_node_executor,
            event_bus=event_bus,
            memory_context=memory_context,
        )

        # After successful completion, ingest facts into long-term memory.
        if self.memory_service is not None:
            try:
                completed_run = self.store.get_run(run_id)
                if completed_run.status in ("passed", "needs_review"):
                    self.memory_service.ingest_completed_run(run_id)
            except Exception:
                pass  # non-fatal

    def _execute_legacy(self, run_id: str, *, allow_retry: bool, run_analysis: Any) -> None:
        run = self.store.get_run(run_id)
        if run.status == "cancelled":
            return
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
            result = run_analysis(
                {**run.input.model_dump(), "evidenceIndex": self._evidence_index_for_input(run.input)},
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
            self.store.append_event(run_id, "run.completed", "分析任务已完成", agent="Coordinator", payload={"status": status})
        except Exception as exc:
            self.store.update_run_status(run_id, "failed", error=str(exc), completed=True)
            self.store.append_event(run_id, "run.failed", f"分析任务执行失败：{exc}", agent="Coordinator")

    def retry_run(self, run_id: str) -> RunRecord:
        previous = self.store.get_run(run_id)
        retry = self.store.create_run(previous.input.model_dump(), parent_run_id=run_id)
        if self.coordinator_service is not None:
            self.coordinator_service.ensure_default_dag(retry.run_id, previous.input.model_dump())
        self.store.append_event(
            retry.run_id,
            "run.created",
            "重试任务已创建",
            agent="Coordinator",
            payload={"parent_run_id": run_id},
        )
        return retry

    def retry_node(self, run_id: str, node_key: str, *, allow_retry: bool = True, event_bus: EventBus | None = None) -> RunRecord:
        run = self.store.get_run(run_id)
        if self.coordinator_loop is None:
            raise RuntimeError("Coordinator loop is not configured")

        from runner import run_analysis
        from services.node_executors import per_node_executor

        self.coordinator_loop.retry_node(
            run_id,
            node_key,
            input_data=run.input,
            allow_retry=allow_retry,
            evidence_index=self._evidence_index_for_input(run.input),
            run_analysis=run_analysis,
            node_executor=per_node_executor,
            event_bus=event_bus,
        )
        return self.store.get_run(run_id)

    def cancel_run(self, run_id: str) -> RunRecord:
        run = self.store.update_run_status(run_id, "cancelled", completed=True)
        self.store.append_event(run_id, "run.cancelled", "分析任务已标记为取消", agent="Coordinator")
        return run

    def empty_extension_payload(self, run_id: str, kind: str) -> dict[str, Any]:
        self.store.get_run(run_id)
        return {"run_id": run_id, "kind": kind, "items": []}

    def _evidence_index_for_input(self, input_data: CompetitorInput) -> str:
        if self.evidence_service is None:
            return DEFAULT_EVIDENCE_INDEX

        dimensions = [dimension.name for dimension in input_data.dimensions]
        competitors = [input_data.productName, *input_data.competitors]
        evidence = []
        seen_ids: set[str] = set()
        for competitor in competitors:
            for item in self.evidence_service.query_evidence(competitor, dimensions):
                if item.evidence_id in seen_ids:
                    continue
                seen_ids.add(item.evidence_id)
                evidence.append(item)
        return self.evidence_service.format_evidence_for_prompt(evidence)
