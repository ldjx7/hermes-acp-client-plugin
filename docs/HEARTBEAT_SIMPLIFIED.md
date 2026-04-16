# 心跳机制 - 简化版设计

**日期**: 2026-04-16  
**状态**: ✅ 简化完成

---

## 核心设计

### 心跳机制 = 进度反馈

```python
# acp/heartbeat_monitor.py - 简化版
class HeartbeatMonitor:
    """
    只负责进度反馈，不判断超时
    超时由 Agent 自己处理
    """
    
    def heartbeat(self, request_id, state, progress, message):
        # 1. 调用进度回调（用户可见进展）
        if progress is not None:
            callbacks['on_progress'](request_id, progress, message)
        
        # 2. 完成时清理
        if state in ('completed', 'failed'):
            self._cleanup_request(request_id)
        
        # 3. 没有超时终止逻辑 ✅
```

---

## 工作流程

```
发送请求 → 等待 Agent 响应 → 接收结果/错误 → 返回用户
    ↓           ↓                 ↓              ↓
    │           │                 │              │
    │           ├─→ 进度更新       │              │
    │           │   (心跳通知)     │              │
    │           │                 │              │
    │           ├─→ 正常结果       │              │
    │           │   (完成)        │              │
    │           │                 │              │
    │           └─→ 错误结果       │              │
    │               (失败)        │              │
    │                             ↓              │
    └────────────────────────── 清理监控 ←───────┘
```

**关键点**：
- ✅ 心跳只负责进度反馈
- ✅ Agent 返回错误 → 正常接收并响应用户
- ✅ 不主动判断超时
- ✅ 等待 Agent 自己返回结果

---

## 使用示例

### 简单任务

```python
from tools import acp_dispatch

# 等待 Agent 返回，不设置超时
result = acp_dispatch('巴黎是哪个国家的首都？', worker='claude-cli')

# 如果 Agent 返回错误，正常显示
if 'error' in result:
    print(f"Agent 返回错误：{result['error']}")
else:
    print(f"结果：{result['output']}")
```

### 复杂任务

```python
# 复杂任务 - Agent 可能需要几分钟
result = acp_dispatch(
    '写一个完整的 Python 项目，包含文档和测试',
    worker='claude-cli'
)

# 等待 Agent 完成（可能 5-10 分钟）
# 如果超时，Agent 自己返回错误
# 如果不超时，返回正常结果
```

### 进度监控

```python
from acp.session_manager import get_session_manager

def on_progress(session_id, progress, message):
    print(f"[{progress*100:.0f}%] {message}")

manager = get_session_manager()
manager.register_progress_callback(on_progress)

result = acp_dispatch('任务...', worker='claude-cli')
# 输出：[45%] Generating code...
#      [67%] Writing tests...
#      [100%] Done!
```

---

## Agent 错误处理

### Claude CLI 错误

```
场景：API 限流、认证失败、内容违规

Claude CLI 返回:
{
    "error": {
        "code": -32000,
        "message": "API rate limit exceeded"
    }
}

我们正常接收并显示给用户:
"Agent 返回错误：API rate limit exceeded"
```

### Gemini CLI 错误

```
场景：网络错误、服务不可用

Gemini CLI 返回:
{
    "error": {
        "code": -32603,
        "message": "Internal error"
    }
}

我们正常接收并显示给用户:
"Agent 返回错误：Internal error"
```

### 不主动超时

```python
# ❌ 之前（错误）
if silence > 120s:
    return "Heartbeat timeout"  # 错误终止

# ✅ 现在（正确）
# 等待 Agent 自己返回
# 如果 Agent 返回错误，正常显示
# 如果 Agent 返回结果，正常显示
# 不主动判断超时
```

---

## 代码变更

### heartbeat_monitor.py

**删除**：
- `first_response_timeout` 参数
- `heartbeat_timeout` 参数
- `max_total_time` 参数
- `on_timeout` 回调
- 超时检测和终止逻辑

**保留**：
- `progress_threshold` 参数
- `on_progress` 回调
- 进度更新逻辑
- 完成清理逻辑
- 日志记录（仅信息，不终止）

### transport.py

**删除**：
- `on_timeout` 回调函数
- 超时检查结果处理
- `result_data['error']` 设置

**保留**：
- `on_progress` 回调
- 进度更新逻辑
- 等待结果循环
- 完成清理

---

## 日志输出

### 正常流程

```
INFO: Progress [abc123]: 0.0% - Starting...
INFO: Progress [abc123]: 25.0% - Analyzing...
INFO: Progress [abc123]: 50.0% - Generating...
INFO: Progress [abc123]: 100.0% - Done!
INFO: Request abc123 completed (total time: 45.2s)
```

### 慢任务

```
INFO: Progress [abc123]: 0.0% - Starting...
INFO: abc123: 长时间无活动 (300s)，可能是慢任务
INFO: abc123: 运行中 (600s)，进度=0%
INFO: Progress [abc123]: 10.0% - Processing...
INFO: Request abc123 completed (total time: 900.5s)
```

### Agent 错误

```
INFO: Progress [abc123]: 0.0% - Starting...
ERROR: ACP-Server (claude-cli): API rate limit exceeded
INFO: Request abc123 failed (total time: 5.2s)
```

---

## 优势对比

| 特性 | 之前（复杂） | 现在（简化） |
|------|--------------|--------------|
| 超时判断 | 心跳机制 | Agent 自己 |
| 进度反馈 | ✅ 有 | ✅ 有 |
| 错误处理 | 心跳超时 | Agent 返回 |
| 代码复杂度 | 高（300 行） | 低（200 行） |
| 维护成本 | 高 | 低 |
| 误判风险 | 高（错误终止） | 无 |

---

## 总结

### 核心原则

```
1. 等待 Agent 返回结果
2. 心跳只负责进度反馈
3. Agent 返回错误 → 正常接收并显示
4. 不主动判断超时
```

### 设计哲学

```
简单 > 复杂
信任 Agent > 主动干预
进度反馈 > 超时判断
```

### 最终状态

```
心跳监控器：~200 行
- 进度回调 ✅
- 完成清理 ✅
- 日志记录 ✅
- 超时终止 ❌

Transport 层：简化
- 移除 on_timeout ✅
- 等待 Agent 结果 ✅

用户体验：提升
- 实时进度可见 ✅
- 不会错误终止 ✅
- 错误正常显示 ✅
```

---

**简化完成日期**: 2026-04-16  
**代码行数**: 300 行 → 200 行 (-33%)  
**复杂度**: 高 → 低  
**状态**: ✅ 完成
