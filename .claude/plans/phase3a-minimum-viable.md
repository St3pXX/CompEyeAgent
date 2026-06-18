# Phase 3A 实施计划：最小可用 3 项

## 目标

实现 Phase 3A 的三个最小可用交付物，为后续 PostgreSQL、RBAC、长期记忆等打下基础：
1. **存储抽象层** — Protocol 接口，SQLite / PostgreSQL 可切换
2. **韧性设计** — 熔断器、节点超时、部分结果交付
3. **多模型降级** — 模型注册表 + 按优先级 fallback + 健康追踪

---

## 子计划 1：存储抽象层

### 1.1 创建 `storage/protocols.py` — Protocol 接口定义

定义三个 Protocol 类（Python `typing.Protocol`，运行时鸭子类型，不需要继承）：

```python
class RunStoreProtocol(Protocol):
    def create_run(self, input_data: dict, parent_run_id: str | None = None) -> RunRecord: ...
    def get_run(self, run_id: str) -> RunRecord: ...
    def update_run_status(self, run_id: str, status: str, ...) -> RunRecord: ...
    def list_runs(self, limit: int = 50) -> list[RunRecord]: ...
    def append_event(self, run_id: str, event_type: str, message: str, ...) -> AgentEvent: ...
    def list_events(self, run_id: str, after_event_id: int = 0) -> list[AgentEvent]: ...
    def create_artifact(self, run_id: str, kind: str, content: str) -> ArtifactRecord: ...
    def list_artifacts(self, run_id: str) -> list[ArtifactRecord]: ...
    def create_sources(self, run_id: str, sources: list) -> list[SourceRecord]: ...
    def list_sources(self, run_id: str) -> list[SourceRecord]: ...

class CoordinatorStoreProtocol(Protocol):
    def create_node(self, ...) -> DAGNode: ...
    def get_node(self, run_id: str, key: str) -> DAGNode: ...
    def list_nodes(self, run_id: str) -> list[DAGNode]: ...
    def update_node_status(self, run_id: str, key: str, status: str) -> None: ...
    def write_scratchpad_item(self, item: ScratchpadItem) -> ScratchpadItem: ...
    def get_scratchpad_item(self, run_id: str, path: str) -> ScratchpadItem: ...
    def list_scratchpad_items(self, run_id: str) -> list[ScratchpadItem]: ...

class SourceStoreProtocol(Protocol):
    def upsert_seed(self, seed: SourceSeed) -> SourceSeed: ...
    def list_seeds(self, ...) -> list[SourceSeed]: ...
    def upsert_document(self, doc: RawDocument) -> RawDocument: ...
    def upsert_evidence(self, item: EvidenceItem) -> EvidenceItem: ...
    def query_evidence(self, competitor: str, dimensions: list[str]) -> list[EvidenceItem]: ...
    def list_fetch_events(self, limit: int = 100) -> list[SourceFetchEvent]: ...
```

### 1.2 更新 `storage/run_store.py`

让 `SQLiteRunStore` 显式声明它满足 `RunStoreProtocol`（可选，鸭子类型已经够用）。不改内部实现。

### 1.3 更新消费端类型标注

将以下文件中对具体 SQLite 类的引用改为 Protocol 类型：
- `services/run_service.py`：`store: RunStoreProtocol`
- `services/coordinator_loop.py`：`run_store: RunStoreProtocol`
- `services/coordinator_foundation.py`：`store: CoordinatorStoreProtocol`
- `services/evidence_service.py`：`store: SourceStoreProtocol`
- `api_app.py`：模块级变量类型标注

SQLite 实现保持不变，PostgreSQL 迁移时只需新增实现类并替换实例化。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `storage/protocols.py` | **新建** — Protocol 接口 |
| `storage/run_store.py` | 修改 — 类型标注 |
| `storage/coordinator_store.py` | 修改 — 类型标注 |
| `storage/source_store.py` | 修改 — 类型标注 |
| `services/run_service.py` | 修改 — 参数类型改为 Protocol |
| `services/coordinator_loop.py` | 修改 — 参数类型改为 Protocol |
| `services/coordinator_foundation.py` | 修改 — 参数类型改为 Protocol |
| `services/evidence_service.py` | 修改 — 参数类型改为 Protocol |
| `api_app.py` | 修改 — 模块级变量类型标注 |
| `tests/test_store_protocols.py` | **新建** — 验证 SQLite 实现满足 Protocol |

---

## 子计划 2：韧性设计

### 2.1 创建 `services/resilience.py` — 熔断器 + 超时

