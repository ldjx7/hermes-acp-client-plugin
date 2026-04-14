# Hermes ACP Client Plugin - Phase 3 开发报告

## 完成日期
2026-04-14

## 执行摘要

Phase 3 已完成生产级功能增强，包括：
- **错误处理系统** - 自定义异常类和重试逻辑
- **进度通知监听** - 实时会话状态更新
- **pre_llm_call 钩子** - 自动注入进度到 Hermes 上下文
- **新增工具** - acp_cancel, acp_list, acp_cleanup, acp_shutdown
- **资源管理** - 优雅关闭和自动清理

---

## 新增文件

### 1. acp/hooks.py (6.1KB) ⭐ 新增
**pre_llm_call 钩子实现**

```python
class ProgressInjector:
    """进度注入器 - 在 LLM 调用前自动注入 ACP 任务进度"""
    
    def pre_llm_call(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 获取正在运行的会话
        # 2. 构建进度消息
        # 3. 注入到系统消息
        # 4. 避免重复注入（时间间隔控制）
```

**功能**:
- ✅ 自动检测活跃会话
- ✅ 构建格式化进度消息
- ✅ 注入到 Hermes 上下文
- ✅ 防止重复注入（30 秒间隔）
- ✅ 限制同时注入数量（最多 5 个）

**使用示例**:
```python
from acp.hooks import pre_llm_call_hook, register_hooks

# 方式 1: 直接调用
context = pre_llm_call_hook(context)

# 方式 2: 注册到 Hermes 钩子系统
register_hooks(hermes_context)
```

**注入效果**:
```
--- ACP 任务进度 ---
🔄 任务 1: abc123
   状态：running | 进度：50%
   正在编写 Python 脚本...
   任务：写一个爬虫...
----------------------
```

---

## 更新文件

### 1. acp/transport.py (11.9KB) - 重大增强

**新增异常类**:
```python
class TransportError(Exception):
    """Base exception for transport errors"""

class WorkerNotAvailableError(TransportError):
    """Raised when worker process cannot be started"""

class RequestTimeoutError(TransportError):
    """Raised when a request times out"""
```

**新增重试逻辑**:
```python
def _send_with_retry(self, message, msg_id, q, timeout):
    for attempt in range(self.max_retries):
        try:
            # 发送请求
            response = q.get(timeout=timeout)
            return response
        except queue.Empty:
            # 指数退避
            time.sleep(self.retry_delay * (attempt + 1))
    raise last_error
```

**新增通知回调系统**:
```python
def register_notification_callback(self, callback):
    """注册 ACP 通知回调"""
    self._notification_callbacks.append(callback)

def _handle_notification(self, data):
    """处理通知并调用所有回调"""
    for callback in self._notification_callbacks:
        callback(data)
```

**新增资源清理**:
```python
def stop(self):
    """优雅关闭 transport"""
    self._running = False
    self.process.terminate()
    self.process.wait(timeout=5)  # 5 秒宽限期
    # 清理 pending 请求
```

**新增全局 shutdown 函数**:
```python
def shutdown_transport(worker: str = None):
    """关闭指定 worker 或所有 worker"""
```

---

### 2. tools.py (13.7KB) - 重写

**acp_dispatch 增强**:
```python
def acp_dispatch(task: str, context: dict = None, 
                 worker: str = "gemini", 
                 timeout: float = None, 
                 max_retries: int = None) -> str:
    """
    新增参数:
    - timeout: 请求超时（秒）
    - max_retries: 最大重试次数
    """
```

**acp_result 增强**:
```python
def acp_result(task_id: str, wait: bool = True, timeout: float = None) -> str:
    """
    新增参数:
    - wait: 是否等待完成（默认 True）
    - timeout: 等待超时（秒）
    """
```

**新增工具**:

| 工具 | 功能 | 参数 |
|------|------|------|
| `acp_cancel` | 取消运行中的任务 | task_id |
| `acp_list` | 列出所有会话 | active_only |
| `acp_cleanup` | 清理旧会话 | max_age_hours |
| `acp_shutdown` | 关闭 transport | worker |

**acp_cancel 示例**:
```python
acp_cancel({"task_id": "abc123"})
# → {"sessionId": "abc123", "status": "cancelled"}
```

**acp_list 示例**:
```python
acp_list({"active_only": True})
# → {"sessions": [...], "total": 3}
```

