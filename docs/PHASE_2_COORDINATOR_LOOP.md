# Phase 2 Coordinator 主循环

本分支在 Coordinator Foundation 之上，加入第一版 Coordinator 主循环。它已经接管 run 执行状态编排，但仍复用现有 CrewAI 顺序链路作为底层执行器。

## 已完成

- 新增 `services/coordinator_loop.py`。
- `RunService.execute_run()` 优先委托 `CoordinatorLoopService.execute()`。
- Coordinator 主循环负责：
  - 检查 run 是否已取消。
  - 初始化默认 DAG。
  - 将 run 状态更新为 `running`。
  - 发送 `run.started` 事件。
  - 接收 `progress_callback` 并同步 DAG 节点状态。
  - 持久化 report、verifier、provenance artifacts。
  - 写入 Scratchpad 中间产物和最终产物。
  - 将 run 标记为 `passed`、`needs_review` 或 `failed`。
- 保留无 Coordinator service 时的 legacy 执行路径，避免破坏旧调用。

## 当前边界

- 主循环已经统一管理执行状态，但还没有把 CrewAI 的 collect/analyze/write/verify 拆成四个可单独重试的节点。
- DAG 节点状态来自现有 progress callback 和执行结果。
- 真正的节点级调度、节点级重试、并行执行仍是下一阶段。

## 下一步

建议优先做 Run Inspector 前端，把当前已有的 DAG、Scratchpad、Artifacts 可视化出来。这样在继续拆节点级调度前，先让内部状态变得可观察。
