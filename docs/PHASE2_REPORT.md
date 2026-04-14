# Hermes ACP Client Plugin - Phase 2 开发报告

## 完成日期
2026-04-13

## 执行摘要

Phase 2 已完成 ACP 协议消息实现和会话管理器开发。核心组件包括：
- **ACP Protocol** - 完整的 JSON-RPC 2.0 消息实现
- **Session Manager** - 会话生命周期管理
- **Transport Layer** - Stdio 传输层（重构）
- **Tools** - 完整的工具 handler 实现

---

## 新增文件

### 1. acp/protocol.py (4.7KB)
**ACP 协议消息实现**

```python
# 核心消息类
InitializeRequest/Response     # 初始化握手
NewSessionRequest/Response     # 创建会话
PromptRequest/Response         # 发送提示
SessionNotification            # 会话通知（进度/完成）
```

**功能**:
- ✅ JSON-RPC 2.0 格式
- ✅ 消息序列化/反序列化
- ✅ 类型安全的 dataclass
- ✅ 工厂方法创建消息

---

### 2. acp/session_manager.py (6.2KB)
**会话管理器**

```python
class SessionState:
    session_id: str
    status: SessionStatus  # pending/running/completed/failed/cancelled
    progress: float        # 0.0 - 1.0
    result: Any
    error: Optional[str]

class SessionManager:
    create_session() -> SessionState
    get_session(session_id) -> SessionState
    update_session(session_id, **kwargs) -> bool
    list_sessions() -> List[SessionState]
    wait_for_completion(session_id, timeout) -> SessionState
```

**功能**:
- ✅ 线程安全的会话管理
- ✅ 状态追踪（5 种状态）
- ✅ 进度更新
- ✅ 超时等待
- ✅ 自动清理旧会话
- ✅ 全局单例模式

---

### 3. acp/transport.py (7.5KB) - 重构
**Stdio 传输层（增强版）**

**新增功能**:
- ✅ 异步响应读取（后台线程）
- ✅ 请求 - 响应映射（基于 ID）
- ✅ 超时处理
- ✅ 错误日志线程
- ✅ 初始化握手 (`initialize()`)
- ✅ 单例模式 (`get_transport()`)

**改进**:
```python
# 旧版：同步阻塞
response = transport.send_request(request)

# 新版：异步等待
event = threading.Event()
self._pending[request_id] = event
response = self.send(message, timeout=30.0)
```

---

### 4. tools.py (6.7KB) - 重写
**完整的工具 handler 实现**

#### acp_dispatch
```python
def acp_dispatch(task: str, context: dict = None, model: str = None) -> str:
    """派发任务到 Gemini CLI"""
    # 1. 初始化传输层
    # 2. 创建会话
    # 3. 发送 NewSessionRequest
    # 4. 发送 PromptRequest
    # 5. 更新会话状态
    # 6. 返回 session_id
```

#### acp_progress
```python
def acp_progress(session_id: str) -> str:
    """查询任务进度"""
    # 1. 从会话管理器获取进度
    # 2. 返回状态、进度百分比、消息
```

#### acp_result
```python
def acp_result(session_id: str, wait: bool = True, timeout: float = None) -> str:
    """获取任务结果"""
    # 1. 可选等待完成
    # 2. 根据状态返回不同结果
    # 3. 支持 pending/running/completed/failed/cancelled
```

---

### 5. schemas.py (1.9KB) - 更新
**增强的 Schema 定义**

```python
ACP_DISPATCH_SCHEMA = {
    "task": {"type": "string"},
    "context": {
        "files": {"type": "array"},
        "constraints": {"type": "string"}
    },
    "model": {"enum": ["gemini-2.5-pro", "gemini-2.5-flash"]}
}
```

---

### 6. __init__.py (1.6KB) - 更新
**插件注册（带日志）**

