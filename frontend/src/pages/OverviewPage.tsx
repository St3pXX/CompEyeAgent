import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getStats, listRuns, listReviews } from "../api/client";
import type { StatsResponse, RunRecord, ReviewItem } from "../api/types";

const STATUS_LABELS: Record<string, string> = {
  passed: "✅ 通过",
  needs_review: "⚠️ 待复核",
  failed: "❌ 失败",
  running: "🔄 运行中",
  queued: "⏳ 排队中",
  cancelled: "🚫 已取消",
};

export function OverviewPage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStats(), listRuns(20), listReviews({ status: "pending", limit: 10 })])
      .then(([s, r, rv]) => {
        setStats(s);
        setRuns(r);
        setReviews(rv);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">加载中…</div>;

  return (
    <div className="overview-page">
      <h1>📊 概览</h1>

      {/* Stats cards */}
      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_runs}</div>
            <div className="stat-label">总分析任务</div>
          </div>
          {Object.entries(stats.by_status).map(([status, count]) => (
            <div key={status} className="stat-card">
              <div className="stat-value">{count}</div>
              <div className="stat-label">{STATUS_LABELS[status] || status}</div>
            </div>
          ))}
          <div className="stat-card stat-card--alert">
            <div className="stat-value">{stats.pending_reviews}</div>
            <div className="stat-label">待审核</div>
          </div>
        </div>
      )}

      <div className="overview-columns">
        {/* Recent runs */}
        <section className="overview-section">
          <h2>最近任务</h2>
          <div className="run-list">
            {runs.map((run) => (
              <Link key={run.run_id} to={`/dashboard/${run.run_id}`} className="run-row">
                <span className={`status-badge status-${run.status}`}>
                  {STATUS_LABELS[run.status] || run.status}
                </span>
                <span className="run-product">{run.input.productName}</span>
                <span className="run-competitors">
                  vs {run.input.competitors.join(", ")}
                </span>
                <span className="run-time">{new Date(run.created_at).toLocaleString()}</span>
              </Link>
            ))}
            {runs.length === 0 && <p className="empty-hint">暂无分析任务</p>}
          </div>
        </section>

        {/* Pending reviews */}
        <section className="overview-section">
          <h2>待审核 <Link to="/reviews" className="see-all">查看全部 →</Link></h2>
          {reviews.length === 0 ? (
            <p className="empty-hint">暂无待审核项</p>
          ) : (
            <div className="review-list">
              {reviews.map((rv) => (
                <Link key={rv.review_id} to={`/dashboard/${rv.run_id}`} className="review-row">
                  <span className="review-issues">{rv.issues.slice(0, 2).join("；")}</span>
                  <span className="review-time">{new Date(rv.created_at).toLocaleString()}</span>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
