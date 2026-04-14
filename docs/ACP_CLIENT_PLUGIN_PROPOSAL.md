# Hermes ACP Client Plugin - 调研与技术方案

## 文档信息

| 项目 | 内容 |
|------|------|
| **项目名称** | hermes-acp-client-plugin |
| **版本** | 0.1.0 |
| **创建日期** | 2026-04-13 |
| **作者** | Hermes Agent Team |
| **状态** | 技术方案/待开发 |

---

## 1. 执行摘要

### 1.1 项目目标

开发一个 Hermes Agent 插件，实现 **ACP (Agent Client Protocol) 客户端** 功能，使 Hermes 能够：

1. **派发子会话** - 将任务派发到独立的 ACP 工作会话（Codex、Claude 等）
2. **监听进度** - 实时接收子会话的执行进度和状态更新
3. **结果回推** - 将子会话结果自动写回父会话

### 1.2 核心价值

| 当前限制 | 插件解决后 |
|----------|------------|
| 单会话执行，长任务阻塞主对话 | 多会话并行，主会话可继续其他工作 |
| 无法追踪子任务进度 | 实时进度更新，透明化执行过程 |
| 手动整合多个 agent 输出 | 自动结果回推，统一工作流 |

---

## 2. 背景调研

### 2.1 ACP 协议概述

**ACP (Agent Client Protocol)** 是一个标准化的 AI Agent 通信协议，定义了：

- Agent 与 Client 之间的 JSON-RPC 消息格式
- 会话管理（创建、恢复、终止）
- 工具调用和进度通知
- 认证和权限管理

**协议版本**: `PROTOCOL_VERSION` (当前 Hermes 使用 `use_unstable_protocol=True`)

### 2.2 Hermes 现有 ACP 实现

Hermes 当前实现了 **ACP Server** 模式：

```
┌─────────────┐         ┌─────────────┐
│   Editor    │  ACP    │   Hermes    │
│  (VS Code)  │ ──────> │  (ACP Server)│
│   Client    │  JSON   │  acp.Agent  │
│             │  -RPC   │             │
└─────────────┘         └─────────────┘
```

**关键文件**:
- `acp_adapter/entry.py` - ACP 入口点
- `acp_adapter/server.py` - `HermesACPAgent` 实现
- `acp_adapter/session.py` - 会话管理器
- `acp_adapter/events.py` - 事件回调处理

### 2.3 acp 包分析

```python
# acp 包位置
/root/.hermes/hermes-agent/venv/lib/python3.11/site-packages/acp/__init__.py

# 核心类
acp.Agent          # Agent 基类
acp.Client         # Client 连接
acp.run_agent()    # 运行 Agent 的入口

# 核心消息类型
acp.InitializeRequest/Response
acp.NewSessionRequest/Response
acp.PromptRequest/Response
acp.SessionNotification
```

### 2.4 与 OpenClaw 的对比

| 特性 | OpenClaw ACP | Hermes ACP (当前) | 本插件目标 |
|------|-------------|------------------|------------|
| **角色** | Client | Server | Client |
| **子会话派发** | ✓ | ✗ | ✓ |
| **进度监听** | ✓ (bridge) | ✗ | ✓ |
| **结果回推** | ✓ (bridge) | ✗ | ✓ |
| **多 worker 支持** | Codex | IDE | Gemini CLI (stdio) |

### 2.5 Gemini CLI 作为首选 Worker

**为什么选择 Gemini CLI**:
- **1M+ tokens 上下文** - 可处理大型代码库
- **原生代码能力** - 文件读写、搜索、Shell 执行
- **ACP 兼容** - 支持 `--acp-server` 模式作为 stdio worker
- **无需额外认证** - 复用现有 Google 凭据

**Gemini CLI 启动模式**:
```bash
gemini --acp-server  # 作为 ACP worker 运行
gemini -p "task" -y  # 非交互模式（备选方案）
```

