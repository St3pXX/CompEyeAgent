import { Link } from "react-router-dom";

const examples = [
  { title: "飞书 AI 办公竞品分析", desc: "钉钉、企业微信、Notion，重点看 AI 助手和协同体验", tag: "SWOT" },
  { title: "AI 编程工具定位", desc: "Cursor、Trae、Copilot，输出战略建议", tag: "综合报告" },
  { title: "视频会议市场机会", desc: "Zoom、腾讯会议、飞书会议，重点看企业付费", tag: "对比表格" }
];

export function DemoPage() {
  return (
    <section className="demo-layout">
      <aside className="demo-sidebar">
        <button className="new-chat-button">+ 新对话</button>
        <div className="sidebar-section">
          <p className="section-label">快捷入口</p>
          <div className="sidebar-item active">探索竞品</div>
          <div className="sidebar-item">发现分析维度</div>
          <div className="sidebar-item">生成报告</div>
        </div>
        <div className="sidebar-section">
          <p className="section-label">快捷案例</p>
          {examples.map((item) => (
            <button className="case-card" key={item.title}>
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

      <div className="chat-page">
        <div className="chat-hero">
          <h1>把模糊竞品需求变成可执行分析任务</h1>
          <p>直接描述目标产品、竞品或市场问题；CompEye 会追问澄清范围，然后生成可追溯报告。</p>
          <div className="prompt-bar">
            <span>例如：帮我分析飞书相对钉钉和企业微信，在 AI 办公协同上的机会...</span>
            <button>→</button>
          </div>
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
            <p>我想分析飞书在 AI 办公协同上的竞争机会。</p>
          </article>
          <article className="message">
            <strong>CompEye</strong>
            <p>我需要确认 3 个点后再启动：竞品范围、分析维度、报告格式。</p>
            <div className="intent-grid">
              <div><b>竞品</b><span>钉钉、企业微信、Notion</span></div>
              <div><b>维度</b><span>定价、功能、AI 助手、生态</span></div>
              <div><b>输出</b><span>SWOT + 对比表格</span></div>
            </div>
          </article>
          <article className="message result-message">
            <div>
              <strong>报告已生成</strong>
              <p>可以继续在对话中查看摘要，也可以进入独立报告页下载完整 Markdown。</p>
            </div>
            <div className="result-actions">
              <Link to="/reports/demo-run" className="button-link">查看报告</Link>
              <Link to="/dashboard/demo-run" className="button-link secondary">打开 Dashboard</Link>
              <button className="button-link secondary">下载 Markdown</button>
            </div>
          </article>
        </div>

        <div className="composer">
          <span>继续补充需求，或直接说“开始分析”...</span>
          <button>→</button>
        </div>
      </div>
    </section>
  );
}
