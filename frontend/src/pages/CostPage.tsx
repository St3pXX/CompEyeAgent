import { useEffect, useState } from "react";
import { getCosts } from "../api/client";
import type { CostEntry } from "../api/types";

export function CostPage() {
  const [costs, setCosts] = useState<CostEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCosts()
      .then(data => setCosts(data.costs))
      .finally(() => setLoading(false));
  }, []);

  const totalInput = costs.reduce((s, c) => s + c.input_tokens, 0);
  const totalOutput = costs.reduce((s, c) => s + c.output_tokens, 0);

  if (loading) return <div className="page-loading">加载中…</div>;

  return (
    <div className="cost-page">
      <h1>💰 成本追踪</h1>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{totalInput.toLocaleString()}</div>
          <div className="stat-label">总输入 Token</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalOutput.toLocaleString()}</div>
          <div className="stat-label">总输出 Token</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{(totalInput + totalOutput).toLocaleString()}</div>
          <div className="stat-label">总 Token</div>
        </div>
      </div>
      <table className="cost-table">
        <thead>
          <tr>
            <th>Run ID</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>输入 Token</th>
            <th>输出 Token</th>
          </tr>
        </thead>
        <tbody>
          {costs.map(c => (
            <tr key={c.run_id}>
              <td className="run-id-cell">{c.run_id.slice(0, 8)}…</td>
              <td><span className={`status-badge status-${c.status}`}>{c.status}</span></td>
              <td>{new Date(c.created_at).toLocaleString()}</td>
              <td className="num-cell">{c.input_tokens.toLocaleString()}</td>
              <td className="num-cell">{c.output_tokens.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
