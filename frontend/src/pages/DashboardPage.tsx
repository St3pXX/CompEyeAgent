import { Link, useParams } from "react-router-dom";

const stages = [
  ["Collect", "公开资料采集", "为每个竞品和指标寻找公开证据"],
  ["Analyze", "结构化分析", "把证据整理为 SWOT / 对比结论"],
  ["Write", "报告撰写", "生成可读 Markdown 竞品报告"],
  ["Verify", "独立质检", "校验幻觉、矛盾、缺失来源"]
];

const events = [
  ["run.created", "根据澄清后的 brief 创建任务"],
  ["agent.progress", "Collector 正在采集公开资料"],
  ["agent.progress", "Analyzer 正在结构化分析"],
  ["artifact.ready", "报告、质检结果和来源索引已生成"]
];

export function DashboardPage() {
  const { runId = "demo-run" } = useParams();

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

      <div className="dashboard-grid">
        <aside className="panel-card">
          <h2>Agent 阶段</h2>
          <div className="stage-list">
            {stages.map(([name, title, desc]) => (
              <div className="stage-card" key={name}>
                <span>✓</span>
                <div>
                  <strong>{name} · {title}</strong>
                  <p>{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </aside>

        <section className="panel-card">
          <h2>事件时间线</h2>
          <div className="timeline-list">
            {events.map(([type, message]) => (
              <div className="timeline-event" key={`${type}-${message}`}>
                <strong>{type}</strong>
                <p>{message}</p>
              </div>
            ))}
          </div>
        </section>

        <aside className="panel-card">
          <h2>产物入口</h2>
          <div className="artifact-actions">
            <Link to={`/reports/${runId}`} className="button-link">查看报告页</Link>
            <button className="button-link secondary">下载 Markdown</button>
            <Link to="/demo" className="button-link secondary">回到对话</Link>
          </div>
        </aside>
      </div>
    </section>
  );
}
