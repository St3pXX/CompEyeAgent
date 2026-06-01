# Phase 2 Coordinator 主循环

本分支在 Coordinator Foundation 之上，加入 Coordinator 主循环、DAG 节点调度和节点级重试。主循环已经接管 run 执行状态编排。当前生产默认执行器仍兼容现有 CrewAI 顺序链路，但调度状态机已经按 DAG 节点推进，并支持替换为真正的单节点执行器。

## 已完成

- 新增 `services/coordinator_loop.py`。
- `RunService.execute_run()` 优先委托 `CoordinatorLoopService.execute()`。
- Coordinator 主循环负责：
  - 检查 run 是否已取消。
  - 初始化默认 DAG。
  - 将 run 状态更新为 `running`。
  - 发送 `run.started` 事件。
  - 根据依赖关系选择 `pending` 且依赖已完成的 ready 节点。
  - 将节点状态更新为 `running / completed / failed / skipped`。
  - 接收 `progress_callback` 并同步历史 CrewAI 进度事件。
  - 记录 `agent.started`、`agent.completed`、`agent.retrying` 事件。
  - 节点失败后按 `metadata.max_retries` 做节点级重试，默认允许 1 次重试。
  - 节点超过重试次数后标记失败，并把下游未执行节点标记为 `skipped`。
  - 持久化 report、verifier、provenance artifacts。
  - 写入 Scratchpad 中间产物和最终产物。
  - 将 run 标记为 `passed`、`needs_review` 或 `failed`。
- 新增节点级重试 API：
  - `POST /api/runs/{run_id}/dag/{node_key}/retry`
- 保留无 Coordinator service 时的 legacy 执行路径，避免破坏旧调用。

## 当前边界

- DAG 调度器已经是真实状态机，但默认生产执行器仍把现有 CrewAI 顺序链路包装在 `collect` 节点里运行，以避免在同一批改动中重写 CrewAI task 上下文。
- 调度器已经支持注入单节点 executor；后续可以把 `collect/analyze/write/verify` 分别拆成独立 CrewAI Crew 或工具函数。
- 节点级重试已经支持同一 run 内重试失败节点及其下游节点；当前前端只接入 API client，尚未在 Dashboard 上提供按钮。
- 并行执行仍未实现；当前 ready 节点按顺序执行。

## 下一步

建议下一步把默认执行器从兼容整链切换为真实单节点 CrewAI executor，然后在 Run Inspector 前端加失败节点重试按钮。