```python
def register(ctx):
    ctx.register_tool(name="acp_dispatch", ...)
    ctx.register_tool(name="acp_progress", ...)
    ctx.register_tool(name="acp_result", ...)
```

---

## 验证结果

```
============================================================
Hermes ACP Client Plugin - Phase 2 验证
============================================================
✓ acp.transport 导入成功
✓ acp.protocol 导入成功
✓ acp.session_manager 导入成功
✓ tools 导入成功
✓ schemas 导入成功

============================================================
协议消息测试
============================================================
✓ InitializeRequest 创建成功：initialize
✓ NewSessionRequest 创建成功，ID: e8dbfe2c-...
✓ PromptRequest 创建成功：sessionId=test-123
✓ SessionNotification 创建成功：type=progress

============================================================
会话管理器测试
============================================================
✓ 会话创建成功：30a9f6aa
✓ 会话更新成功：status=running, progress=0.5
✓ 进度查询成功：running
✓ 会话列表成功：共 1 个会话
```

---

## 文件结构

```
~/.hermes/plugins/acp-client/
├── plugin.yaml              # 307B
├── __init__.py              # 1.6KB ✓ 更新
├── schemas.py               # 1.9KB ✓ 更新
├── tools.py                 # 6.7KB ✓ 重写
└── acp/
    ├── __init__.py          # 891B  ✓ 新增
    ├── protocol.py          # 4.7KB  ✓ 新增
    ├── session_manager.py   # 6.2KB  ✓ 新增
    └── transport.py         # 7.5KB  ✓ 重构
```

**总计**: 8 个文件，约 28KB 代码

---

## 技术亮点

### 1. 线程安全设计
```python
class SessionManager:
    def __init__(self):
        self._lock = threading.RLock()  # 可重入锁
    
    def create_session(self):
        with self._lock:  # 自动加锁/解锁
            ...
```

### 2. 异步响应处理
```python
def _read_responses(self):
    for line in iter(self.process.stdout.readline, ''):
        response = json.loads(line)
        request_id = response.get('id')
        if request_id in self._pending:
            self._responses[request_id] = response
            self._pending[request_id].set()  # 唤醒等待线程
```

### 3. 单例模式
```python
_manager: Optional[SessionManager] = None
_lock = threading.Lock()

def get_session_manager() -> SessionManager:
    with _lock:
        if _manager is None:
            _manager = SessionManager()
        return _manager
```

### 4. 状态机设计
```python
class SessionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

## 待完成事项

### 高优先级

1. **Gemini CLI ACP 模式测试**
   - 验证 `gemini --acp-server` 命令
   - 测试实际 JSON-RPC 通信
   - 处理协议差异

2. **错误处理增强**
   - 子进程崩溃恢复
   - 网络超时重试
   - 资源泄漏预防

3. **日志系统**
   - 结构化日志
   - 日志级别控制
   - 日志文件轮转

### 中优先级

4. **进度通知**
   - 实现 SessionNotification 监听
   - 后台进度更新线程
   - 回调机制

5. **会话持久化**
   - SQLite 存储
   - 重启恢复
   - 历史记录查询

---

## Phase 3 计划

### 目标：结果回推和自动注入

1. **实现进度监听线程**
   - 监听 SessionNotification
   - 自动更新 SessionState
   - 触发 Hermes 上下文注入

2. **实现 pre_llm_call 钩子**
   - 检查是否有进度更新
   - 注入到用户消息
   - 透明化执行过程

3. **完善错误处理**
   - 重试逻辑
   - 超时处理
   - 资源清理

---

## 安装说明

### 前置要求

1. Python >= 3.9
2. Gemini CLI 已安装
3. GOOGLE_API_KEY 环境变量

### 验证安装

```bash
cd ~/.hermes/plugins/acp-client
python3 -c "from acp.protocol import InitializeRequest; print('✓ OK')"
```

---

*报告生成：2026-04-13*  
*开发者：Hermes Agent (Autonomous Engineering)*
