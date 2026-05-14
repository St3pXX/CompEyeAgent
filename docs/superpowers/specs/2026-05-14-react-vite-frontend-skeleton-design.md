# React / Vite 前端骨架设计

## 目标

构建 Phase 1.5 Web App 的前端骨架，包含三个稳定路由：对话优先的 Demo 页面、实时运行 Dashboard 页面和 Report 报告页面。视觉风格沿用已完成的 Streamlit UI：浅蓝灰背景、半透明面板、深色主操作按钮、红色标签、薄荷绿状态标记和圆角卡片。

## 页面

### Demo `/demo`

Demo 页面是主要产品入口。它采用 chatbot 式布局，让用户用自然语言描述竞品分析需求。创建 run 前，助手需要澄清目标产品、竞品、分析维度、重点指标和输出格式等缺失信息。左侧侧边栏提供新对话、快捷入口、快捷案例和历史对话。

页面也需要支持在对话中展示结果卡。run 创建或完成后，对话内可以展示 Dashboard、Report 和下载等操作入口。

### Dashboard `/dashboard/:runId`

Dashboard 页面展示单次 run 的执行状态。它消费 FastAPI API 返回的 Run 和 Event 数据，后续会订阅 SSE。骨架阶段需要预留 Agent 阶段、事件时间线、run 摘要和产物操作区域。

### Report `/reports/:runId`

Report 页面是正式产物视图。它展示完整 Markdown 报告、Verifier 结果、Input Brief、来源索引和下载操作。用户可以从 Demo 对话结果卡或 Dashboard 产物面板进入该页面。

## 架构

前端位于 `frontend/` 下，并与 Python 后端保持独立。API 访问集中在 `src/api/client.ts`，数据契约位于 `src/api/types.ts`，页面位于 `src/pages/`。共享布局组件放在 `src/components/AppShell.tsx`。

骨架阶段不引入 UI 框架。CSS 保留在 `src/styles.css` 中，方便检查 Streamlit 风格的视觉语言，并为后续迁移到 design tokens 留出空间。

## 初始范围

本骨架只创建路由、静态页面结构、类型化 API helper 和视觉占位。不需要立即触发真实 Agent 执行。API helper 需要为下一步做好准备：`/demo` 调用 `POST /api/runs`，Dashboard 打开 SSE，Report 加载 artifacts 和 sources。

## 验收标准

- `/` 重定向到 `/demo`。
- `/demo`、`/dashboard/:runId` 和 `/reports/:runId` 可以独立渲染。
- Demo 页面展示自然语言输入、澄清卡、快捷案例、历史对话和内联报告操作。
- Dashboard 页面展示阶段列表、时间线和报告/下载操作。
- Report 页面展示报告内容、Verifier/Brief/Source 面板和下载按钮。
- `npm run build` 成功。
