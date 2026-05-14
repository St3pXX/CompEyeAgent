export type AnalysisType = "SWOT" | "对比表格" | "综合报告";
export type RunStatus = "queued" | "running" | "passed" | "needs_review" | "failed" | "cancelled";
export type ArtifactKind = "report_markdown" | "verifier_json" | "brief_json" | "provenance_index";

export type Dimension = {
  name: string;
  indicators: string[];
};

export type CompetitorInput = {
  productName: string;
  competitors: string[];
  dimensions: Dimension[];
  analysisType: AnalysisType;
};

export type RunRecord = {
  run_id: string;
  input: CompetitorInput;
  status: RunStatus;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
  error?: string | null;
  parent_run_id?: string | null;
};

export type AgentEvent = {
  event_id: number;
  run_id: string;
  type: string;
  agent?: string | null;
  stage?: string | null;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type ArtifactRecord = {
  artifact_id: string;
  run_id: string;
  kind: ArtifactKind;
  content: string;
  content_preview: string;
  created_at: string;
};

export type SourceRecord = {
  source_id: string;
  run_id: string;
  conclusion_id?: string | null;
  uri: string;
  snippet: string;
  confidence: "high" | "medium" | "low";
  retrieved_at?: string | null;
};

export type CreateRunRequest = {
  input: CompetitorInput;
  allow_retry: boolean;
};

export type CreateRunResponse = {
  run: RunRecord;
};

export type RunDetailResponse = {
  run: RunRecord;
  events: AgentEvent[];
  artifacts: ArtifactRecord[];
  sources: SourceRecord[];
};