---

## 3. 技术方案

### 3.1 插件架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Hermes Agent                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              acp-client 插件                         │    │
│  │  ┌───────────┐  ┌───────────┐  ┌───────────────┐   │    │
│  │  │  工具层   │  │  事件层   │  │  连接管理层   │   │    │
│  │  │  Tools    │  │  Events   │  │  Connection   │   │    │
│  │  └───────────┘  └───────────┘  └───────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
         │
         │ ACP JSON-RPC (stdio)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   ACP Workers                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Gemini CLI (首选)                       │    │
│  │  - 1M+ tokens 上下文                                 │    │
│  │  - 原生代码工具链                                     │    │
│  │  - stdio 模式                                        │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌───────────┐  ┌───────────┐                               │
│  │  Codex    │  │  Claude   │  (备选)                       │
│  └───────────┘  └───────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 插件目录结构

```
~/.hermes/plugins/acp-client/
├── plugin.yaml              # 插件清单
├── __init__.py              # 注册入口
├── schemas.py               # 工具 Schema 定义
├── tools.py                 # 工具实现
├── hooks.py                 # 生命周期钩子
├── acp/
│   ├── __init__.py
│   ├── client.py            # ACP 客户端连接
│   ├── session.py           # 子会话管理
│   └── events.py            # 事件监听
└── skill.md                 # 捆绑技能文档
```

### 3.3 核心工具设计

#### 3.3.1 `acp_dispatch` - 派发任务

**Schema**:
```python
{
    "name": "acp_dispatch",
    "description": (
        "Dispatch a task to an ACP worker agent (Codex, Claude, etc.). "
        "Use this when you need to delegate a self-contained coding or research task "
        "to a separate agent session. The task runs asynchronously and you can track "
        "progress with acp_progress."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The task description to dispatch"
            },
            "worker": {
                "type": "string",
                "description": "Target worker type (codex, claude, opencode, custom)",
                "enum": ["codex", "claude", "opencode", "custom"]
            },
            "timeout": {
                "type": "integer",
                "description": "Max execution time in seconds (default: 600)"
            },
            "priority": {
                "type": "string",
                "description": "Task priority",
                "enum": ["low", "normal", "high"]
            }
        },
        "required": ["task", "worker"]
    }
}
```

**Handler**:
```python
def acp_dispatch(args: dict, **kwargs) -> str:
    """Dispatch a task to an ACP worker."""
    from acp.client import ACPClient
    
    task = args.get("task")
    worker = args.get("worker", "codex")
    timeout = args.get("timeout", 600)
    
    client = ACPClient.get_instance()
    session_id = client.create_session(worker=worker)
    client.send_prompt(session_id, task)
    
    return json.dumps({
        "session_id": session_id,
        "status": "dispatched",
        "worker": worker,
        "estimated_time": timeout
    })
```

#### 3.3.2 `acp_progress` - 查询进度

**Schema**:
```python
{
    "name": "acp_progress",
    "description": (
        "Query the progress of a dispatched ACP task. Returns current status, "
        "progress percentage, and any intermediate results or logs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session ID from acp_dispatch"
            }
        },
        "required": ["session_id"]
    }
}
```

#### 3.3.3 `acp_result` - 获取结果

**Schema**:
```python
{
    "name": "acp_result",
    "description": (
        "Get the final result of a completed ACP task. Blocks until completion "
        "if the task is still running."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "The session ID from acp_dispatch"
            },
            "wait": {
                "type": "boolean",
                "description": "Whether to wait for completion (default: true)"
            }
        },
        "required": ["session_id"]
    }
}
```

### 3.4 事件钩子设计

#### 3.4.1 `post_llm_call` - 自动派发

