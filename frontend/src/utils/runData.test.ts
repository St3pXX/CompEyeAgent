import { describe, expect, it } from "vitest";

import { buildCreateRunRequest, deriveStageStates, selectArtifacts } from "./runData";
import type { AgentEvent, ArtifactRecord } from "../api/types";

describe("buildCreateRunRequest", () => {
  it("builds a backend payload from the clarified chat brief", () => {
    const payload = buildCreateRunRequest({
      productName: "飞书",
      competitorsText: "钉钉, 企业微信、Notion",
      dimensionsText: "定价、功能、AI 助手",
      metricsText: "免费套餐, 文档协作",
      analysisType: "SWOT",
      allowRetry: false
    });

    expect(payload).toEqual({
      allow_retry: false,
      input: {
        productName: "飞书",
        competitors: ["钉钉", "企业微信", "Notion"],
        analysisType: "SWOT",
        dimensions: [
          { name: "定价", indicators: ["免费套餐", "文档协作"] },
          { name: "功能", indicators: ["免费套餐", "文档协作"] },
          { name: "AI 助手", indicators: ["免费套餐", "文档协作"] }
        ]
      }
    });
  });
});

describe("deriveStageStates", () => {
  it("marks stages as done, active, or waiting from real events", () => {
    const events: AgentEvent[] = [
      event(1, "agent.progress", "collect", "Collector"),
      event(2, "agent.progress", "analyze", "Analyzer")
    ];

    expect(deriveStageStates(events).map((stage) => [stage.key, stage.status])).toEqual([
      ["collect", "done"],
      ["analyze", "active"],
      ["write", "waiting"],
      ["verify", "waiting"],
      ["rewrite", "waiting"],
      ["final", "waiting"]
    ]);
  });
});

describe("selectArtifacts", () => {
  it("selects the newest artifact by kind", () => {
    const artifacts: ArtifactRecord[] = [
      artifact("a1", "report_markdown", "old report"),
      artifact("a2", "brief_json", "{\"productName\":\"飞书\"}"),
      artifact("a3", "report_markdown", "new report")
    ];

    expect(selectArtifacts(artifacts).report?.content).toBe("new report");
    expect(selectArtifacts(artifacts).brief?.content).toContain("飞书");
    expect(selectArtifacts(artifacts).verifier).toBeUndefined();
  });
});

function event(event_id: number, type: string, stage: string, agent: string): AgentEvent {
  return {
    event_id,
    run_id: "run-1",
    type,
    stage,
    agent,
    message: `${stage} message`,
    payload: {},
    created_at: `2026-05-14T00:00:0${event_id}Z`
  };
}

function artifact(artifact_id: string, kind: ArtifactRecord["kind"], content: string): ArtifactRecord {
  return {
    artifact_id,
    run_id: "run-1",
    kind,
    content,
    content_preview: content.slice(0, 20),
    created_at: "2026-05-14T00:00:00Z"
  };
}
