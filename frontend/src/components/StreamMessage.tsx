import { useEffect, useRef, useState, type ReactNode } from "react";

import type { AgentEvent } from "../api/types";

type StreamMessageProps = {
  /** Header label, e.g. "CompEye". */
  agent: string;
  /** Ordered, deduped agent events for this run (earliest first). */
  events: AgentEvent[];
  /** True while the run is still producing events (shows blinking cursor). */
  live?: boolean;
  /** Optional final content rendered after the event list (e.g. the report). */
  children?: ReactNode;
};

/** Event types that carry meaningful progress text for the conversation view. */
const PROGRESS_TYPES = new Set([
  "run.started",
  "agent.started",
  "agent.progress",
  "agent.completed",
  "agent.retrying",
  "run.completed",
  "run.failed",
  "run.cancelled",
]);

/** Typewriter hook: reveals `text` one char at a time within ~250ms. */
function useTypewriter(text: string, enabled: boolean) {
  const [revealed, setRevealed] = useState(enabled ? "" : text);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (!enabled) {
      setRevealed(text);
      return;
    }
    // Reset and animate whenever the target text changes.
    setRevealed("");
    const total = text.length;
    if (total === 0) return;
    const duration = 250;
    const step = Math.max(1, Math.ceil(total / (duration / 16)));
    let shown = 0;
    const tick = () => {
      shown = Math.min(total, shown + step);
      setRevealed(text.slice(0, shown));
      if (shown < total) {
        frame.current = requestAnimationFrame(tick);
      }
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [text, enabled]);

  return revealed;
}

/** Map a stage key to a short Chinese label for the stage chip. */
const STAGE_LABEL: Record<string, string> = {
  collect: "Collect",
  analyze: "Analyze",
  write: "Write",
  verify: "Verify",
  rewrite: "Rewrite",
};

/** True when an event is a low-emphasis heartbeat ("正在生成中…"). */
function isHeartbeat(event: AgentEvent): boolean {
  return Boolean(event.payload && event.payload.kind === "heartbeat");
}

/**
 * Collapse runs of consecutive heartbeat events into a single entry (the last
 * one), so the UI shows "still generating…" once per stage instead of every 8s.
 */
function collapseHeartbeats(events: AgentEvent[]): AgentEvent[] {
  const result: AgentEvent[] = [];
  for (const event of events) {
    const prev = result.at(-1);
    if (isHeartbeat(event) && prev !== undefined && isHeartbeat(prev)) {
      result[result.length - 1] = event;
    } else {
      result.push(event);
    }
  }
  return result;
}

function statusIcon(type: string): string {
  if (type === "agent.completed" || type === "run.completed" || type === "artifact.ready") return "✓";
  if (type === "run.failed" || type === "run.cancelled") return "✕";
  if (type === "agent.retrying") return "↻";
  return "·";
}

/** Convert event type to a CSS-safe class suffix (dots -> dashes). */
function statusClass(type: string): string {
  return `stream-type-${type.replace(/\./g, "-")}`;
}

export function StreamMessage({ agent, events, live = false, children }: StreamMessageProps) {
  const visible = collapseHeartbeats(events.filter((event) => PROGRESS_TYPES.has(event.type)));
  const latest = visible.at(-1);
  const showCursor = live && latest !== undefined && !/completed$|failed$|cancelled$/.test(latest.type);
  // Typewriter applies only to the newest line; earlier lines render instantly.
  const latestText = useTypewriter(latest?.message ?? "", showCursor);

  // Autoscroll to the newest line when events arrive.
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [visible.length, latestText]);

  if (visible.length === 0) {
    return (
      <article className="message stream-message">
        <strong>{agent}</strong>
        <p className="stream-idle">{live ? "正在启动分析任务…" : "等待事件"}</p>
      </article>
    );
  }

  return (
    <article className="message stream-message">
      <strong>{agent}</strong>
      <ul className="stream-steps">
        {visible.map((event, index) => {
          const isLatest = event.event_id === latest?.event_id;
          const text = isLatest ? latestText : event.message;
          const stageLabel = event.stage ? STAGE_LABEL[event.stage] ?? event.stage : null;
          return (
            <li
              className={`stream-step ${statusClass(event.type)}${isHeartbeat(event) ? " stream-heartbeat" : ""}`}
              key={event.event_id}
            >
              <span className="stream-icon" aria-hidden="true">{statusIcon(event.type)}</span>
              {stageLabel && <span className="stream-stage">{stageLabel}</span>}
              <span className="stream-text">
                {text}
                {isLatest && showCursor && <span className="stream-cursor" aria-hidden="true">▍</span>}
              </span>
              <small className="stream-time">{new Date(event.created_at).toLocaleTimeString()}</small>
            </li>
          );
        })}
      </ul>
      {children}
      <div ref={endRef} />
    </article>
  );
}
