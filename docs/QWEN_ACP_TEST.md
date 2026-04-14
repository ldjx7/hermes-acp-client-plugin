# Qwen CLI ACP 兼容性测试报告

## 测试日期
2026-04-14

## 测试摘要

✅ **Qwen CLI ACP 模式测试通过**

Qwen CLI (v0.14.3) 完全支持 ACP 协议，可以用作 Hermes ACP Client Plugin 的 worker。

---

## Qwen ACP 协议要求

Qwen 的 ACP 实现有一些特定的协议要求，与 Gemini 略有不同：

### 1. Initialize 请求

```json
{
  "jsonrpc": "2.0",
  "id": "uuid",
  "method": "initialize",
  "params": {
    "protocolVersion": 1,  // ⚠️ 必须是数字，不是字符串
    "capabilities": {},
    "clientInfo": {
      "name": "hermes-acp-client-plugin",
      "version": "0.2.0"
    }
  }
}
```

**关键点**: `protocolVersion` 必须是整数 `1`，而不是日期字符串。

### 2. session/new 请求

```json
{
  "jsonrpc": "2.0",
  "id": "uuid",
  "method": "session/new",
  "params": {
    "name": "test_session",
    "cwd": "/tmp",          // ⚠️ 必需字段
    "mcpServers": []        // ⚠️ 必需字段
  }
}
```

**关键点**: 必须提供 `cwd` (当前工作目录) 和 `mcpServers` (MCP 服务器列表)。

### 3. session/prompt 请求

```json
{
  "jsonrpc": "2.0",
  "id": "uuid",
  "method": "session/prompt",
  "params": {
    "sessionId": "xxx",
    "prompt": [             // ⚠️ 必须是数组
      {
        "type": "text",     // ⚠️ 必须有 type 字段
        "text": "Hello"     // ⚠️ 内容在 text 字段
      }
    ]
  }
}
```

**关键点**: `prompt` 是消息数组，每条消息需要 `type` 和 `text` 字段。

---

## 代码修改

### protocol.py 修改

```python
# InitializeRequest - protocolVersion 改为数字
@dataclass
class InitializeRequest(ACPMessage):
    params: Dict[str, Any] = field(default_factory=lambda: {
        "protocolVersion": 1,  # 数字，不是字符串
        "capabilities": {},
        "clientInfo": {"name": "...", "version": "..."}
    })

# NewSessionRequest - 添加必需参数
@classmethod
def create(cls, name: str = "default", cwd: str = None, mcp_servers: list = None):
    import os
    params = {
        "name": name,
        "cwd": cwd or os.getcwd(),      # 必需
        "mcpServers": mcp_servers or []  # 必需
    }

# PromptRequest - 消息格式
@classmethod
def create(cls, session_id: str, prompt: str, system_prompt: str = None):
    messages = [{
        "type": "text",    # 必需
        "text": prompt     # 必需
    }]
    params = {
        "sessionId": session_id,
        "prompt": messages
    }
    if system_prompt:
        params["systemPrompt"] = system_prompt
```

---

## 测试结果

```
======================================================================
Qwen CLI ACP 模式端到端测试
======================================================================

[步骤 1] 初始化 Transport...
✓ Transport 启动成功 (PID: 2862429)

[步骤 2] Initialize 握手...
✓ Initialize 成功
   Agent: qwen-code v0.14.3

[步骤 3] 创建会话...
✓ 会话创建成功：c288b280-332f-41a2-8d02-dd1c505af33a

[步骤 4] 发送提示...
   提示：用中文回复：你好，世界！
✓ 提示发送成功
   停止原因：end_turn

[步骤 5] 清理...
✓ Transport 已关闭

======================================================================
✅ Qwen CLI ACP 测试完成!
======================================================================
```

---

## 使用方法

### 1. 安装 Qwen CLI

```bash
npm install -g @qwen-code/qwen-code
```

### 2. 配置 API Key

```bash
export OPENAI_API_KEY="sk-..."  # Qwen 使用 OpenAI 兼容 API
```

### 3. 在 Hermes 中使用

```python
# 派发任务到 Qwen
acp_dispatch({
    "task": "写一个 Python 脚本",
    "worker": "qwen",           # 指定使用 Qwen
    "timeout": 180,
    "max_retries": 3
})

# 查询进度
acp_progress({"task_id": "abc123"})

# 获取结果
acp_result({"task_id": "abc123"})
```

---

## Worker 对比

| Worker | 命令 | 协议版本 | 特殊要求 | 状态 |
|--------|------|---------|---------|------|
| **Gemini** | `gemini --acp` | `"2025-06-18"` (字符串) | 无 | ✅ 支持 |
| **Qwen** | `qwen --acp` | `1` (数字) | cwd, mcpServers, prompt 数组 | ✅ 支持 |
| **Claude** | `claude --acp` | 待确认 | 待确认 | ⏳ 待测试 |
| **Codex** | `codex --acp` | 待确认 | 待确认 | ⏳ 待测试 |

---

## 协议适配器

为了兼容不同 Worker 的协议差异，我们实现了协议适配层：

```python
class ProtocolAdapter:
    """自动适配不同 Worker 的协议要求"""
    
    @staticmethod
    def get_initialize_params(worker: str) -> dict:
        if worker == "qwen":
            return {"protocolVersion": 1}
        else:
            return {"protocolVersion": "2025-06-18"}
    
    @staticmethod
    def format_prompt(worker: str, prompt: str) -> any:
        if worker == "qwen":
            return [{"type": "text", "text": prompt}]
        else:
            return prompt  # 字符串格式
```

---

## 结论

✅ **Qwen CLI 是完全兼容的 ACP worker**

- Initialize 握手成功
- 会话创建成功
- 提示发送成功
- 响应接收成功

**推荐配置**:
- 使用 `worker="qwen"` 参数
- 设置 `OPENAI_API_KEY` 环境变量
- 超时设置 30-60 秒
- 重试次数 2-3 次

---

*测试报告生成：2026-04-14*  
*Qwen CLI 版本：0.14.3*  
*插件版本：0.2.1*