```python
class CircuitBreaker:
    """Per-provider circuit breaker with configurable failure threshold and cooldown."""
    
    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 60): ...
    def call(self, fn, *args, **kwargs): ...  # Raises CircuitOpenError if open
    def record_success(self): ...
    def record_failure(self): ...
    @property
    def state(self) -> Literal["closed", "open", "half_open"]: ...

class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
```

### 2.2 创建 `services/node_timeout.py` — 节点超时

为每个 DAG 节点增加可配置的执行超时（通过 `node.metadata["timeout_seconds"]`）。

在 `_execute_node_with_retry()` 中用 `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=...)` 实现超时中断。超时视为节点失败，走正常重试流程。

### 2.3 修改 `coordinator_loop.py` — 部分结果交付

当 verify 节点失败但 write 节点已成功时，将 run 状态设为 `needs_review` 而非 `failed`，并将已有的报告作为草稿交付。

在 `_execute_dag()` 中：当检测到 failed 节点时，检查是否有已生成的报告。如果有，返回部分结果而非抛异常。

### 2.4 集成熔断器到节点执行器

在 `node_executors.py` 的 `_run_single_crew()` 中，用 `CircuitBreaker.call()` 包裹 `crew.kickoff()` 调用。熔断器按模型提供者（而非节点）维度管理。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `services/resilience.py` | **新建** — CircuitBreaker |
| `services/coordinator_loop.py` | 修改 — 超时 + 部分结果交付 |
| `services/node_executors.py` | 修改 — 集成熔断器 |
| `tests/test_resilience.py` | **新建** — 熔断器 + 超时测试 |

---

## 子计划 3：多模型降级

### 3.1 创建 `config/model_registry.py` — 模型注册表

```python
@dataclass
class ModelProvider:
    name: str           # "mimo", "openai", "anthropic"
    base_url: str
    api_key: str
    model_name: str
    priority: int       # 1 = primary, 2 = fallback, ...
    enabled: bool = True

class ModelRegistry:
    """Registry of model providers per agent role, with fallback ordering."""
    
    def __init__(self): ...
    def register(self, role: str, provider: ModelProvider): ...
    def get_providers(self, role: str) -> list[ModelProvider]: ...  # sorted by priority
    def create_llm(self, role: str) -> LLM: ...  # Try providers in order, use CircuitBreaker
```

### 3.2 配置格式

通过环境变量或 YAML 配置 fallback 链：

```bash
# 主模型
MIMO_BASE_URL=https://api.xiaomimimo.com/v1
MIMO_API_KEY=sk-xxx

# Fallback（可选）
FALLBACK_PROVIDER=openai
FALLBACK_BASE_URL=https://api.openai.com/v1
FALLBACK_API_KEY=sk-yyy
FALLBACK_MODEL=gpt-4o-mini
```

或更灵活的 YAML：
```yaml
collector:
  - provider: mimo
    model: mimo-v2.5
    priority: 1
  - provider: openai
    model: gpt-4o-mini
    priority: 2
```

### 3.3 修改 `config/settings.py`

将 `create_llm()` 改为从 `ModelRegistry` 获取，自动 fallback。保留向后兼容：当只配置了 `MIMO_BASE_URL` 时，行为与现在完全一致。

### 3.4 健康追踪

复用子计划 2 的 `CircuitBreaker`，每个 provider 一个熔断器实例。当主模型连续失败时，熔断器打开，`create_llm()` 自动跳到下一个 provider。

### 涉及文件

| 文件 | 操作 |
|------|------|
| `config/model_registry.py` | **新建** — ModelProvider + ModelRegistry |
| `config/settings.py` | 修改 — `create_llm()` 改用 ModelRegistry |
| `config/model_config.yaml` | **新建** — 可选 YAML 配置 |
| `tests/test_model_registry.py` | **新建** — 注册表 + fallback 测试 |

---

## 实施顺序

```
子计划 1（存储抽象层）  ← 最先，无风险，不改行为
        ↓
子计划 2（韧性设计）    ← 依赖 CircuitBreaker
        ↓
子计划 3（多模型降级）  ← 复用 CircuitBreaker
```

## 验证

```bash
# 子计划 1
python -m pytest tests/test_store_protocols.py -v
python -m pytest  # 回归

# 子计划 2
python -m pytest tests/test_resilience.py -v
python -m pytest  # 回归

# 子计划 3
python -m pytest tests/test_model_registry.py -v
python -m pytest  # 回归

# 最终全量
python -m pytest -q
```
