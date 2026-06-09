import type {
  AgentEvent,
  ArtifactRecord,
  CostsResponse,
  CreateRunRequest,
  CreateRunResponse,
  DAGView,
  InspectorSummary,
  ReviewItem,
  RunDetailResponse,
  RunRecord,
  ScratchpadItem,
  SourceRecord,
  StatsResponse,
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

export async function getRunDag(runId: string): Promise<DAGView> {
  const data = await request<{ dag: DAGView }>(`/api/runs/${runId}/dag`);
  return data.dag;
}

export async function listScratchpad(runId: string): Promise<ScratchpadItem[]> {
  const data = await request<{ items: ScratchpadItem[] }>(`/api/runs/${runId}/scratchpad`);
  return data.items;
}

export async function getRunInspector(runId: string): Promise<InspectorSummary> {
  const data = await request<{ inspector: InspectorSummary }>(`/api/runs/${runId}/inspector`);
  return data.inspector;
}

export async function retryRunNode(runId: string, nodeKey: string): Promise<{ run: RunDetailResponse["run"]; node_key: string }> {
  return request<{ run: RunDetailResponse["run"]; node_key: string }>(`/api/runs/${runId}/dag/${nodeKey}/retry`, {
    method: "POST"
  });
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

// ---------------------------------------------------------------------------
// Review queue
// ---------------------------------------------------------------------------

export async function listReviews(params?: { status?: string; limit?: number }): Promise<ReviewItem[]> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status);
  if (params?.limit) qs.set("limit", String(params.limit));
  const data = await request<{ reviews: ReviewItem[] }>(`/api/reviews?${qs}`);
  return data.reviews;
}

export async function getReview(reviewId: string): Promise<ReviewItem> {
  const data = await request<{ review: ReviewItem }>(`/api/reviews/${reviewId}`);
  return data.review;
}

export async function approveReview(reviewId: string, notes?: string): Promise<ReviewItem> {
  const data = await request<{ review: ReviewItem }>(`/api/reviews/${reviewId}/approve`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
  return data.review;
}

export async function rejectReview(reviewId: string, notes?: string): Promise<ReviewItem> {
  const data = await request<{ review: ReviewItem }>(`/api/reviews/${reviewId}/reject`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
  return data.review;
}

export async function assignReview(reviewId: string, assignee: string): Promise<ReviewItem> {
  const data = await request<{ review: ReviewItem }>(`/api/reviews/${reviewId}/assign`, {
    method: "POST",
    body: JSON.stringify({ assignee }),
  });
  return data.review;
}

// ---------------------------------------------------------------------------
// Stats & costs
// ---------------------------------------------------------------------------

export async function getStats(): Promise<StatsResponse> {
  return request<StatsResponse>("/api/stats");
}

export async function getCosts(): Promise<CostsResponse> {
  return request<CostsResponse>("/api/costs");
}

export async function listRuns(limit = 50): Promise<RunRecord[]> {
  const data = await request<{ runs: RunRecord[] }>(`/api/runs?limit=${limit}`);
  return data.runs;
}
