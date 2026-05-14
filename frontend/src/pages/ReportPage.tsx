import { Link, useParams } from "react-router-dom";

const sources = [
  ["example.com", "报告中的上下文片段，后续由 source_references 接口填充。"],
  ["docs.example.cn", "报告中的上下文片段，后续展示 URL、snippet 和 confidence。"]
];

export function ReportPage() {
  const { runId = "demo-run" } = useParams();

  return (
    <section className="report-page page-frame">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Report Detail</p>
          <h1>完整竞品分析报告</h1>
          <p>Run ID: {runId}</p>
        </div>
        <Link to={`/dashboard/${runId}`} className="button-link secondary">查看 Dashboard</Link>
      </div>

      <div className="report-grid">
        <article className="report-body">
          <p className="eyebrow">Markdown Report</p>
          <h2>飞书 AI 办公协同竞品分析</h2>
          <p>
            基于公开信息，对钉钉、企业微信、Notion 等产品进行 SWOT 与对比分析。
            下一步会从 `report_markdown` artifact 加载完整报告内容。
          </p>
          <div className="download-row">
            <button className="button-link">下载 Markdown</button>
            <button className="button-link secondary">下载 JSON</button>
            <button className="button-link secondary">复制报告链接</button>
          </div>
        </article>

        <aside className="panel-card">
          <h2>报告元信息</h2>
          <div className="source-card">
            <strong>Verifier</strong>
            <p>Needs review</p>
          </div>
          <div className="source-card">
            <strong>Input Brief</strong>
            <p>目标产品、竞品、维度、指标</p>
          </div>
          <h2 className="source-heading">来源索引</h2>
          {sources.map(([host, snippet]) => (
            <div className="source-card" key={host}>
              <strong>{host}</strong>
              <p>{snippet}</p>
            </div>
          ))}
        </aside>
      </div>
    </section>
  );
}
