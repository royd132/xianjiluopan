# Agent 与事件协议

## 1. Agent 契约

所有 Agent 实现统一接口：

```python
async def run(request, board, harness, trace_id) -> None:
    ...
```

Agent 从 Blackboard 读取已发布 Artifact，完成职责后发布新的 Artifact。`execute` 包装器负责发送开始/完成事件和写入 Harness Trace。

## 2. Artifact 契约

| Artifact | 发布者 | 消费者 |
|---|---|---|
| `raw_market_data` | Collector | 评论、市场、供应链 Agent |
| `evidences` | Collector | Decision Compiler、Safety Evaluator |
| `pain_points` | Review Analyzer | Decision Compiler、前端 |
| `market_metrics` | Market Analyzer | Decision Compiler |
| `supply_signals` | Supply Chain Agent | 前端、失效监控 |
| `decision_cards_draft` | Decision Compiler | Safety Evaluator |
| `decision_cards` | Safety Evaluator | API、前端、Memory |
| `evaluation` | Safety Evaluator | API、Trace |

## 3. 事件类型

| 事件 | 含义 |
|---|---|
| `task.started` | 任务创建并进入 Runtime |
| `agent.started` | Agent 开始工作 |
| `artifact.published` | 新 Artifact 已写入黑板 |
| `agent.completed` | Agent 完成工作 |
| `gate.passed` | 决策卡通过安全评测闸门 |
| `checkpoint.saved` | Harness 保存任务快照 |
| `task.completed` | 最终结果可读取 |
| `task.failed` | 任务失败并携带原因 |
| `feedback.recorded` | 人工或系统反馈已记录 |

## 4. SSE 格式

```text
event: agent.completed
data: {"event_id":"...","task_id":"...","agent":"review-analyzer","message":"review-analyzer completed","timestamp":"..."}
```

## 5. 决策卡闸门

Safety Evaluator 当前强制执行：

1. 每张卡不少于三条证据；
2. 至少一条非英语证据；
3. 必须存在 `PrivateDomainHook`；
4. 至少一项可观测的 `FailureCondition`；
5. AI 生成标记和人工复核初始状态完整。

任一条件失败，Runtime 不发布最终卡片。

## 6. 新增 Agent

新增 Agent 时：

1. 继承 `BaseAgent`；
2. 明确输入和输出 Artifact；
3. 不直接调用其他 Agent；
4. 对使用的工具经过 Harness Policy；
5. 添加独立单元测试；
6. 在 Runtime 中加入正确的依赖阶段。
