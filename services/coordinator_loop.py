"""Coordinator main loop for executing a run through DAG-backed state."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from models.coordinator import AssembledResult, DAGNode, NodeExecutionResult
from models.schema import CompetitorInput
from services.coordinator_foundation import CoordinatorFoundationService
from services.source_indexer import extract_source_references
from services.verification import verification_issues
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
        node_executor: Callable[..., NodeExecutionResult] | None = None,
    ) -> None:
        run = self.run_store.get_run(run_id)
        if run.status == "cancelled":
            return

        self.foundation.ensure_default_dag(run_id, input_data.model_dump())
        self.run_store.update_run_status(run_id, "running")
        self.run_store.append_event(run_id, "run.started", "Coordinator 主循环开始执行", agent="Coordinator")

        try:
            result = self._execute_dag(
                run_id,
                input_data=input_data,
                allow_retry=allow_retry,
                evidence_index=evidence_index,
                run_analysis=run_analysis,
                node_executor=node_executor,
            )
            self._persist_success(run_id, input_data, result)
        except Exception as exc:
            self.run_store.update_run_status(run_id, "failed", error=str(exc), completed=True)
            self.run_store.append_event(
                run_id,
                "run.failed",
                f"Coordinator 主循环执行失败：{exc}",
                agent="Coordinator",
                payload={"error_type": type(exc).__name__},
            )

    def retry_node(
        self,
        run_id: str,
        node_key: str,
        *,
        input_data: CompetitorInput,
        allow_retry: bool,
        evidence_index: str,
        run_analysis: Callable[..., Any],
        node_executor: Callable[..., NodeExecutionResult] | None = None,
    ) -> None:
        self.run_store.get_run(run_id)
        self.foundation.reset_node_for_retry(run_id, node_key)
        self.run_store.update_run_status(run_id, "running")
        self.run_store.append_event(
            run_id,
            "agent.retrying",
            f"正在重试 DAG 节点：{node_key}",
            agent="Coordinator",
            stage=node_key,
        )
        self.execute(
            run_id,
            input_data=input_data,
            allow_retry=allow_retry,
            evidence_index=evidence_index,
            run_analysis=run_analysis,
            node_executor=node_executor,
        )

    def _execute_dag(
        self,
        run_id: str,
        *,
        input_data: CompetitorInput,
        allow_retry: bool,
        evidence_index: str,
        run_analysis: Callable[..., Any],
        node_executor: Callable[..., NodeExecutionResult] | None,
    ) -> Any:
        executor = node_executor or self._legacy_chain_node_executor(run_analysis)
        context: dict[str, Any] = {
            "input_data": input_data,
            "allow_retry": allow_retry,
            "evidence_index": evidence_index,
            "final_result": None,
        }

        while True:
            run = self.run_store.get_run(run_id)
            if run.status == "cancelled":
                raise RuntimeError("Run was cancelled")

            nodes = self.foundation.get_dag(run_id).nodes
            failed = [node for node in nodes if node.status == "failed"]
            if failed:
                raise RuntimeError(f"DAG node failed: {failed[0].key}")

            if all(node.status in {"completed", "skipped"} for node in nodes):
                # If executor already set final_result (legacy path), use it.
                result = context.get("final_result")
                if result is not None:
                    return result
                # Per-node path: assemble result from scratchpad items.
                return self._assemble_from_scratchpad(run_id, input_data)

            ready = _ready_nodes(nodes)
            if not ready:
                raise RuntimeError("No runnable DAG node found")

            for node in ready:
                result = self._execute_node_with_retry(run_id, node, executor, context)
                if result.final_result is not None:
                    context["final_result"] = result.final_result

    def _execute_node_with_retry(
        self,
        run_id: str,
        node: DAGNode,
        executor: Callable[..., NodeExecutionResult],
        context: dict[str, Any],
    ) -> NodeExecutionResult:
        max_retries = int(node.metadata.get("max_retries", 1))
        attempts = int(node.metadata.get("retry_attempts", 0))
        while True:
            attempts += 1
            self.foundation.update_node_metadata(run_id, node.key, {"retry_attempts": attempts})
            self.foundation.store.update_node_status(run_id, node.key, "running")
            self.run_store.append_event(
                run_id,
                "agent.started",
                f"{node.agent or node.key} 节点开始执行",
                agent=node.agent or STAGE_AGENT.get(node.key, "Agent"),
                stage=node.key,
                payload={"attempt": attempts, "max_retries": max_retries},
            )
            try:
                result = executor(
                    run_id=run_id,
                    node=node,
                    context=context,
                    progress_callback=self._progress_callback(run_id),
                    foundation=self.foundation,
                )
                self.foundation.record_stage_outputs(run_id, result.scratchpad_outputs)
                if result.output_refs:
                    current = self.foundation.store.get_node(run_id, node.key)
                    output_refs = [*current.output_refs]
                    for ref in result.output_refs:
                        if ref not in output_refs:
                            output_refs.append(ref)
                    self.foundation.store.update_node_refs(run_id, node.key, output_refs=output_refs)
                self.foundation.store.update_node_status(run_id, node.key, "completed")
                self.run_store.append_event(
                    run_id,
                    "agent.completed",
                    f"{node.agent or node.key} 节点执行完成",
                    agent=node.agent or STAGE_AGENT.get(node.key, "Agent"),
                    stage=node.key,
                    payload={"attempt": attempts},
                )
                return result
            except Exception as exc:
                self.foundation.update_node_metadata(run_id, node.key, {"last_error": str(exc)})
                if attempts <= max_retries:
                    self.run_store.append_event(
                        run_id,
                        "agent.retrying",
                        f"{node.agent or node.key} 节点失败，准备第 {attempts + 1} 次尝试：{exc}",
                        agent=node.agent or STAGE_AGENT.get(node.key, "Agent"),
                        stage=node.key,
                        payload={"attempt": attempts, "max_retries": max_retries, "error": str(exc)},
                    )
                    continue
                self.foundation.mark_run_failed(run_id, node.key)
                raise

    def _legacy_chain_node_executor(self, run_analysis: Callable[..., Any]) -> Callable[..., NodeExecutionResult]:
        def execute_legacy_chain(
            *,
            run_id: str,
            node: DAGNode,
            context: dict[str, Any],
            progress_callback: Callable[[str, str], None],
        ) -> NodeExecutionResult:
            if node.key != "collect":
                return NodeExecutionResult()

            input_data: CompetitorInput = context["input_data"]
            run_inputs = input_data.model_dump()
            run_inputs.setdefault("evidenceIndex", context["evidence_index"])
            result = run_analysis(
                run_inputs,
                allow_retry=context["allow_retry"],
                progress_callback=progress_callback,
            )
            scratchpad_outputs = getattr(result, "scratchpad_outputs", {})
            for completed_key in ("collect", "analyze", "write", "verify"):
                self.foundation.store.update_node_status(run_id, completed_key, "completed")
            return NodeExecutionResult(
                output_refs=_refs_for_node("collect", scratchpad_outputs),
                scratchpad_outputs=scratchpad_outputs,
                final_result=result,
            )

        return execute_legacy_chain

    def _progress_callback(self, run_id: str) -> Callable[[str, str], None]:
        def progress_callback(stage: str, message: str) -> None:
            self.foundation.mark_stage_running(run_id, stage)
            self.run_store.append_event(
                run_id,
                "agent.progress",
                message,
                agent=STAGE_AGENT.get(stage, "Agent"),
                stage=stage,
            )

        return progress_callback

    def _read_scratchpad(self, run_id: str, path: str) -> str:
        """Read a single scratchpad item by path, returning empty string if missing."""
        try:
            item = self.foundation.store.get_scratchpad_item(run_id, path)
            return item.content
        except Exception:
            return ""

    def _assemble_from_scratchpad(self, run_id: str, input_data: CompetitorInput) -> AssembledResult:
        """Build an AssembledResult from scratchpad items after per-node execution."""
        report = self._read_scratchpad(run_id, "write/report.md")
        verifier_result = self._read_scratchpad(run_id, "verify/verifier.json")
        issues = verification_issues(report, verifier_result) if report else ["报告内容为空"]
        return AssembledResult(
            report=report,
            verifier_result=verifier_result,
            passed=not issues,
            retried=False,
            scratchpad_outputs={
                "collect/raw.json": self._read_scratchpad(run_id, "collect/raw.json"),
                "analyze/findings.json": self._read_scratchpad(run_id, "analyze/findings.json"),
                "write/report.md": report,
                "verify/verifier.json": verifier_result,
            },
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


def _ready_nodes(nodes: list[DAGNode]) -> list[DAGNode]:
    by_key = {node.key: node for node in nodes}
    ready: list[DAGNode] = []
    for node in nodes:
        if node.status != "pending":
            continue
        if all(by_key[dependency].status == "completed" for dependency in node.depends_on if dependency in by_key):
            ready.append(node)
    return ready


def _refs_for_node(node_key: str, scratchpad_outputs: dict[str, str]) -> list[str]:
    if node_key == "collect":
        prefixes = ("collect/",)
    elif node_key == "analyze":
        prefixes = ("analyze/",)
    elif node_key == "write":
        prefixes = ("write/",)
    elif node_key == "verify":
        prefixes = ("verify/",)
    else:
        prefixes = ()
    return [path for path, content in scratchpad_outputs.items() if content and path.startswith(prefixes)]
