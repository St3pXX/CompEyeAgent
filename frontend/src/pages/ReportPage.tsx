import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { downloadTextFile, getRun } from "../api/client";
import type { RunDetailResponse } from "../api/types";
import { MarkdownView } from "../components/MarkdownView";
import { createJsonFilename, createMarkdownFilename, selectArtifacts } from "../utils/runData";

export function ReportPage() {
  const { runId } = useParams();
  const [detail, setDetail] = useState<RunDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const id = runId ?? "";

  useEffect(() => {
    if (!id) return;
    setError(null);
    getRun(id)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : "加载报告失败"));
  }, [id]);

  const artifacts = useMemo(() => selectArtifacts(detail?.artifacts ?? []), [detail]);
  const reportContent = artifacts.report?.content ?? "报告还未生成。请先到 Dashboard 查看任务执行状态。";
  const verifierContent = artifacts.verifier?.content ?? "{}";
  const briefContent = artifacts.brief?.content ?? "{}";

  if (!runId) {
    return (
      <section className="report-page page-frame">
        <div className="status-banner error-message">缺少 Run ID。请从 Demo 页面创建分析任务，或从概览页选择已有 Run。</div>
      </section>
    );
  }

  return (
    <section className="report-page page-frame">
      <div className="page-title-row">
        <div>
          <p className="eyebrow">Report Detail</p>
          <h1>完整竞品分析报告</h1>
          <p>Run ID: {id}</p>
        </div>
        <Link to={`/dashboard/${id}`} className="button-link secondary">查看 Dashboard</Link>
      </div>

      {error && <div className="status-banner error-message">加载失败：{error}</div>}

      <div className="report-grid">
        <article className="report-body">
          <p className="eyebrow">Markdown Report</p>
          <MarkdownView content={reportContent} className="markdown-report" />
          <div className="download-row">
            <button
              className="button-link"
              disabled={!artifacts.report}
              onClick={() => artifacts.report && downloadTextFile(createMarkdownFilename(id), artifacts.report.content, "text/markdown;charset=utf-8")}
            >
              下载 Markdown
            </button>
            <button
              className="button-link secondary"
              disabled={!detail}
              onClick={() => detail && downloadTextFile(createJsonFilename(id, "artifacts"), JSON.stringify(detail, null, 2), "application/json;charset=utf-8")}
            >
              下载 JSON
            </button>
            <button className="button-link secondary" onClick={() => navigator.clipboard.writeText(window.location.href)}>
              复制报告链接
            </button>
          </div>
        </article>

        <aside className="panel-card">
          <h2>报告元信息</h2>
          <div className="source-card">
            <strong>Run 状态</strong>
            <p>{detail?.run.status ?? "loading"}</p>
          </div>
          <div className="source-card">
            <strong>Verifier JSON</strong>
            <pre>{verifierContent}</pre>
          </div>
          <div className="source-card">
            <strong>Input Brief</strong>
            <pre>{briefContent}</pre>
          </div>
          <h2 className="source-heading">来源索引</h2>
          {(detail?.sources.length ?? 0) === 0 ? (
            <div className="source-card">
              <strong>暂无来源</strong>
              <p>任务完成后，这里会展示从报告中提取的 URL 和上下文片段。</p>
            </div>
          ) : (
            detail?.sources.map((source) => (
              <a className="source-card source-link" key={source.source_id} href={source.uri} target="_blank" rel="noreferrer">
                <strong>{source.uri}</strong>
                <p>{source.snippet || "无上下文片段"}</p>
                <small>confidence: {source.confidence}</small>
              </a>
            ))
          )}
        </aside>
      </div>
    </section>
  );
}
