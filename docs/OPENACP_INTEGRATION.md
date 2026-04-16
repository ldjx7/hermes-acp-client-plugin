# Hermes ACP Plugin via OpenACP Bridge

基于 OpenACP 的 Hermes ACP 插件桥接层，支持 28+ AI 编码 Agent。

## 架构设计

```
Hermes Agent
    ↓ (ACP Protocol)
OpenACP Bridge
    ↓ (ACP Protocol)
AI Agents (28+ supported)
├── Gemini CLI
├── Claude Code (via claude-agent-acp)
├── Codex CLI
├── Qwen Code
├── Cursor
├── Copilot
└── ... and 23 more
```

## 优势

1. **统一接口** - 通过 OpenACP 标准化所有 Agent 的 ACP 协议差异
2. **自动协议适配** - OpenACP 处理不同 Agent 的协议变体
3. **28+ Agent 支持** - 无需为每个 Agent 单独实现协议适配
4. **Agent 热切换** - 运行时切换不同 Agent，无需重启
5. **内置 failover** - OpenACP 支持 Agent 故障转移

## 实现方案

### 方案 A: OpenACP 作为后端服务

```python
# openacp_bridge.py
import requests
import subprocess
import json

class OpenACPBridge:
    """通过 OpenACP REST API 调用 AI Agent"""
    
    def __init__(self, openacp_url: str = "http://localhost:3000"):
        self.base_url = openacp_url
    
    def dispatch(self, agent: str, prompt: str, session_id: str = None) -> dict:
        """
        派发任务到指定 Agent
        
        Args:
            agent: Agent 名称 (gemini, claude, codex, qwen, etc.)
            prompt: 任务提示
            session_id: 可选的会话 ID
            
        Returns:
            ACP 格式的响应
        """
        payload = {
            "agent": agent,
            "prompt": prompt,
            "sessionId": session_id
        }
        
        response = requests.post(
            f"{self.base_url}/api/sessions",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return response.json()
    
    def get_result(self, session_id: str) -> dict:
        """获取任务结果"""
        response = requests.get(
            f"{self.base_url}/api/sessions/{session_id}"
        )
        return response.json()
    
    def list_agents(self) -> list:
        """列出所有可用 Agent"""
        response = requests.get(f"{self.base_url}/api/agents")
        return response.json().get("agents", [])
```

### 方案 B: 直接调用 OpenACP CLI

```python
# openacp_cli_bridge.py
import subprocess
import json

class OpenACPCliBridge:
    """通过 OpenACP CLI 调用 AI Agent"""
    
    def __init__(self, workspace: str = None):
        self.workspace = workspace
    
    def dispatch(self, agent: str, prompt: str) -> str:
        """
        派发任务
        
        Args:
            agent: Agent 名称
            prompt: 任务提示
            
        Returns:
            Agent 响应文本
        """
        cmd = [
            "openacp",
            "agents",
            "run",
            agent,
            "--",
            "-p",  # print mode
            prompt
        ]
        
        if self.workspace:
            cmd.extend(["--cwd", self.workspace])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        return result.stdout
    
    def list_agents(self) -> list:
        """列出所有已安装 Agent"""
        result = subprocess.run(
            ["openacp", "agents", "--json"],
            capture_output=True,
            text=True
        )
        data = json.loads(result.stdout)
        return data.get("agents", [])
```

## 集成到 Hermes ACP 插件

### 1. 修改 transport.py

```python
# ~/.hermes/plugins/acp-client/acp/transport.py

class OpenACPTransport:
    """使用 OpenACP 作为后端"""
    
    def __init__(self, agent: str = "gemini", openacp_url: str = None):
        self.agent = agent
        self.openacp_url = openacp_url
        self.bridge = OpenACPBridge(openacp_url) if openacp_url else OpenACPCliBridge()
    
    def send_prompt(self, prompt: str, session_id: str = None) -> str:
        """发送提示并获取响应"""
        return self.bridge.dispatch(self.agent, prompt, session_id)
```

### 2. 添加新 Worker 配置

