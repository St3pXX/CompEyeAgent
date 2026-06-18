# Async Generator 升级计划

## 背景

当前 SSE 事件流是 **数据库轮询**：`coordinator_loop` 同步写 SQLite → SSE 端点每秒轮询 `list_events()` → 推送给前端。延迟 0-1 秒，每客户端每秒 2 次 SQLite 查询。

Phase 2 目标：用 **内存事件队列** 替代轮询，事件从 Coordinator 直推 SSE 端点，延迟降至毫秒级，零轮询开销。同时保留 SQLite 持久化，支持断线重连。

## 设计

```
Coordinator (sync thread)
  -> EventQueue.put(event)  [thread-safe, via call_soon_threadsafe]
    -> SSE _event_stream() awaits queue.get()
      -> yields SSE text to frontend EventSource
```

**关键约束**：CrewAI `kickoff()` 是同步阻塞调用，不能改为 async。因此 Coordinator 仍运行在 `BackgroundTasks` 线程中，通过 `asyncio.Queue` + `loop.call_soon_threadsafe()` 桥接到 async SSE 端点。

## 实施步骤

### Step 1: 新建 `services/event_bus.py` — 内存事件总线

```python
class EventBus:
    """Per-run async event queue bridging sync coordinator to async SSE."""
    
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
    
    def create(self, run_id: str) -> asyncio.Queue:
        """Create a queue for a run (called from async context)."""
    
    def publish(self, run_id: str, event: dict):
        """Put event into queue (called from sync thread via call_soon_threadsafe)."""
    
    def close(self, run_id: str):
        """Signal stream end (put sentinel None)."""
    
    def get_queue(self, run_id: str) -> asyncio.Queue | None:
        """Get existing queue for a run."""
```

### Step 2: 修改 `coordinator_loop.py` — 双写模式

在 `append_event()` 调用的同时，如果 `event_bus` 存在，也推送到内存队列：

- `execute()` 接受可选 `event_bus` 参数
- `_emit()` 辅助方法：先 `run_store.append_event()` 持久化，再 `event_bus.publish()` 直推
- 所有现有的 `append_event()` 调用改为通过 `_emit()` 双写
- `execute()` 结束时调用 `event_bus.close()` 发送结束信号

这样做的好处：
- SQLite 持久化保留，支持断线重连（`after_event_id` 机制不变）
- 内存队列提供毫秒级实时推送
- `event_bus=None` 时回退到纯数据库模式（向后兼容）

### Step 3: 修改 `run_service.py` — 传递 event_bus

- `execute_run()` 接受可选 `event_bus` 参数，透传给 `coordinator_loop.execute()`

### Step 4: 修改 `api_app.py` — SSE 端点使用事件队列

改造 `stream_run_events()` 和 `_event_stream()`：

1. 如果 `EventBus` 有该 run 的队列 → 直接 await 队列（零轮询）
2. 队列不存在（run 已结束或旧模式）→ 回退到现有数据库轮询
3. 收到 `None` 哨兵 → 发送 `stream.closed` 并结束

启动 run 时创建队列：
```python
@app.post("/api/runs")
async def create_run(..., background_tasks: BackgroundTasks):
    ...
    queue = event_bus.create(run.run_id)
    background_tasks.add_task(run_service.execute_run, run.run_id, ..., event_bus=event_bus)
```

### Step 5: 前端无需改动

SSE 协议完全不变：相同的事件类型、相同的 `id:` 字段、相同的 `stream.closed` 哨兵。前端 `EventSource` 无需任何修改。

### Step 6: 更新测试

- 新增 `tests/test_event_bus.py`：测试 EventBus 的 create/publish/close/get_queue
- 更新 `tests/test_coordinator_foundation.py`：验证双写模式下事件同时进入 SQLite 和内存队列

## 涉及文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `services/event_bus.py` | **新建** | 内存事件总线 |
| `services/coordinator_loop.py` | 修改 | `_emit()` 双写 + event_bus 参数 |
| `services/run_service.py` | 修改 | 透传 event_bus |
| `api_app.py` | 修改 | SSE 端点优先使用事件队列 |
| `tests/test_event_bus.py` | **新建** | EventBus 单元测试 |
| `tests/test_coordinator_foundation.py` | 修改 | 适配双写模式 |

## 不涉及的文件

- **前端代码**：SSE 协议不变，`DashboardPage.tsx`、`client.ts` 无需改动
- **CrewAI 代码**：`kickoff()` 保持同步，通过线程桥接
- **models/**：`AgentEvent` 模型不变
- **storage/**：SQLite 持久化逻辑不变

## 验证

```bash
python -m pytest tests/test_event_bus.py -v
python -m pytest tests/test_coordinator_foundation.py -v
python -m pytest  # 全量
```