```python
def on_post_llm_call(session_id, assistant_response, **kwargs):
    """
    检测 assistant 回复中的派发意图，自动创建 ACP 子会话。
    
    触发条件：
    - 回复包含 "dispatch to codex" 或类似关键词
    - 回复包含 ACP 派发标记
    """
    if should_dispatch(assistant_response):
        task = extract_task(assistant_response)
        # 自动派发逻辑
```

#### 3.4.2 `pre_tool_call` - 进度注入

```python
def on_pre_tool_call(tool_name, args, task_id, **kwargs):
    """
    在每次工具调用前，检查是否有 ACP 进度更新需要注入。
    """
    updates = ACPClient.get_pending_updates(task_id)
    if updates:
        # 将进度注入到上下文
        return {"context": format_progress(updates)}
```

### 3.5 ACP 客户端实现

```python
# acp/client.py
import asyncio
import json
import logging
from typing import Dict, Optional, Callable
import acp

logger = logging.getLogger(__name__)

class ACPClient:
    """ACP Client for managing sub-sessions."""
    
    _instance: Optional['ACPClient'] = None
    
    @classmethod
    def get_instance(cls) -> 'ACPClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._conn: Optional[acp.Client] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        
    def connect(self, worker: str = "codex") -> None:
        """Connect to an ACP worker."""
        # 根据 worker 类型建立连接
        # codex: stdio
        # claude: stdio 或 SSE
        pass
    
    def create_session(self, worker: str) -> str:
        """Create a new ACP sub-session."""
        session_id = str(uuid.uuid4())
        # 发送 NewSessionRequest
        # 记录会话状态
        return session_id
    
    def send_prompt(self, session_id: str, prompt: str) -> None:
        """Send a prompt to an ACP session."""
        # 发送 PromptRequest
        pass
    
    def subscribe_progress(self, session_id: str, callback: Callable) -> None:
        """Subscribe to progress updates from a session."""
        # 注册进度回调
        pass
```

---

## 4. 实现路线图

### 4.1 阶段划分

| 阶段 | 目标 | 预计工时 |
|------|------|----------|
| **Phase 1** | 基础框架 + `acp_dispatch` 工具 | 2-3 天 |
| **Phase 2** | 进度监听 + `acp_progress` 工具 | 2-3 天 |
| **Phase 3** | 结果回推 + 自动注入 | 2-3 天 |
| **Phase 4** | 多 worker 支持 + 错误处理 | 2-3 天 |
| **Phase 5** | 测试 + 文档 + 技能捆绑 | 1-2 天 |

**总预计**: 9-14 天

### 4.2 Phase 1 详细任务（修正版：Gemini CLI 优先）

```
Week 1:
├── Day 1: 插件骨架创建
│   ├── plugin.yaml (requires_env: GOOGLE_API_KEY)
│   ├── __init__.py
│   └── 基础目录结构
├── Day 2: StdioTransport 实现
│   ├── acp/transport.py
│   ├── Gemini CLI 进程管理
│   └── stdio 读写/错误捕获
├── Day 3: acp_dispatch 工具
│   ├── schemas.py (Schema 定义)
│   ├── tools.py (Handler 实现)
│   └── initialize/new_session/prompt 流程
└── Day 4: 冒烟测试
    ├── 测试脚本
    ├── 验证 Gemini CLI 进程拉起
    └── 验证 ACP 响应流
```

### 4.3 关键里程碑

1. **M1**: 能够成功派发任务到 Codex ACP
2. **M2**: 能够接收进度通知
3. **M3**: 完整工作流：派发→进度→结果→回推
4. **M4**: 插件发布到 Hermes Skills Hub

---

## 5. 技术挑战与解决方案

### 5.1 挑战 1: ACP 协议稳定性

**问题**: Hermes 使用 `use_unstable_protocol=True`，协议可能变化

**解决方案**:
- 使用 Hermes 内置的 `acp` 包，保持版本同步
- 在 `plugin.yaml` 中声明 Hermes 版本依赖
- 实现协议版本检测

### 5.2 挑战 2: 异步事件处理