```python
WORKER_CONFIGS = {
    # 直接调用 (原有方式)
    "gemini": WorkerConfig("gemini", ["gemini", "--acp"]),
    "qwen": WorkerConfig("qwen", ["qwen", "--acp"]),
    
    # 通过 OpenACP (新方式)
    "openacp:gemini": WorkerConfig("openacp:gemini", ["openacp", "agents", "run", "gemini", "--"]),
    "openacp:claude": WorkerConfig("openacp:claude", ["openacp", "agents", "run", "claude", "--"]),
    "openacp:codex": WorkerConfig("openacp:codex", ["openacp", "agents", "run", "codex", "--"]),
    "openacp:cursor": WorkerConfig("openacp:cursor", ["openacp", "agents", "run", "cursor", "--"]),
    "openacp:copilot": WorkerConfig("openacp:copilot", ["openacp", "agents", "run", "copilot", "--"]),
}
```

### 3. 创建 OpenACP 桥接插件

```python
# ~/.hermes/plugins/openacp-bridge/tools.py

from openacp_bridge import OpenACPBridge

bridge = OpenACPBridge()

def openacp_dispatch(agent: str, prompt: str) -> dict:
    """Dispatch task to AI agent via OpenACP"""
    result = bridge.dispatch(agent, prompt)
    return {"status": "success", "result": result}

def openacp_list_agents() -> dict:
    """List all available agents"""
    agents = bridge.list_agents()
    return {"status": "success", "agents": agents}

def openacp_get_result(session_id: str) -> dict:
    """Get task result"""
    result = bridge.get_result(session_id)
    return {"status": "success", "result": result}

TOOLS = {
    "openacp_dispatch": openacp_dispatch,
    "openacp_list_agents": openacp_list_agents,
    "openacp_get_result": openacp_get_result,
}
```

## 安装步骤

### 1. 安装 OpenACP

```bash
npm install -g @openacp/cli
```

### 2. 配置 OpenACP

```bash
# 首次运行会启动配置向导
openacp

# 或手动配置
mkdir -p ~/.openacp
cat > ~/.openacp/config.json << 'EOF'
{
  "agents": {
    "gemini": {"command": "gemini", "args": []},
    "claude": {"command": "claude-agent-acp", "args": []},
    "codex": {"command": "codex", "args": ["--acp"]},
    "qwen": {"command": "qwen", "args": ["--acp"]}
  },
  "workspace": "~/projects"
}
EOF
```

### 3. 安装需要的 Agent

```bash
openacp agents install gemini
openacp agents install claude
openacp agents install codex
openacp agents install qwen
```

### 4. 启动 OpenACP 服务

```bash
# 后台运行
openacp start --daemon

# 或前台运行
openacp --foreground
```

### 5. 在 Hermes 中使用

```python
# 使用 OpenACP 桥接
acp_dispatch({
    "task": "写一个 Python 函数",
    "worker": "openacp:gemini",  # 或 openacp:claude, openacp:codex 等
    "timeout": 300
})
```

## 支持的 Agent 列表

OpenACP 支持 28+ AI 编码 Agent：

| Agent | 命令 | 状态 |
|-------|------|------|
| Gemini CLI | `gemini` | ✅ |
| Claude Code | `claude-agent-acp` | ✅ |
| Codex CLI | `codex` | ✅ |
| Qwen Code | `qwen` | ✅ |
| Cursor | `cursor` | ✅ |
| GitHub Copilot | `copilot` | ✅ |
| Goose | `goose` | ✅ |
| OpenCode | `opencode` | ✅ |
| OpenHands | `openhands` | ✅ |
| ... | ... | +18 more |

## 性能对比

| 方式 | 延迟 | 兼容性 | 推荐度 |
|------|------|--------|--------|
| 直接 ACP | 低 | 需要单独适配 | ⭐⭐⭐ |
| OpenACP CLI | 中 | 自动适配 | ⭐⭐⭐⭐ |
| OpenACP API | 中 | 自动适配 | ⭐⭐⭐⭐⭐ |

## 总结

使用 OpenACP 作为后端的优势：

1. ✅ **一次集成，支持 28+ Agent**
2. ✅ **自动处理协议差异**
3. ✅ **内置 Agent 管理和安装**
4. ✅ **支持热切换 Agent**
5. ✅ **内置 failover 和重试**

推荐将 OpenACP 作为 Hermes ACP 插件的主要后端。
