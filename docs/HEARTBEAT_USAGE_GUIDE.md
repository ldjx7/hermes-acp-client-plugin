# ACP 心跳超时机制 - 使用指南

**状态**: ✅ 已完成并测试  
**日期**: 2026-04-16

---

## 快速开始

### 默认使用（推荐）

```python
from tools import acp_dispatch

# 简单任务 - 自动适应
result = acp_dispatch("巴黎是哪个国家的首都？", worker="claude-cli")

# 复杂任务 - 自动支持长时间运行
result = acp_dispatch(
    "请审查这个项目的代码质量...",
    worker="claude-cli"
)
```

**无需配置** - 心跳机制自动启用！

---

## 工作原理

```
发送请求 → 注册心跳监控 → 等待响应
    ↓
    ├─ 收到 running → ✓ 重置心跳计时器
    ├─ 收到 progress → ✓ 重置心跳计时器
    ├─ 收到 completed → ✓ 清理监控
    └─ 120s 无活动 → × 判定超时
```

**超时策略**:
1. **首次响应**: 30 秒内必须收到第一个响应
2. **心跳超时**: 120 秒无活动判定失败
3. **最大时间**: 1800 秒（30 分钟）强制终止

---

## 配置参数

### 全局配置

```python
# acp/heartbeat_monitor.py
heartbeat_monitor = HeartbeatMonitor(
    first_response_timeout=30.0,   # 首次响应超时
    heartbeat_timeout=120.0,       # 心跳超时（已增加到 120 秒）
    max_total_time=1800.0,         # 最大总时间
    progress_threshold=0.01        # 最小进度变化
)
```

### 自定义配置

```python
from acp.transport import get_transport

transport = get_transport(worker="claude-cli")

# 针对特定任务调整
transport.heartbeat_timeout = 180.0      # 3 分钟心跳超时
transport.max_total_time = 3600.0        # 1 小时最大时间

result = transport.send_prompt(session_id, "复杂任务...")
```

---

## 使用场景

### 场景 1: 快速问答

```python
result = acp_dispatch("巴黎是哪个国家的首都？")
# ✅ 1-3 秒完成，首次响应检测正常
```

### 场景 2: 代码生成

```python
result = acp_dispatch(
    "实现一个快速排序算法，包含注释和测试",
    worker="claude-cli"
)
# ✅ 30-60 秒完成，进度可见
```

### 场景 3: 代码审查

```python
result = acp_dispatch(
    """
    请审查这个项目的代码质量：
    1. 检查所有 Python 文件
    2. 识别性能问题
    3. 提出重构建议
    """,
    worker="claude-cli",
    timeout=600  # 10 分钟
)
# ✅ 5-10 分钟完成，持续进度更新
```

### 场景 4: 项目分析

```python
result = acp_dispatch(
    """
    分析整个项目架构：
    - 模块划分
    - 依赖关系
    - 潜在问题
    - 优化建议
    """,
    worker="claude-cli"
)
# ✅ 10-20 分钟完成，心跳机制防止过早超时
```

---

## 进度监控

### 查看实时进度

```python
from acp.session_manager import get_session_manager

def on_progress(session_id, progress, message):
    print(f"\r[{progress*100:5.1f}%] {message}", end="", flush=True)

manager = get_session_manager()
manager.register_progress_callback(on_progress)

result = acp_dispatch("任务...", worker="claude-cli")
# 输出：[ 45.3%] Analyzing code structure...
```

### 查询任务状态

```python
from acp.heartbeat_monitor import heartbeat_monitor

status = heartbeat_monitor.get_status(request_id)
if status:
    print(f"状态：{status['current_state']}")
    print(f"进度：{status['last_progress']*100:.1f}%")
    print(f"消息：{status['progress_message']}")
    print(f"静默：{status['silence_seconds']}s")
```

---

## 错误处理

### 超时类型

| 超时类型 | 原因 | 解决方法 |
|----------|------|----------|
| `first_response` | 30 秒无首次响应 | 检查 Agent 是否正常启动 |
| `heartbeat` | 120 秒无活动 | 增加 `heartbeat_timeout` |
| `max_total` | 超过 30 分钟 | 增加 `max_total_time` |

