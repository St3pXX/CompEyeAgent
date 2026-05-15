# Phase 1.5 云部署说明

本文档用于部署 CompEye Agent 的 Phase 1.5 在线产品 Demo。当前部署形态是 FastAPI 同服务托管 React/Vite 静态资源，后端提供 `/api/*` 与 `/sse/*`，前端页面由同一个服务返回。

## 1. 环境变量

必填：

```bash
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your_api_key_here
```

推荐显式配置：

```bash
RUN_STORE_PATH=/data/run_store.sqlite3
COLLECTOR_MODEL=mimo-v2.5
ANALYZER_MODEL=mimo-v2.5
WRITER_MODEL=mimo-v2.5
VERIFIER_MODEL=mimo-v2.5-pro
```

说明：

- `RUN_STORE_PATH` 控制 SQLite run store 的位置。云端必须放在持久化磁盘或挂载卷中，否则应用重启或重新部署后历史任务、事件、报告索引会丢失。
- 默认值是 `data/run_store.sqlite3`，适合本地开发，不适合作为无持久卷平台的唯一存储。
- `PORT` 通常由云平台自动注入；本地可以使用 `8000`。
- 同服务部署时前端不需要 `VITE_API_BASE_URL`。只有前端和后端分开部署时，才需要在前端构建前设置 `VITE_API_BASE_URL=https://your-api-host`。

## 2. 构建命令

在仓库根目录执行：

```bash
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
```

构建完成后会生成 `frontend/dist/`。FastAPI 启动时会自动托管该目录：

- `/`、`/demo`、`/dashboard/:runId`、`/reports/:runId` 返回 React 应用
- `/assets/*` 返回前端静态资源
- `/api/*` 返回后端 REST API
- `/sse/*` 返回后端 SSE 事件流

## 3. 启动命令

Linux / 云平台：

```bash
uvicorn api_app:app --host 0.0.0.0 --port ${PORT:-8000}
```

PowerShell 本地生产模式：

```powershell
$env:PORT = "8000"
uvicorn api_app:app --host 0.0.0.0 --port $env:PORT
```

启动后检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

## 4. 持久化要求

SQLite 文件由 `RUN_STORE_PATH` 指定，目录会自动创建。云端建议：

```bash
RUN_STORE_PATH=/data/run_store.sqlite3
```

并将 `/data` 配置为持久化磁盘或 volume。

不要把以下目录或文件提交到 Git：

- `data/`
- `frontend/dist/`
- `frontend/node_modules/`
- `.env`
- 任何 API key、token、私钥

## 5. 平台配置示例

### Render / Railway / Fly.io 类平台

Build command：

```bash
python -m pip install -r requirements.txt && cd frontend && npm ci && npm run build
```

Start command：

```bash
uvicorn api_app:app --host 0.0.0.0 --port $PORT
```

Environment variables：

```bash
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your_api_key_here
RUN_STORE_PATH=/data/run_store.sqlite3
COLLECTOR_MODEL=mimo-v2.5
ANALYZER_MODEL=mimo-v2.5
WRITER_MODEL=mimo-v2.5
VERIFIER_MODEL=mimo-v2.5-pro
```

同时把 `/data` 挂载为持久化目录。

### 云服务器 / VPS

```bash
git clone https://github.com/St3pXX/CompEyeAgent.git
cd CompEyeAgent
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
export MIMO_BASE_URL=https://api.xiaomimimo.com/v1
export MIMO_API_KEY=your_api_key_here
export RUN_STORE_PATH=/data/compeye/run_store.sqlite3
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

生产环境可再接入 systemd、Nginx 反向代理和 HTTPS 证书。

## 6. 端到端验收

部署后按这个顺序验证：

1. 打开 `/health`，确认服务返回 `{"status":"ok"}`。
2. 打开 `/demo`，用自然语言填写分析需求并创建任务。
3. 自动进入 `/dashboard/{run_id}`，确认事件时间线持续更新。
4. 任务完成后进入 `/reports/{run_id}`。
5. 确认报告 Markdown、Verifier JSON、Input Brief、来源索引都能加载。
6. 下载 Markdown / JSON，确认文件内容与页面一致。
7. 重启服务后重新打开同一个 `/reports/{run_id}`，确认 `RUN_STORE_PATH` 持久化生效。

## 7. 当前限制

- Phase 1.5 使用 SQLite，适合单实例 Demo。多实例部署需要升级到 PostgreSQL 或确保只有一个实例写入同一个数据库。
- 后台任务目前由 FastAPI BackgroundTasks 执行。云平台如果有严格请求生命周期限制，后续应迁移到队列 worker。
- SSE 需要平台支持长连接；如经过 Nginx，需关闭响应缓冲。
