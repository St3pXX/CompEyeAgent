import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { downloadTextFile, getRun, openRunEventStream } from "../api/client";
import type { AgentEvent, ArtifactRecord, RunRecord, SourceRecord } from "../api/types";
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
  const { runId = "demo-run" } = useParams();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState("connecting");

  const loadRun = useCallback(async () => {
    const detail = await getRun(runId);
    setRun(detail.run);
    setEvents(detail.events);
    setArtifacts(detail.artifacts);
    setSources(detail.sources);
  }, [runId]);

  useEffect(() => {
    setError(null);
    loadRun().catch((err) => setError(err instanceof Error ? err.message : "加载 run 失败"));
  }, [loadRun]);

  useEffect(() => {
    const source = openRunEventStream(runId);
    setStreamStatus("connected");

    function handleEvent(message: MessageEvent<string>) {
      const event = JSON.parse(message.data) as AgentEvent;
      setEvents((current) => mergeEvents(current, event));
      if (event.type === "artifact.ready" || event.type === "run.completed") {
        loadRun().catch(() => undefined);
      }
    }

    STREAM_EVENTS.forEach((eventName) => source.addEventListener(eventName, handleEvent));
    source.addEventListener("stream.closed", (message) => {
      setStreamStatus("closed");
      const payload = JSON.parse((message as MessageEvent<string>).data) as { status?: RunRecord["status"] };
      setRun((current) => current ? { ...current, status: payload.status ?? current.status } : current);
      loadRun().catch(() => undefined);
      source.close();
    });
    source.onerror = () => setStreamStatus("reconnecting");

    return () => {
      STREAM_EVENTS.forEach((eventName) => source.removeEventListener(eventName, handleEvent));
      source.close();
    };
  }, [loadRun, runId]);

  const stages = useMemo(() => deriveStageStates(events), [events]);
  const selectedArtifacts = useMemo(() => selectArtifacts(artifacts), [artifacts]);

  return (
    <section className="dashboard-page page-frame">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Run Dashboard</p>
          <h1>Agent 执行追踪</h1>
          <p>Run ID: {runId}</p>
        </div>
        <Link to={`/reports/${runId}`} className="button-link">查看报告</Link>
      </div>

      {error && <div className="status-banner error-message">加载失败：{error}</div>}

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
            <Link to={`/reports/${runId}`} className="button-link">查看报告页</Link>
            <button
              className="button-link secondary"
              disabled={!selectedArtifacts.report}
              onClick={() => selectedArtifacts.report && downloadTextFile(createMarkdownFilename(runId), selectedArtifacts.report.content, "text/markdown;charset=utf-8")}
            >
              下载 Markdown
            </button>
            <Link to="/demo" className="button-link secondary">回到对话</Link>
          </div>
        </aside>
      </div>
    </section>
  );
}

function mergeEvents(current: AgentEvent[], next: AgentEvent) {
  if (current.some((event) => event.event_id === next.event_id)) {
    return current;
  }
  return [...current, next].sort((a, b) => a.event_id - b.event_id);
}
