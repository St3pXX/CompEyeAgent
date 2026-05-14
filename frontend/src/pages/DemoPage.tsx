import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createRun } from "../api/client";
import type { AnalysisType, RunRecord } from "../api/types";
import { buildCreateRunRequest, DEFAULT_BRIEF, splitList, type ClarifiedBrief } from "../utils/runData";

const examples: Array<{ title: string; desc: string; tag: AnalysisType; brief: ClarifiedBrief }> = [
  {
    title: "飞书 AI 办公竞品分析",
    desc: "钉钉、企业微信、Notion，重点看 AI 助手和协同体验",
    tag: "SWOT",
    brief: DEFAULT_BRIEF
  },
  {
    title: "AI 编程工具定位",
    desc: "Cursor、Trae、Copilot，输出战略建议",
    tag: "综合报告",
    brief: {
      productName: "Trae",
      competitorsText: "Cursor、GitHub Copilot、通义灵码",
      dimensionsText: "产品定位、代码生成、IDE 集成、定价",
      metricsText: "开发效率、上下文理解、插件生态、企业部署",
      analysisType: "综合报告",
      allowRetry: true
    }
  },
  {
    title: "视频会议市场机会",
    desc: "Zoom、腾讯会议、飞书会议，重点看企业付费",
    tag: "对比表格",
    brief: {
      productName: "飞书会议",
      competitorsText: "Zoom、腾讯会议、钉钉会议",
      dimensionsText: "定价、音视频体验、企业管理、AI 摘要",
      metricsText: "免费套餐、录制能力、会议纪要、企业安全",
      analysisType: "对比表格",
      allowRetry: true
    }
  }
];

export function DemoPage() {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("帮我分析飞书相对钉钉和企业微信，在 AI 办公协同上的机会");
  const [brief, setBrief] = useState<ClarifiedBrief>(DEFAULT_BRIEF);
  const [createdRun, setCreatedRun] = useState<RunRecord | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const payloadPreview = useMemo(() => buildCreateRunRequest(brief), [brief]);

  async function handleCreateRun(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsCreating(true);
    try {
      const response = await createRun(payloadPreview);
      setCreatedRun(response.run);
      navigate(`/dashboard/${response.run.run_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setIsCreating(false);
    }
  }

  function applyExample(nextBrief: ClarifiedBrief) {
    setBrief(nextBrief);
    setPrompt(`帮我分析${nextBrief.productName}，竞品包括${nextBrief.competitorsText}`);
    setCreatedRun(null);
    setError(null);
  }

  return (
    <section className="demo-layout">
      <aside className="demo-sidebar">
        <button className="new-chat-button" onClick={() => setCreatedRun(null)}>+ 新对话</button>
        <div className="sidebar-section">
          <p className="section-label">快捷入口</p>
          <div className="sidebar-item active">探索竞品</div>
          <div className="sidebar-item">发现分析维度</div>
          <div className="sidebar-item">生成报告</div>
        </div>
        <div className="sidebar-section">
          <p className="section-label">快捷案例</p>
          {examples.map((item) => (
            <button className="case-card" key={item.title} onClick={() => applyExample(item.brief)}>
              <span>{item.tag}</span>
              <strong>{item.title}</strong>
              <small>{item.desc}</small>
            </button>
          ))}
        </div>
        <div className="sidebar-section">
          <p className="section-label">历史对话</p>
          <div className="history-item">帮我分析在线协作文档...</div>
          <div className="history-item">SaaS 定价策略竞品...</div>
        </div>
      </aside>

      <form className="chat-page" onSubmit={handleCreateRun}>
        <div className="chat-hero">
          <h1>把模糊竞品需求变成可执行分析任务</h1>
          <p>直接描述目标产品、竞品或市场问题；CompEye 会追问澄清范围，然后生成可追溯报告。</p>
          <label className="prompt-bar" aria-label="自然语言需求">
            <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            <button type="submit" disabled={isCreating}>{isCreating ? "…" : "→"}</button>
          </label>
          <div className="capability-row">
            <span>实时搜索</span>
            <span>自动澄清需求</span>
            <span>来源索引</span>
            <span>报告可下载</span>
          </div>
        </div>

        <div className="chat-thread">
          <article className="message user-message">
            <strong>用户</strong>
            <p>{prompt}</p>
          </article>
          <article className="message">
            <strong>CompEye</strong>
            <p>我会按以下 brief 创建真实分析任务。你可以直接编辑字段后开始分析。</p>
            <div className="brief-form">
              <label>
                目标产品
                <input value={brief.productName} onChange={(event) => setBrief({ ...brief, productName: event.target.value })} />
              </label>
              <label>
                竞品
                <input value={brief.competitorsText} onChange={(event) => setBrief({ ...brief, competitorsText: event.target.value })} />
              </label>
              <label>
                分析维度
                <input value={brief.dimensionsText} onChange={(event) => setBrief({ ...brief, dimensionsText: event.target.value })} />
              </label>
              <label>
                重点指标
                <input value={brief.metricsText} onChange={(event) => setBrief({ ...brief, metricsText: event.target.value })} />
              </label>
              <label>
                输出形式
                <select
                  value={brief.analysisType}
                  onChange={(event) => setBrief({ ...brief, analysisType: event.target.value as AnalysisType })}
                >
                  <option value="SWOT">SWOT</option>
                  <option value="对比表格">对比表格</option>
                  <option value="综合报告">综合报告</option>
                </select>
              </label>
            </div>
            <div className="intent-grid">
              <div><b>竞品</b><span>{splitList(brief.competitorsText).join("、")}</span></div>
              <div><b>维度</b><span>{splitList(brief.dimensionsText).join("、")}</span></div>
              <div><b>输出</b><span>{brief.analysisType}</span></div>
            </div>
          </article>
          {error && (
            <article className="message error-message">
              <strong>创建失败</strong>
              <p>{error}</p>
            </article>
          )}
          {createdRun && (
            <article className="message result-message">
              <div>
                <strong>任务已创建</strong>
                <p>Run ID: {createdRun.run_id}。Dashboard 会实时展示 Agent 执行过程。</p>
              </div>
              <div className="result-actions">
                <Link to={`/dashboard/${createdRun.run_id}`} className="button-link">打开 Dashboard</Link>
                <Link to={`/reports/${createdRun.run_id}`} className="button-link secondary">查看报告</Link>
              </div>
            </article>
          )}
        </div>

        <div className="composer">
          <span>确认 brief 后点击右侧按钮创建真实任务</span>
          <button type="submit" disabled={isCreating}>{isCreating ? "…" : "→"}</button>
        </div>
      </form>
    </section>
  );
}
