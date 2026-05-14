import type {
  AgentEvent,
  ArtifactRecord,
  CreateRunRequest,
  CreateRunResponse,
  RunDetailResponse,
  SourceRecord
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export function createRun(payload: CreateRunRequest): Promise<CreateRunResponse> {
  return request<CreateRunResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getRun(runId: string): Promise<RunDetailResponse> {
  return request<RunDetailResponse>(`/api/runs/${runId}`);
}

export async function listEvents(runId: string, afterEventId = 0): Promise<AgentEvent[]> {
  const data = await request<{ events: AgentEvent[] }>(`/api/runs/${runId}/events?after_event_id=${afterEventId}`);
  return data.events;
}

export async function listArtifacts(runId: string): Promise<ArtifactRecord[]> {
  const data = await request<{ artifacts: ArtifactRecord[] }>(`/api/runs/${runId}/artifacts`);
  return data.artifacts;
}

export async function listSources(runId: string): Promise<SourceRecord[]> {
  const data = await request<{ sources: SourceRecord[] }>(`/api/runs/${runId}/sources`);
  return data.sources;
}

export async function getArtifact(artifactId: string): Promise<ArtifactRecord> {
  const data = await request<{ artifact: ArtifactRecord }>(`/api/artifacts/${artifactId}`);
  return data.artifact;
}

export function openRunEventStream(runId: string, afterEventId = 0): EventSource {
  return new EventSource(`${API_BASE}/sse/runs/${runId}?after_event_id=${afterEventId}`);
}

export function downloadTextFile(filename: string, content: string, mimeType = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
