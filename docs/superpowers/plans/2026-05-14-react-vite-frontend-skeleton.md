# React / Vite 前端骨架实现计划

> **给 agentic workers：** 必需子技能：使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按任务逐步实现本计划。步骤使用 checkbox（`- [ ]`）语法追踪进度。

**目标：** 创建包含 Demo、Dashboard 和 Report 路由的 Phase 1.5 Web App 前端骨架。

**架构：** 前端隔离在 `frontend/` 下。React Router 负责页面路由，API helper 集中在 `src/api/`，共享外壳组件放在 `src/components/`，初始样式集中在 `src/styles.css`。

**技术栈：** Vite、React、TypeScript、React Router、浏览器 `fetch`、浏览器 `EventSource`、普通 CSS。

---

### 任务 1：搭建 Vite 文件

**文件：**
- 创建：`frontend/package.json`
- 创建：`frontend/tsconfig.json`
- 创建：`frontend/tsconfig.node.json`
- 创建：`frontend/vite.config.ts`
- 创建：`frontend/index.html`

- [ ] **步骤 1：创建 package 和配置文件**

使用 Vite + React + TypeScript。脚本必须包含 `dev`、`build` 和 `preview`。

- [ ] **步骤 2：运行安装和构建验证**

在 `frontend/` 下运行：`npm install`，然后运行 `npm run build`。

预期结果：Vite 生产构建完成。

### 任务 2：添加应用路由

**文件：**
- 创建：`frontend/src/main.tsx`
- 创建：`frontend/src/App.tsx`
- 创建：`frontend/src/components/AppShell.tsx`

- [ ] **步骤 1：接入 React Router**

路由：
- `/` 重定向到 `/demo`
- `/demo` 渲染 `DemoPage`
- `/dashboard/:runId` 渲染 `DashboardPage`
- `/reports/:runId` 渲染 `ReportPage`

- [ ] **步骤 2：添加共享外壳**

`AppShell` 提供顶部导航、Live 标记和统一页面背景。

### 任务 3：添加 API 类型和 Client

**文件：**
- 创建：`frontend/src/api/types.ts`
- 创建：`frontend/src/api/client.ts`

- [ ] **步骤 1：定义契约**

镜像后端字段：`RunRecord`、`AgentEvent`、`ArtifactRecord`、`SourceRecord`、`RunDetailResponse` 和 `CreateRunRequest`。

- [ ] **步骤 2：定义 helper**

添加 `createRun`、`getRun`、`listEvents`、`listArtifacts`、`listSources`、`getArtifact`、`openRunEventStream`，以及文本 artifact 下载 helper。

### 任务 4：添加页面骨架

**文件：**
- 创建：`frontend/src/pages/DemoPage.tsx`
- 创建：`frontend/src/pages/DashboardPage.tsx`
- 创建：`frontend/src/pages/ReportPage.tsx`
- 创建：`frontend/src/styles.css`

- [ ] **步骤 1：构建 Demo 骨架**

创建 chatbot 风格页面，包含左侧侧边栏、自然语言输入、快捷案例、澄清卡、内联结果卡、Dashboard 操作、Report 操作和下载操作。

- [ ] **步骤 2：构建 Dashboard 骨架**

创建 Agent 阶段列表、事件时间线、run 摘要、报告入口、下载操作和返回 Demo 操作。

- [ ] **步骤 3：构建 Report 骨架**

创建完整报告区域、Verifier 面板、Input Brief 面板、来源索引面板，以及 Markdown/JSON 下载按钮。

### 任务 5：更新项目文档

**文件：**
- 修改：`docs/PHASE_1_5_PLAN.md`
- 修改：`README.md`

- [ ] **步骤 1：标记前端骨架完成**

构建成功后，把 Phase 1.5 的任务 9 标记为完成。

- [ ] **步骤 2：添加前端运行命令**

记录 `cd frontend`、`npm install`、`npm run dev` 和 `npm run build`。