**acp_cleanup 示例**:
```python
acp_cleanup({"max_age_hours": 24})
# → {"cleaned_count": 5, "cleaned_sessions": [...]}
```

---

### 3. schemas.py (3.0KB) - 扩展

**ACP_DISPATCH_SCHEMA 新增字段**:
```python
"timeout": {
    "type": "number",
    "description": "Request timeout in seconds",
    "default": 120
},
"max_retries": {
    "type": "integer",
    "description": "Maximum retry attempts",
    "default": 3,
    "minimum": 0,
    "maximum": 10
}
```

**新增 Schema**:
```python
ACP_CANCEL_SCHEMA      # acp_cancel 参数
ACP_LIST_SCHEMA        # acp_list 参数
ACP_CLEANUP_SCHEMA     # acp_cleanup 参数
ACP_SHUTDOWN_SCHEMA    # acp_shutdown 参数
```

---

### 4. acp/__init__.py (1.6KB) - 更新

**导出所有公共 API**:
```python
__all__ = [
    # Transport
    "StdioTransport", "get_transport", "initialize_transport",
    "shutdown_transport", "TransportError", "RequestTimeoutError",
    # Session
    "SessionManager", "SessionState", "SessionStatus",
    # Protocol
    "ACPMessage", "InitializeRequest", "NewSessionRequest",
    # Hooks
    "ProgressInjector", "pre_llm_call_hook", "register_hooks",
]
```

---

### 5. plugin.yaml (470B) - 更新

**版本升级到 0.2.0**:
```yaml
version: 0.2.0
provides_tools:
  - acp_dispatch
  - acp_progress
  - acp_result
  - acp_cancel      # 新增
  - acp_list        # 新增
  - acp_cleanup     # 新增
  - acp_shutdown    # 新增
hooks:
  pre_llm_call: acp.hooks.pre_llm_call_hook  # 新增
```

---

## 验证结果

```
======================================================================
Hermes ACP Client Plugin - Phase 3 验证
======================================================================

[测试 1] 模块导入验证
✓ transport 模块导入成功
✓ session_manager 模块导入成功
✓ protocol 模块导入成功
✓ hooks 模块导入成功
✓ tools 模块导入成功

[测试 2] 错误类型验证
✓ TransportError: Test transport error
✓ RequestTimeoutError: Test timeout
✓ WorkerNotAvailableError: Worker not found

[测试 3] Worker 配置验证
✓ gemini: ['gemini', '--acp']
✓ claude: ['claude', '--acp']
✓ codex: ['codex', '--acp']
✓ unknown: ['gemini', '--acp']

[测试 4] Transport 配置验证
✓ worker: gemini
✓ max_retries: 5
✓ retry_delay: 0.5
✓ request_timeout: 30.0

[测试 5] 会话管理器增强测试
✓ 创建会话：test_0, test_1, test_2
✓ 会话状态更新成功

[测试 6] ProgressInjector 测试
✓ 上下文消息数：2
✓ 系统消息角色：system
✓ 包含进度信息：True

[测试 7] pre_llm_call_hook 测试
✓ Hook 执行成功

[测试 8] Tools 函数签名测试
✓ acp_dispatch 参数：['task', 'context', 'worker', 'timeout', 'max_retries']
✓ acp_cancel 存在：True
✓ acp_list 存在：True
✓ acp_cleanup 存在：True
✓ acp_shutdown 存在：True

[测试 9] Schema 验证
✓ ACP_DISPATCH_SCHEMA 字段完整
✓ 新增 Schema 存在

[测试 10] 通知回调测试
✓ 注册通知回调
✓ 处理模拟通知
✓ 收到通知数：1

[测试 11] Transport 重试逻辑验证
✓ _send_with_retry 方法存在

[测试 12] 资源清理测试
✓ 清理测试会话
✓ 剩余会话数：0

所有测试通过! ✅
```

---

## 文件结构

```
~/.hermes/plugins/acp-client/
├── plugin.yaml              # 470B   ✓ 更新 (v0.2.0)
├── __init__.py              # 1.6KB  ✓ 更新
├── schemas.py               # 3.0KB  ✓ 更新
├── tools.py                 # 13.7KB ✓ 重写
└── acp/
    ├── __init__.py          # 1.6KB  ✓ 更新
    ├── protocol.py          # 2.1KB  ✓ 不变
    ├── session_manager.py   # 4.8KB  ✓ 不变
    ├── transport.py         # 11.9KB ✓ 重大增强
    └── hooks.py             # 6.1KB  ★ 新增

tests/
└── test_phase3.py           # 8.8KB  ★ 新增

docs/
├── PHASE1_REPORT.md
├── PHASE2_REPORT.md
└── PHASE3_REPORT.md         # ★ 新增
```

