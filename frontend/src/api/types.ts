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

export type DAGNodeStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type DAGNode = {
  node_id: string;
  run_id: string;
  key: string;
  name: string;
  agent: string;
  status: DAGNodeStatus;
  depends_on: string[];
  input_refs: string[];
  output_refs: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type DAGEdge = {
  source: string;
  target: string;
};

export type DAGView = {
  run_id: string;
  nodes: DAGNode[];
  edges: DAGEdge[];
};

export type ScratchpadItem = {
  item_id: string;
  run_id: string;
  path: string;
  kind: "json" | "markdown" | "text";
  content: string;
  content_preview: string;
  producer_node_id?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type InspectorSummary = {
  run_id: string;
  dag: {
    node_count: number;
    status_counts: Record<string, number>;
  };
  scratchpad: {
    item_count: number;
    paths: string[];
  };
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

export type ReviewStatus = "pending" | "in_review" | "approved" | "rejected";

export type ReviewItem = {
  review_id: string;
  run_id: string;
  status: ReviewStatus;
  issues: string[];
  assigned_to?: string | null;
  review_notes?: string | null;
  created_at: string;
  updated_at: string;
  reviewed_at?: string | null;
};

export type StatsResponse = {
  total_runs: number;
  by_status: Record<string, number>;
  pending_reviews: number;
  total_reviews: number;
};

export type CostEntry = {
  run_id: string;
  status: string;
  created_at: string;
  input_tokens: number;
  output_tokens: number;
};

export type CostsResponse = {
  costs: CostEntry[];
};
