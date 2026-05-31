# Phase 2 Coordinator Foundation

本分支在 Source Layer 子里程碑之后，开始建设 Phase 2 的 Coordinator Foundation。当前阶段只补 DAG、Scratchpad 和 Inspector 的基础数据层，不替换现有 CrewAI 执行链路。

## 本批已完成

- DAG schema：描述 run 内部节点和依赖边。
- Scratchpad schema：保存每个 run 的 JSON、Markdown、文本类中间产物。
- SQLite 持久化：`storage/coordinator_store.py`。
- Foundation 服务层：`services/coordinator_foundation.py`。
- `RunService.create_run()` 会同步创建默认 DAG，并写入 `input/brief.json`。
- 现有 `progress_callback` 会把 DAG 节点从 `pending` 更新为 `running / completed`。
- 现有执行结束后，会把报告、Verifier JSON、Provenance Index 写入 Scratchpad：
  - `collect/raw.json`
  - `analyze/findings.json`
  - `write/report.md`
  - `verify/verifier.json`
  - `verify/provenance_index.json`
- `collect`、`analyze`、`write` 和 `verify` 节点会记录对应的 `input_refs / output_refs`。
- API 接入：
  - `GET /api/runs/{run_id}/dag`
  - `GET /api/runs/{run_id}/scratchpad`
  - `POST /api/runs/{run_id}/scratchpad`
  - `GET /api/runs/{run_id}/inspector`

## 默认 DAG

默认 DAG 对齐当前 CrewAI 顺序链路：

```text
collect -> analyze -> write -> verify
```

创建 run 时会初始化这条默认 DAG，并把原始 run input 写入 Scratchpad 的 `input/brief.json`。如果历史 run 没有 DAG，请求 `/api/runs/{run_id}/dag` 时仍会懒初始化。

## 本批明确不做

- 不实现 Coordinator 主循环。
- 不实现 DAG 节点调度执行。
- 不替换 `RunService.execute_run()`。
- 不实现前端 Run Inspector UI。

## 下一批

下一批可以在两个方向里选一个：一是做前端 Run Inspector，把 DAG 和 Scratchpad 可视化出来；二是开始真正的 Coordinator 主循环，把 CrewAI 顺序链路逐步拆成可调度节点。