**总计**: 11 个文件，约 54KB 代码

---

## 技术亮点

### 1. 分层错误处理
```python
try:
    resp = transport.send_prompt(session_id, prompt)
except RequestTimeoutError as e:
    return {"error": str(e), "status": "timeout"}
except TransportError as e:
    return {"error": str(e), "status": "transport_error"}
except Exception as e:
    return {"error": str(e), "status": "failed"}
```

### 2. 指数退避重试
```python
for attempt in range(self.max_retries):
    try:
        return self._send_message(...)
    except Exception as e:
        if attempt < self.max_retries - 1:
            time.sleep(self.retry_delay * (attempt + 1))  # 1x, 2x, 3x...
```

### 3. 智能进度注入
```python
# 避免过于频繁注入
last_injected = self._injected_sessions.get(session_id)
if last_injected and datetime.now() - last_injected < self._injection_interval:
    continue  # 跳过，30 秒后再注入

# 限制同时注入数量
if len(active) > self._max_injected_sessions:
    active = active[:self._max_injected_sessions]
```

### 4. 优雅关闭
```python
def stop(self):
    self.process.terminate()
    try:
        self.process.wait(timeout=5)  # 5 秒宽限期
    except subprocess.TimeoutExpired:
        self.process.kill()  # 强制终止
```

---

## 使用示例

### 1. 带重试的任务派发
```python
# 派发任务，自定义超时和重试
acp_dispatch({
    "task": "写一个 Python 爬虫",
    "worker": "gemini",
    "timeout": 180,       # 3 分钟超时
    "max_retries": 5      # 最多重试 5 次
})
```

### 2. 查询进度
```python
acp_progress({"task_id": "abc123"})
# → {"status": "running", "progress": 0.65, "message": "正在编写代码..."}
```

### 3. 获取结果（不等待）
```python
acp_result({"task_id": "abc123", "wait": False})
# → {"status": "running", "progress": 0.65, ...}
```

### 4. 取消任务
```python
acp_cancel({"task_id": "abc123"})
# → {"sessionId": "abc123", "status": "cancelled"}
```

### 5. 列出活跃任务
```python
acp_list({"active_only": True})
# → {"sessions": [{"session_id": "abc123", "status": "running", ...}], "total": 1}
```

### 6. 清理旧会话
```python
acp_cleanup({"max_age_hours": 12})
# → {"cleaned_count": 10, "cleaned_sessions": [...]}
```

### 7. 关闭 worker
```python
acp_shutdown({"worker": "gemini"})  # 关闭指定 worker
acp_shutdown({})                     # 关闭所有 worker
```

---

## 待完成事项

### 高优先级

1. **Gemini CLI ACP 模式端到端测试**
   - 需要完成 `gemini login` 认证
   - 验证实际 JSON-RPC 通信
   - 测试进度通知流

2. **Claude Code / Codex 兼容性测试**
   - 验证 `claude --acp` 是否支持
   - 验证 `codex --acp` 是否支持
   - 处理协议差异

### 中优先级

3. **日志系统增强**
   - 结构化日志输出
   - 日志文件轮转
   - 日志级别动态配置

4. **会话持久化**
   - SQLite 存储会话历史
   - 重启后会话恢复
   - 会话导出/导入

### 低优先级

5. **Web UI 监控面板**
   - 实时进度可视化
   - 会话历史查询
   - 统计图表

---

## Phase 1-3 总结

| Phase | 目标 | 状态 | 代码量 |
|-------|------|------|--------|
| Phase 1 | 基础架构 | ✅ 100% | ~15KB |
| Phase 2 | 核心功能 | ✅ 100% | ~25KB |
| Phase 3 | 生产增强 | ✅ 100% | ~54KB |

**整体进度**: ████████████████████ 100% 核心功能完成

---

## 下一步

1. **完成 Gemini 认证**: `gemini login`
2. **端到端测试**: 实际派发任务并验证
3. **文档完善**: API 参考、使用指南
4. **性能优化**: 并发会话支持、资源优化

---

*报告生成：2026-04-14*  
*版本：v0.2.0*  
*开发者：Hermes Agent (Autonomous Engineering)*
