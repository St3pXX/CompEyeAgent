# 云部署说明

本文档用于部署 CompEye Agent 的 Web App + FastAPI + MCP，以及可选的自托管 Langfuse 可观测组件。部署形态是 FastAPI 同服务托管 React/Vite 静态资源（`/api/*`、`/sse/*` + 前端页面由同一服务返回）。

## 1. 部署方式

推荐使用 `docker-compose` 一键拉起 CompEyeAgent + Langfuse：

```bash
docker-compose up -d
```

- CompEyeAgent 暴露在 `http://<host>:8000`
- Langfuse UI 暴露在 `http://<host>:3000`（仅内网，不对外）

如果不需要 Langfuse，单独启动 CompEyeAgent 即可：

```bash
docker compose up -d compeye
```

## 2. 环境变量

### CompEyeAgent 必填

```bash
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your_api_key_here
```

### CompEyeAgent 持久化（推荐显式配置）

```bash
RUN_STORE_PATH=/data/run_store.sqlite3
COORDINATOR_STORE_PATH=/data/coordinator_store.sqlite3
SOURCE_STORE_PATH=/data/source_store.sqlite3
COMPETEYE_VECTOR_STORE_PATH=/data/vector_store
COMPETEYE_CHECKPOINT_PATH=/data/graph_checkpoints.sqlite3
```

### CompEyeAgent 模型（可选，有默认值）

```bash
COLLECTOR_MODEL=mimo-v2.5
ANALYZER_MODEL=mimo-v2.5
WRITER_MODEL=mimo-v2.5
VERIFIER_MODEL=mimo-v2.5-pro
COMPETEYE_EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5
```

### Langfuse（可选，不配置则 LLM 追踪关闭）

```bash
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

> Langfuse 密钥通过 `docker compose up` 时自动生成（见 `docker-compose.yml` 的 `healthcheck` 初始化流程）。

说明：

- 所有 `*_STORE_PATH` 目录必须放在持久化磁盘或挂载卷中，否则重启后历史任务、事件、来源索引、DAG 状态、图检查点和长期记忆丢失。
- `COMPETEYE_CHECKPOINT_PATH` 是 LangGraph 的 SQLite checkpointer 路径，支持断点续跑。
- `COMPETEYE_EMBEDDING_MODEL` 默认为 `BAAI/bge-base-zh-v1.5`（768 维，~400MB），首次启动自动下载。低内存机器可降级为 `BAAI/bge-small-zh-v1.5`。
- `PORT` 通常由云平台自动注入；本地使用 `8000`。
- 同服务部署时前端不需要 `VITE_API_BASE_URL`。

## 3. 构建命令

### Docker 构建（推荐）

```bash
docker build -t compeye-agent .
```

Dockerfile 是多阶段构建：Node 构建前端 → Python 3.12 slim 运行时。

### 手动构建

```bash
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
```

## 4. 启动命令

### Docker

```bash
# 仅 CompEyeAgent
docker run -d --name compeye -p 8000:8000 \
  -v /data/compeye:/app/data \
  -e MIMO_API_KEY=sk-xxx \
  compeye-agent

# CompEyeAgent + Langfuse
docker compose up -d
```

### 直接启动

```bash
uvicorn api_app:app --host 0.0.0.0 --port ${PORT:-8000}
```

启动后检查：

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

## 5. 平台配置示例

### 阿里云 ECS

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 拉取代码
git clone https://github.com/St3pXX/CompEyeAgent.git
cd CompEyeAgent

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 MIMO_API_KEY 等

# 4. 启动（含 Langfuse）
docker compose up -d

# 5. 验证
curl http://localhost:8000/health
curl http://localhost:3000   # Langfuse UI
```

### Render / Railway

Build command：

```bash
python -m pip install -r requirements.txt && cd frontend && npm ci && npm run build
```

Start command：

```bash
uvicorn api_app:app --host 0.0.0.0 --port $PORT
```

Environment variables（除 MiMo 密钥外，加上持久化和 Langfuse）：

```bash
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=your_api_key_here
RUN_STORE_PATH=/data/run_store.sqlite3
COORDINATOR_STORE_PATH=/data/coordinator_store.sqlite3
SOURCE_STORE_PATH=/data/source_store.sqlite3
COMPETEYE_VECTOR_STORE_PATH=/data/vector_store
COMPETEYE_CHECKPOINT_PATH=/data/graph_checkpoints.sqlite3
COLLECTOR_MODEL=mimo-v2.5
ANALYZER_MODEL=mimo-v2.5
WRITER_MODEL=mimo-v2.5
VERIFIER_MODEL=mimo-v2.5-pro
```

同时把 `/data` 挂载为持久化磁盘。

## 6. 持久化要求

| 路径 | 说明 |
|------|------|
| `RUN_STORE_PATH` | 任务记录 + 事件 |
| `COORDINATOR_STORE_PATH` | DAG 节点状态 + Scratchpad 中间产物 |
| `SOURCE_STORE_PATH` | 来源索引 + Evidence Items |
| `COMPETEYE_VECTOR_STORE_PATH` | ChromaDB 长期记忆向量库 |
| `COMPETEYE_CHECKPOINT_PATH` | LangGraph checkpointer（断点续跑） |
| `/data` | 所有数据路径的父目录，挂载为持久化磁盘或 volume |

不要把以下内容提交到 Git：

- `data/`
- `frontend/dist/`
- `frontend/node_modules/`
- `.env`
- 任何 API key、token、私钥

## 7. Langfuse 部署

`docker-compose.yml` 中已包含 Langfuse 自托管部署，包含以下服务：

- **langfuse**：Langfuse 应用服务（端口 3000）
- **langfuse-db**：PostgreSQL（Langfuse 元数据存储）

启动后首次访问 Langfuse 需注册管理员账户。后续创建 API keys（Public Key + Secret Key），填入 `.env` 的 `LANGFUSE_*` 变量，CompEyeAgent 自动通过 litellm 向 Langfuse 发送追踪数据。

**注意**：`LANGFUSE_HOST` 在 docker-compose 网络内使用 `http://langfuse:3000`（容器间通信），如 CompEyeAgent 与 Langfuse 不在同一网络，则使用实际地址。

## 8. Nginx 反向代理（生产推荐）

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # CompEyeAgent
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # SSE — 必须关闭缓冲
    location /sse/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # Langfuse（仅内网访问，不对外暴露）
    # location /langfuse/ {
    #     proxy_pass http://127.0.0.1:3000/;
    #     proxy_set_header Host $host;
    # }
}
```

## 9. 端到端验收

1. `curl /health` 返回 `{"status":"ok"}`
2. 打开 Web App，创建分析任务
3. Dashboard 实时事件流正常滚动，阶段卡片按 collect→analyze→write→verify 点亮
4. 任务完成后查看报告 Markdown、Verifier JSON、sources
5. 下载 Markdown，内容与页面一致
6. 重启服务后重新打开同一任务，确认持久化生效
7. 打开 Langfuse（`http://<host>:3000`），确认能看到 CompEyeAgent 的 LLM trace

## 10. 当前限制

- SQLite 适合单实例。多实例需升级 PostgreSQL（`storage/protocols.py` 已解耦，只需新增 PgRunStore 实现类）
- 后台任务由 FastAPI BackgroundTasks 执行，云平台如有严格请求生命周期限制需迁移到队列 worker
- SSE 经过 Nginx 时需 `proxy_buffering off`，否则事件流不实时
- bge-base-zh-v1.5 首次启动下载 ~400MB 模型权重到本地
