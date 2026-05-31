# AGENTS.md

本文件是 `CompEyeAgent` 仓库的项目级协作说明。若与全局偏好冲突，以本文件中更贴近本项目的规则为准。

## 项目概览

- 这是一个 Python 3.11+ 的 AI 竞品分析 Agent 协作系统。
- 当前核心链路是 Collector -> Analyzer -> Writer -> Verifier，并通过 provenance guard 保证报告结论可溯源。
- 后端入口包括 `main.py`、`runner.py`、`api_app.py` 和 `app.py`。
- 前端位于 `frontend/`，开发时通常由 Vite 代理到本地 FastAPI。
- 设计和部署背景优先参考 `README.md`、`docs/DESIGN.md`、`docs/PHASE_1_5_PLAN.md`、`docs/DEPLOYMENT.md`。

## 开发约定

- 修改前先读相关模块和测试，保持现有结构和命名风格。
- 优先做小而清晰的改动，避免为单点需求引入大抽象。
- 涉及 Agent 职责、任务链路、provenance、run store 或 SSE 事件时，要同步考虑端到端行为。
- 报告、证据、质检结果等结构化对象应优先使用 `models/` 中已有 schema。
- 不要把密钥、token、SSH 私钥、真实 API key、模型权重、日志、数据库文件或构建产物提交进仓库。
- `.env` 只用于本地；示例配置放在 `.env.example`。

## 常用命令

后端依赖安装：

```bash
python3 -m pip install -r requirements.txt
```

运行测试：

```bash
python3 -m pytest
```

启动 FastAPI：

```bash
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

启动 React 开发服务器：

```bash
cd frontend
npm install
npm run dev
```

构建前端：

```bash
cd frontend
npm run build
```

## 验证要求

- Python 后端改动优先运行相关 pytest；不确定影响面时运行完整 `python3 -m pytest`。
- 前端改动至少运行 `npm run build`；交互或布局改动需要在浏览器中检查关键页面。
- API、SSE、run store 或前后端联动改动，要尽量验证一次本地后端与前端代理链路。
- 如果因为缺少依赖、密钥或外部服务无法验证，要在回复中明确说明未验证的部分和原因。

## Git 规则

- 不要使用 `git add -A`，除非用户明确要求。
- 不要回滚用户已有改动；遇到无关未提交文件时保持原样。
- 不要提交 `frontend/dist/`、本地数据库、缓存、日志、模型文件或密钥文件。
- 新增忽略规则前先检查现有 `.gitignore`。

## CodeGraph

- 本仓库可能使用 `.codegraph/` 索引。结构性问题优先使用 CodeGraph 工具。
- 查找符号定义、调用关系、影响范围时优先用 `codegraph_*`；查找字面文本时使用 `rg`。
- CodeGraph 索引会有短暂延迟，刚编辑完文件后不要立即依赖它确认最新内容。
