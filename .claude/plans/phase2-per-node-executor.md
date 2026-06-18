# Phase 2 完成计划：逐节点独立执行器

## 背景

当前 DAG 调度器（`coordinator_loop.py`）已完整实现节点状态机、依赖推进、节点级重试。但默认执行器 `_legacy_chain_node_executor()` 将整条 CrewAI 链路（collect→analyze→write→verify）作为一个整体运行在 `collect` 节点里，其余节点被跳过。Phase 2 的核心缺口是：**每个 DAG 节点拥有独立的执行逻辑，通过 Scratchpad 传递上下文**。

## 实施步骤

### Step 1: 创建逐节点执行器 `services/node_executors.py`

新建文件，实现四个独立的节点执行函数，每个函数：
- 从 `context` 读取输入数据和 evidence index
- 从 Scratchpad 读取上游节点输出（而非依赖 CrewAI `context=[previous_task]`）
- 创建独立的单节点 CrewAI Crew
- 执行并将输出写入 Scratchpad
- 返回 `NodeExecutionResult`

关键设计：
- **collect 节点**：读 `context["input_data"]` + `context["evidence_index"]`，创建 `Crew(collector, [collect_task])`，输出写 `collect/raw.json`
- **analyze 节点**：从 Scratchpad 读 `collect/raw.json`，创建新 Task（description 中注入上游数据），`Crew(analyzer, [task])`，输出写 `analyze/findings.json`
- **write 节点**：从 Scratchpad 读 `analyze/findings.json`，创建新 Task，`Crew(writer, [task])`，输出写 `write/report.md`
- **verify 节点**：从 Scratchpad 读 `write/report.md`，创建新 Task，`Crew(verifier, [task])`，输出写 `verify/verifier.json`

创建一个 `per_node_executor()` 函数，根据 `node.key` 分发到对应的执行逻辑。此函数签名兼容 `coordinator_loop.py` 中 `node_executor` 的调用约定。

### Step 2: 从 `runner.py` 提取验证逻辑

将以下函数从 `runner.py` 提取到 `services/verification.py`（新文件）：
- `_provenance_guard()`
- `_verification_issues()`
- `_parse_verifier_result()`
- `_claim_like_lines()`

这样 `runner.py`（Phase 1 兼容路径）和新的逐节点执行器都可以复用这些逻辑，避免代码重复。

`runner.py` 改为从 `services/verification.py` 导入这些函数。

### Step 3: 更新 `coordinator_loop.py`

修改 `_persist_success()` 方法：
- 当前：依赖 `result.passed`、`result.report`、`result.verifier_result`（`AnalysisRunResult` 字段）
- 改为：从 Scratchpad 读取 `write/report.md` 和 `verify/verifier.json`，然后调用 `verification.py` 中的验证逻辑判断 `passed`

这样 `_persist_success()` 不再依赖 `AnalysisRunResult`，而是从 Scratchpad 组装最终结果。

同时需要修改 `_execute_dag()` 的完成判断：
- 当前：`context["final_result"]` 不为 None 时才认为完成
- 改为：所有节点 completed/skipped 时，从 Scratchpad 组装 `final_result`，不再要求 executor 返回 `final_result`

### Step 4: 更新 `run_service.py` 注入点

在 `execute_run()` 中，当 `coordinator_loop` 存在时，传入 `node_executor=per_node_executor`：

```python
from services.node_executors import per_node_executor

self.coordinator_loop.execute(
    run_id,
    input_data=run.input,
    allow_retry=allow_retry,
    evidence_index=self._evidence_index_for_input(run.input),
    run_analysis=run_analysis,
    node_executor=per_node_executor,
)
```

同样更新 `retry_node()` 的调用。

### Step 5: 保留 Phase 1 兼容路径

`runner.py` 中的 `run_analysis()` 保持不变，作为 `main.py` 和 `app.py`（Streamlit）的直接调用入口。`_legacy_chain_node_executor()` 也保留在 `coordinator_loop.py` 中作为 fallback（当 `node_executor=None` 时使用）。

### Step 6: 更新测试

- 新增 `tests/test_node_executors.py`：测试每个节点执行器的独立运行（mock CrewAI kickoff）
- 新增 `tests/test_verification.py`：测试提取出的验证逻辑
- 更新 `tests/test_coordinator_foundation.py`：确保 DAG 逐节点推进的测试通过

### Step 7: 端到端验证

1. 启动 FastAPI：`uvicorn api_app:app --port 8000`
2. 启动前端：`cd frontend && npm run dev`
3. 通过 `/demo` 创建一个分析任务
4. 验证 Dashboard 上四个节点（collect→analyze→write→verify）依次从 pending→running→completed
5. 验证每个节点的 Scratchpad 产物可读
6. 验证报告、质检结果和来源索引正确生成

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/node_executors.py` | **新建** | 四个逐节点执行器 + 分发函数 |
| `services/verification.py` | **新建** | 从 runner.py 提取的验证逻辑 |
| `services/coordinator_loop.py` | 修改 | `_persist_success` 改为从 Scratchpad 组装结果 |
| `services/run_service.py` | 修改 | 注入 `per_node_executor` |
| `runner.py` | 修改 | 验证逻辑改为从 verification.py 导入 |
| `tests/test_node_executors.py` | **新建** | 逐节点执行器单元测试 |
| `tests/test_verification.py` | **新建** | 验证逻辑单元测试 |
| `tests/test_coordinator_foundation.py` | 修改 | 更新 DAG 推进测试 |

## 验证命令

```bash
python3 -m pytest tests/test_node_executors.py -v
python3 -m pytest tests/test_verification.py -v
python3 -m pytest tests/test_coordinator_foundation.py -v
python3 -m pytest   # 全量测试
```

## 风险与缓解

- **CrewAI Task context 注入**：逐节点执行需要将 Scratchpad 内容注入 Task description。如果内容过长，可能超出模型上下文。缓解：对上游输出做截断（保留前 4000 字符）。
- **CrewAI Agent 单例**：模块级 Agent 单例在多次 kickoff 时可能有状态残留。缓解：CrewAI 的 `kickoff()` 设计上是幂等的，单例可安全复用。
- **Phase 1 回归**：`runner.py` 的改动仅限导入路径，不改逻辑。`main.py` 和 `app.py` 不受影响。
