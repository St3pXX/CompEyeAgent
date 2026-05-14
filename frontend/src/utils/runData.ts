import type { AgentEvent, AnalysisType, ArtifactRecord, CreateRunRequest } from "../api/types";

export type ClarifiedBrief = {
  productName: string;
  competitorsText: string;
  dimensionsText: string;
  metricsText: string;
  analysisType: AnalysisType;
  allowRetry: boolean;
};

export type StageStatus = "done" | "active" | "waiting";

export type StageState = {
  key: string;
  title: string;
  description: string;
  status: StageStatus;
};

export const DEFAULT_BRIEF: ClarifiedBrief = {
  productName: "飞书",
  competitorsText: "钉钉、企业微信、Notion",
  dimensionsText: "定价、功能、AI 助手、生态",
  metricsText: "免费套餐、文档协作、视频会议、AI 助手",
  analysisType: "SWOT",
  allowRetry: true
};

export const STAGE_DEFINITIONS = [
  { key: "collect", title: "Collect · 公开资料采集", description: "为每个竞品和指标寻找公开证据" },
  { key: "analyze", title: "Analyze · 结构化分析", description: "把证据整理为 SWOT / 对比结论" },
  { key: "write", title: "Write · 报告撰写", description: "生成可读 Markdown 竞品报告" },
  { key: "verify", title: "Verify · 独立质检", description: "校验幻觉、矛盾、缺失来源" },
  { key: "rewrite", title: "Rewrite · 自动修复", description: "按质检意见最小重写一次" },
  { key: "final", title: "Done · 产物交付", description: "输出报告、质检 JSON 和输入 brief" }
];

export function buildCreateRunRequest(brief: ClarifiedBrief): CreateRunRequest {
  const competitors = splitList(brief.competitorsText);
  const indicators = splitList(brief.metricsText);
  const dimensions = splitList(brief.dimensionsText).map((name) => ({
    name,
    indicators
  }));

  return {
    allow_retry: brief.allowRetry,
    input: {
      productName: brief.productName.trim(),
      competitors,
      dimensions,
      analysisType: brief.analysisType
    }
  };
}

export function splitList(value: string): string[] {
  return value
    .split(/[、,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function deriveStageStates(events: AgentEvent[]): StageState[] {
  const seenStages = events.map((event) => event.stage).filter(Boolean) as string[];
  const activeStage = seenStages.at(-1);
  return STAGE_DEFINITIONS.map((stage) => {
    const seenIndex = seenStages.lastIndexOf(stage.key);
    if (stage.key === activeStage) {
      return { ...stage, status: "active" as const };
    }
    if (seenIndex >= 0 || isTerminalStageDone(stage.key, events)) {
      return { ...stage, status: "done" as const };
    }
    return { ...stage, status: "waiting" as const };
  });
}

export function selectArtifacts(artifacts: ArtifactRecord[]) {
  return {
    report: newestArtifact(artifacts, "report_markdown"),
    brief: newestArtifact(artifacts, "brief_json"),
    verifier: newestArtifact(artifacts, "verifier_json"),
    provenance: newestArtifact(artifacts, "provenance_index")
  };
}

export function newestArtifact(artifacts: ArtifactRecord[], kind: ArtifactRecord["kind"]) {
  return artifacts.filter((artifact) => artifact.kind === kind).at(-1);
}

export function createMarkdownFilename(runId: string) {
  return `compeye-report-${runId}.md`;
}

export function createJsonFilename(runId: string, kind: string) {
  return `compeye-${kind}-${runId}.json`;
}

function isTerminalStageDone(stage: string, events: AgentEvent[]) {
  if (stage !== "final") {
    return false;
  }
  return events.some((event) => event.type === "run.completed" || event.type === "artifact.ready");
}
