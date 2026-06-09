import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReviews, approveReview, rejectReview, assignReview } from "../api/client";
import type { ReviewItem, ReviewStatus } from "../api/types";

const FILTERS: { label: string; value: ReviewStatus | "" }[] = [
  { label: "全部", value: "" },
  { label: "待处理", value: "pending" },
  { label: "审核中", value: "in_review" },
  { label: "已通过", value: "approved" },
  { label: "已驳回", value: "rejected" },
];

function ReviewCard({ review, onAction }: { review: ReviewItem; onAction: (id: string, action: string, value?: string) => void }) {
  const [assignee, setAssignee] = useState("");
  const [showAssign, setShowAssign] = useState(false);

  return (
    <div className={`review-card review-${review.status}`}>
      <div className="review-header">
        <span className={`status-badge status-${review.status}`}>
          {review.status === "pending" ? "待处理" : review.status === "in_review" ? "审核中" : review.status === "approved" ? "已通过" : "已驳回"}
        </span>
        <Link to={`/dashboard/${review.run_id}`} className="review-run-link">
          Run: {review.run_id.slice(0, 8)}…
        </Link>
        <span className="review-time">{new Date(review.created_at).toLocaleString()}</span>
      </div>
      <ul className="review-issues">
        {review.issues.map((issue, i) => <li key={i}>{issue}</li>)}
      </ul>
      {review.assigned_to && <p className="review-assignee">审核人：{review.assigned_to}</p>}
      {review.review_notes && <p className="review-notes">备注：{review.review_notes}</p>}
      {review.status === "pending" && (
        <div className="review-actions">
          <button className="btn btn-approve" onClick={() => onAction(review.review_id, "approve")}>✓ 批准</button>
          <button className="btn btn-reject" onClick={() => onAction(review.review_id, "reject")}>✗ 驳回</button>
          <button className="btn btn-assign" onClick={() => setShowAssign(!showAssign)}>指派</button>
          {showAssign && (
            <span className="assign-input">
              <input value={assignee} onChange={e => setAssignee(e.target.value)} placeholder="审核人" />
              <button onClick={() => { onAction(review.review_id, "assign", assignee); setShowAssign(false); }}>确认</button>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function ReviewPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [filter, setFilter] = useState<ReviewStatus | "">("");
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    listReviews({ status: filter || undefined, limit: 100 })
      .then(setReviews)
      .finally(() => setLoading(false));
  };

  useEffect(load, [filter]);

  const handleAction = async (id: string, action: string, value?: string) => {
    try {
      if (action === "approve") await approveReview(id, value);
      else if (action === "reject") await rejectReview(id, value);
      else if (action === "assign") await assignReview(id, value!);
      load();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="review-page">
      <h1>📋 复核队列</h1>
      <div className="review-filters">
        {FILTERS.map(f => (
          <button
            key={f.value || "all"}
            className={filter === f.value ? "active" : ""}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {loading ? <p>加载中…</p> : (
        <div className="review-list">
          {reviews.map(r => (
            <ReviewCard key={r.review_id} review={r} onAction={handleAction} />
          ))}
          {reviews.length === 0 && <p className="empty-hint">暂无复核记录</p>}
        </div>
      )}
    </div>
  );
}