**问题**: ACP 事件流是异步的，需要在同步工具中处理

**解决方案**:
- 使用 `asyncio` 事件循环
- 实现事件队列 + 轮询机制
- 工具返回后立即开始后台监听

### 5.3 挑战 3: 多 worker 认证

**问题**: 不同 worker (Codex, Claude) 需要不同认证

**解决方案**:
- 使用 Hermes 的 `requires_env` 门控
- 每个 worker 独立的认证配置
- 认证状态缓存

---

## 6. 测试策略

### 6.1 单元测试

```python
# tests/test_acp_client.py
def test_acp_dispatch():
    """测试任务派发功能"""
    result = acp_dispatch({"task": "test", "worker": "codex"})
    data = json.loads(result)
    assert data["status"] == "dispatched"
    assert "session_id" in data

def test_acp_progress():
    """测试进度查询功能"""
    # Mock ACP 会话
    pass
```

### 6.2 集成测试

```python
# tests/test_integration.py
def test_full_workflow():
    """测试完整工作流：派发→进度→结果"""
    # 实际连接 ACP worker
    # 验证端到端流程
    pass
```

### 6.3 手动测试场景

1. 派发一个简单的代码生成任务
2. 查询进度（多次）
3. 获取最终结果
4. 验证结果写回父会话

---

## 7. 配置示例

### 7.1 plugin.yaml

```yaml
name: acp-client
version: 0.1.0
description: ACP client for dispatching tasks to Gemini CLI worker
author: Hermes Agent Team
provides_tools:
  - acp_dispatch
  - acp_progress
  - acp_result
provides_hooks:
  - post_llm_call
  - pre_tool_call
requires_env:
  - name: GOOGLE_API_KEY
    description: "Google API key for Gemini CLI"
    url: "https://aistudio.google.com/app/apikey"
    secret: true
  - name: GEMINI_CLI_PATH
    description: "Path to gemini CLI binary (default: 'gemini')"
    default: "gemini"
```

### 7.2 用户使用示例

```python
# 在 Hermes 会话中
User: "帮我写一个 FastAPI 用户认证模块"

Assistant: "我将把这个任务派发给 Gemini CLI 来完成。"
       [调用 acp_dispatch]
       → {"session_id": "abc123", "status": "dispatched", "worker": "gemini"}

Assistant: "任务已派发 (session: abc123)，Gemini 正在执行中..."

# 5 分钟后
Assistant: [自动调用 acp_progress]
           → {"progress": 0.8, "update": "正在编写测试用例"}

Assistant: "当前进度 80%：正在编写测试用例"

# 完成后
Assistant: [自动调用 acp_result]
           → {"status": "completed", "result": "..."}

Assistant: "任务完成！以下是生成的代码：..."
```

---

## 8. 参考资源

### 8.1 Hermes 内部参考

- `~/.hermes/hermes-agent/acp_adapter/` - ACP 适配器源码
- `~/.hermes/hermes-agent/tools/registry.py` - 工具注册机制
- `~/.hermes/hermes-agent/hermes_cli/plugins.py` - 插件系统

### 8.2 外部参考

- [Agent Client Protocol Spec](https://github.com/agent-client-protocol)
- [Hermes Plugin Guide](https://hermes-agent.nousresearch.com/docs/developer-guide/build-a-hermes-plugin)
- [OpenClaw ACP Implementation](https://github.com/GalaxyXieyu/openclaw-coding-kit)

### 8.3 相关技能

- `hermes-agent` - Hermes 使用指南
- `claude-code` - Claude Code 集成
- `codex` - OpenAI Codex 集成

---

## 9. 下一步行动

1. **确认需求** - 与用户确认功能优先级
2. **环境准备** - 确保 ACP worker 可用
3. **开始 Phase 1** - 创建插件骨架
4. **周报复** - 每周五同步进度

---

*文档版本: 0.1.0 | 最后更新：2026-04-13*