### 处理超时

```python
from tools import acp_dispatch
import json

result = acp_dispatch("任务...", worker="claude-cli")
data = json.loads(result)

if data.get('status') == 'failed':
    timeout_type = data.get('timeout_type', 'unknown')
    
    if timeout_type == 'first_response':
        print("Agent 启动失败，请检查配置")
    elif timeout_type == 'heartbeat':
        print("Agent 长时间无响应，可能卡住")
    elif timeout_type == 'max_total':
        print("任务超时，考虑拆分任务")
```

---

## 最佳实践

### 1. 选择合适的超时

```python
# 简单任务 - 使用默认
acp_dispatch("简单问题")

# 中等任务 - 5-10 分钟
acp_dispatch("代码生成", timeout=600)

# 复杂任务 - 15-30 分钟
acp_dispatch("项目分析", timeout=1800)
```

### 2. 监控进度

```python
# 注册进度回调
manager = get_session_manager()
manager.register_progress_callback(lambda sid, p, m: print(f"{p*100:.0f}% {m}"))

# 执行任务
result = acp_dispatch("任务...")
```

### 3. 处理慢启动 Agent

```python
# Claude CLI 可能启动较慢（30-60 秒）
# 已配置 120 秒心跳超时，通常足够

# 如果仍然超时，增加超时时间
from acp.transport import get_transport
transport = get_transport(worker="claude-cli")
transport.heartbeat_timeout = 180.0  # 3 分钟
```

### 4. 拆分超大任务

```python
# ❌ 不要：单个超大任务
acp_dispatch("分析整个 GitHub 组织的所有项目...")

# ✅ 推荐：拆分成小任务
acp_dispatch("分析项目 A 的代码质量")
acp_dispatch("分析项目 B 的代码质量")
# ...
```

---

## 技术细节

### 心跳通知格式

```javascript
// Claude Adapter 发送的心跳通知
sendNotification('session/state', {
    sessionId: 'session-xxx',
    state: 'running',
    progress: 0.45,
    message: 'Generating response... (45%)'
})
```

### Python 端处理

```python
# transport.py: _handle_notification
if method == "session/state":
    session_id = params.get("sessionId")
    state = params.get("state", "running")
    progress = params.get("progress")
    message = params.get("message", "")
    
    request_id = self._session_to_request.get(session_id)
    if request_id:
        heartbeat_monitor.heartbeat(
            request_id=request_id,
            state=state,
            progress=progress,
            message=message
        )
```

---

## 测试验证

### 单元测试

```bash
cd /root/.hermes/plugins/acp-client
python3 tests/test_heartbeat.py
```

### 集成测试

```bash
# 测试心跳机制
bash tests/run_with_env.sh -c "
from tools import acp_dispatch
result = acp_dispatch(
    '实现一个完整的 Python 工具类',
    worker='claude-cli',
    timeout=300
)
print(result)
"
```

---

## 常见问题

### Q: 为什么我的心跳超时了？

**A**: 可能原因：
1. Agent 启动慢（>120 秒）- 增加 `heartbeat_timeout`
2. Agent 处理卡住 - 检查任务复杂度
3. 网络问题 - 检查 API 连接

### Q: 如何禁用心跳监控？

**A**: 不推荐，但可以：
```python
from acp.transport import get_transport
transport = get_transport(worker="claude-cli")
# 使用传统 send 方法（不推荐）
response = transport.send(req, timeout=300)
```

### Q: 心跳监控影响性能吗？

**A**: 几乎无影响：
- 内存：~1KB/请求
- CPU: <0.1%
- 延迟：无（异步）

---

## 总结

**核心优势**:
- ✅ 自动适应任务复杂度
- ✅ 支持超长任务（最长 30 分钟）
- ✅ 实时进度可见
- ✅ 检测 Agent 假死

**默认配置**:
- 首次响应：30 秒
- 心跳超时：120 秒
- 最大时间：1800 秒

**使用建议**:
- 简单任务：无需配置
- 复杂任务：增加 `timeout` 参数
- 超大任务：拆分成小任务

---

**文档版本**: 1.0  
**最后更新**: 2026-04-16
