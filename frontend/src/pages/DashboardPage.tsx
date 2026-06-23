import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { downloadTextFile, getRun, getRunDag, getRunInspector, listScratchpad, openRunEventStream } from "../api/client";
import type { AgentEvent, ArtifactRecord, DAGView, InspectorSummary, RunRecord, ScratchpadItem, SourceRecord } from "../api/types";
import { StreamMessage } from "../components/StreamMessage";
import { createMarkdownFilename, deriveStageStates, selectArtifacts } from "../utils/runData";

const STREAM_EVENTS = [
  "run.created",
  "run.started",
  "agent.started",
  "agent.progress",
  "agent.completed",
  "verifier.issue",
  "artifact.ready",
  "run.completed",
  "run.failed",
  "run.cancelled"
];

export function DashboardPage() {
  const { runId } = useParams();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [dag, setDag] = useState<DAGView | null>(null);
  const [scratchpad, setScratchpad] = useState<ScratchpadItem[]>([]);
  const [inspector, setInspector] = useState<InspectorSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState("connecting");

  const id = runId ?? "";

  const loadRun = useCallback(async () => {
    if (!id) return;
    const detail = await getRun(id);
    setRun(detail.run);
    setEvents(detail.events);
    setArtifacts(detail.artifacts);
    setSources(detail.sources);
  }, [id]);

  const loadInspector = useCallback(async () => {
    if (!id) return;
    const [nextDag, nextScratchpad, nextInspector] = await Promise.all([
      getRunDag(id),
      listScratchpad(id),
      getRunInspector(id)
    ]);
    setDag(nextDag);
    setScratchpad(nextScratchpad);
    setInspector(nextInspector);
  }, [id]);

  useEffect(() => {
    if (!id) return;
    setError(null);
    Promise.all([loadRun(), loadInspector()]).catch((err) => setError(err instanceof Error ? err.message : "加载 run 失败"));
  }, [loadInspector, loadRun, id]);

  useEffect(() => {
    if (!id) return;
    const source = openRunEventStream(id);
    setStreamStatus("connected");

    function handleEvent(message: MessageEvent<string>) {
      const event = JSON.parse(message.data) as AgentEvent;
      setEvents((current) => mergeEvents(current, event));
      if (event.type === "artifact.ready" || event.type === "run.completed") {
        loadRun().catch(() => undefined);
        loadInspector().catch(() => undefined);
      }
    }

    STREAM_EVENTS.forEach((eventName) => source.addEventListener(eventName, handleEvent));
    source.addEventListener("stream.closed", (message) => {
      setStreamStatus("closed");
      const payload = JSON.parse((message as MessageEvent<string>).data) as { status?: RunRecord["status"] };
      setRun((current) => current ? { ...current, status: payload.status ?? current.status } : current);
      loadRun().catch(() => undefined);
      loadInspector().catch(() => undefined);
      source.close();
    });
    source.onerror = () => setStreamStatus("reconnecting");

    return () => {
      STREAM_EVENTS.forEach((eventName) => source.removeEventListener(eventName, handleEvent));
      source.close();
    };
  }, [loadInspector, loadRun, id]);

  const stages = useMemo(() => deriveStageStates(events), [events]);
  const selectedArtifacts = useMemo(() => selectArtifacts(artifacts), [artifacts]);

  if (!runId) {
    return (
      <section className="dashboard-page page-frame">
        <div className="status-banner error-message">缺少 Run ID。请从 Demo 页面创建分析任务，或从概览页选择已有 Run。</div>
      </section>
    );
  }

  return (
    <section className="dashboard-page page-frame">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Run Dashboard</p>
          <h1>Agent 执行追踪</h1>
          <p>Run ID: {id}</p>
        </div>
        <Link to={`/reports/${id}`} className="button-link">查看报告</Link>
      </div>

      {error && <div className="status-banner error-message">加载失败：{error}</div>}

      {events.length > 0 && (
        <section className="panel-card dashboard-stream">
          <div className="panel-heading">
            <h2>Agent 实时对话</h2>
            <span className="live-badge">{streamStatus}</span>
          </div>
          <StreamMessage
            agent="CompEye"
            events={events}
            live={(run?.status === "running" || run?.status === "queued") && streamStatus !== "closed"}
          />
        </section>
      )}

      <div className="dashboard-grid">
        <aside className="panel-card">
          <h2>Agent 阶段</h2>
          <div className="stage-list">
            {stages.map((stage) => (
              <div className={`stage-card stage-${stage.status}`} key={stage.key}>
                <span>{stage.status === "waiting" ? "…" : "✓"}</span>
                <div>
                  <strong>{stage.title}</strong>
                  <p>{stage.description}</p>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="panel-card">
          <div className="panel-heading">
            <h2>事件时间线</h2>
            <span className="live-badge">{streamStatus}</span>
          </div>
          <div className="timeline-list">
            {events.length === 0 ? (
              <div className="timeline-event"><strong>等待事件</strong><p>创建 run 后这里会显示 SSE 实时事件。</p></div>
            ) : (
              events.map((event) => (
                <div className="timeline-event" key={event.event_id}>
                  <strong>{event.type}</strong>
                  <p>{event.agent ? `${event.agent} · ` : ""}{event.message}</p>
                  <small>{new Date(event.created_at).toLocaleString()}</small>
                </div>
              ))
            )}
          </div>
        </section>

        <aside className="panel-card">
          <h2>产物入口</h2>
          <div className="run-summary">
            <span>状态</span>
            <strong>{run?.status ?? "loading"}</strong>
            <span>来源</span>
            <strong>{sources.length}</strong>
          </div>
          <div className="artifact-actions">
            <Link to={`/reports/${id}`} className="button-link">查看报告页</Link>
            <button
              className="button-link secondary"
              disabled={!selectedArtifacts.report}
              onClick={() => selectedArtifacts.report && downloadTextFile(createMarkdownFilename(id), selectedArtifacts.report.content, "text/markdown;charset=utf-8")}
            >
              下载 Markdown
            </button>
            <Link to="/demo" className="button-link secondary">回到对话</Link>
          </div>
        </aside>
      </div>

      <section className="inspector-section">
        <div className="panel-card inspector-dag">
          <div className="panel-heading">
            <h2>Run Inspector</h2>
            <span className="live-badge">{inspector?.dag.node_count ?? 0} nodes</span>
          </div>
          <div className="dag-node-list">
            {(dag?.nodes ?? []).map((node) => (
              <div className={`dag-node dag-${node.status}`} key={node.key}>
                <div>
                  <strong>{node.key}</strong>
                  <p>{node.agent || "Coordinator"} · {node.name}</p>
                </div>
                <span>{node.status}</span>
                <small>in: {node.input_refs.length ? node.input_refs.join(", ") : "none"}</small>
                <small>out: {node.output_refs.length ? node.output_refs.join(", ") : "none"}</small>
              </div>
            ))}
          </div>
          <div className="edge-list">
            {(dag?.edges ?? []).map((edge) => (
              <span key={`${edge.source}-${edge.target}`}>{edge.source} → {edge.target}</span>
            ))}
          </div>
        </div>

        <aside className="panel-card inspector-scratchpad">
          <h2>Scratchpad</h2>
          <div className="run-summary">
            <span>条目</span>
            <strong>{inspector?.scratchpad.item_count ?? scratchpad.length}</strong>
            <span>失败节点</span>
            <strong>{inspector?.dag.status_counts.failed ?? 0}</strong>
          </div>
          <div className="scratchpad-list">
            {scratchpad.length === 0 ? (
              <p>暂无 Scratchpad 条目。</p>
            ) : (
              scratchpad.map((item) => (
                <div className="scratchpad-item" key={item.item_id}>
                  <strong>{item.path}</strong>
                  <span>{item.kind}</span>
                  <p>{item.content_preview || "无预览"}</p>
                </div>
              ))
            )}
          </div>
        </aside>
      </section>
    </section>
  );
}

function mergeEvents(current: AgentEvent[], next: AgentEvent) {
  if (current.some((event) => event.event_id === next.event_id)) {
    return current;
  }
  return [...current, next].sort((a, b) => a.event_id - b.event_id);
}
