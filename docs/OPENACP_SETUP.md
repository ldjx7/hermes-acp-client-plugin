# Hermes ACP + OpenACP 集成指南

## 概述

OpenACP 是一个统一的 AI Agent 桥接器，支持 28+ AI 编码 Agent。通过 OpenACP，Hermes ACP 插件可以：

- ✅ 统一接口访问所有 Agent
- ✅ 自动处理协议差异
- ✅ 运行时切换不同 Agent
- ✅ 内置 failover 支持

## 架构图

```
Hermes Agent
    ↓ (ACP Protocol)
Hermes ACP Plugin
    ↓ (OpenACP Bridge)
OpenACP
    ↓ (ACP Protocol)
AI Agents (28+)
├── Gemini CLI
├── Claude Code (via adapter)
├── Codex CLI
├── Qwen Code
├── Cursor
├── GitHub Copilot
└── ... (23 more)
```

## 安装步骤

### 1. 安装 OpenACP

```bash
npm install -g @openacp/cli
```

### 2. 初始化 OpenACP 配置

```bash
# 创建工作目录
mkdir -p ~/openacp-workspace
cd ~/openacp-workspace

# 运行配置向导
openacp
```

配置向导会询问：
- 选择消息平台（选 None 仅使用 API）
- 选择默认 Agent
- 配置工作目录

### 3. 安装需要的 Agent

```bash
# 查看可用 Agent
openacp agents

# 安装常用 Agent
openacp agents install gemini
openacp agents install claude
openacp agents install codex
openacp agents install qwen
openacp agents install cursor

# 查看已安装 Agent
openacp agents --json
```

### 4. 启动 OpenACP 服务

```bash
# 后台运行（推荐）
openacp start --daemon

# 查看状态
openacp status

# 查看日志
openacp logs

# 停止服务
openacp stop
```

### 5. 在 Hermes 中使用

```python
# 使用 OpenACP worker
acp_dispatch({
    "task": "写一个 Python 函数",
    "worker": "openacp:gemini",  # 或 openacp:claude, openacp:codex 等
    "timeout": 300
})

# 列出可用 Agent
from acp.transport import list_openacp_agents
agents = list_openacp_agents()
print(f"Available agents: {agents}")
```

## Worker 配置

### 直接使用 ACP（原生协议）

```python
# 推荐：Gemini（100% 成功率）
worker="gemini"

# 推荐：Qwen（需要协议适配）
worker="qwen"
```

### 通过 OpenACP（统一接口）

```python
# Gemini via OpenACP
worker="openacp:gemini"

# Claude via OpenACP
worker="openacp:claude"

# Codex via OpenACP
worker="openacp:codex"

# Qwen via OpenACP
worker="openacp:qwen"

# Cursor via OpenACP
worker="openacp:cursor"

# GitHub Copilot via OpenACP
worker="openacp:copilot"
```

## 支持的 Agent 列表

OpenACP 支持 28+ AI 编码 Agent：

| Agent | Worker 名称 | 状态 |
|-------|-----------|------|
| Gemini CLI | `openacp:gemini` | ✅ |
| Claude Code | `openacp:claude` | ✅ |
| Codex CLI | `openacp:codex` | ✅ |
| Qwen Code | `openacp:qwen` | ✅ |
| Cursor | `openacp:cursor` | ✅ |
| GitHub Copilot | `openacp:copilot` | ✅ |
| Goose | `openacp:goose` | ✅ |
| OpenCode | `openacp:opencode` | ✅ |
| OpenHands | `openacp:openhands` | ✅ |
| Cline | `openacp:cline` | ✅ |
| Blackbox AI | `openacp:blackbox` | ✅ |
| AutoDev | `openacp:auto-dev` | ✅ |
| Crow CLI | `openacp:crow-cli` | ✅ |
| cagent | `openacp:cagent` | ✅ |
| fast-agent | `openacp:fast-agent` | ✅ |
| Factory Droid | `openacp:factory-droid` | ✅ |
| Fount | `openacp:fount` | ✅ |
| Junie (JetBrains) | `openacp:junie` | ✅ |
| Kimi CLI | `openacp:kimi-cli` | ✅ |
| Kiro CLI | `openacp:kiro-cli` | ✅ |
| Minion Code | `openacp:minion-code` | ✅ |
| Mistral Vibe | `openacp:mistral-vibe` | ✅ |
| OpenClaw | `openacp:openclaw` | ✅ |
| Pi | `openacp:pi` | ✅ |
| Qoder CLI | `openacp:qoder-cli` | ✅ |
| Stakpak | `openacp:stakpak` | ✅ |
| stdio Bus | `openacp:stdio-bus` | ✅ |
| VT Code | `openacp:vt-code` | ✅ |

## API 使用方式

### CLI 模式（默认）

```python
from acp.openacp_bridge import OpenACPCliBridge

bridge = OpenACPCliBridge(workspace="/path/to/workspace")

# 列出 Agent
agents = bridge.list_agents()

# 派发任务
result = bridge.dispatch("gemini", "写一个快速排序")
print(result["output"])
```

### API 模式（需要 OpenACP daemon）

```python
from acp.openacp_bridge import OpenACPAPIBridge

bridge = OpenACPAPIBridge(base_url="http://localhost:3000")

# 派发任务
result = bridge.dispatch("gemini", "写一个快速排序")
session_id = result["session_id"]

# 获取结果
result = bridge.get_result(session_id)
print(result["output"])
```

## 故障排除

### OpenACP 未配置

```
Error: No OpenACP instances found. Run `openacp` in your workspace directory to set up.
```

**解决**：运行 `openacp` 完成配置向导。

### Agent 未安装

```
Error: Agent 'gemini' is not installed. Run `openacp agents install gemini`
```

**解决**：安装对应的 Agent。

### OpenACP 服务未运行

```bash
# 检查状态
openacp status

# 启动服务
openacp start --daemon
```

### 查看日志

```bash
openacp logs
```

### 重新配置

```bash
openacp reset
```

## 性能对比

| 方式 | 延迟 | 兼容性 | 推荐场景 |
|------|------|--------|----------|
| 直接 ACP | 低 (~500ms) | 需要单独适配 | 生产环境（Gemini/Qwen） |
| OpenACP CLI | 中 (~1-2s) | 自动适配 | 测试/开发 |
| OpenACP API | 中 (~800ms) | 自动适配 | 生产环境（多 Agent） |

## 最佳实践

### 1. 生产环境

推荐直接使用原生 ACP：
```python
worker="gemini"  # 稳定，100% 成功率
```

### 2. 多 Agent 测试

使用 OpenACP 快速切换：
```python
for agent in ["gemini", "claude", "codex", "qwen"]:
    result = acp_dispatch({
        "task": "写一个函数",
        "worker": f"openacp:{agent}"
    })
```

### 3. Failover 配置

```python
# 配置自动 failover
acp_dispatch({
    "task": "写代码",
    "worker": "gemini",
    "fallback_workers": ["openacp:claude", "openacp:codex", "qwen"]
})
```

## 下一步

1. ✅ 安装 OpenACP
2. ✅ 配置工作目录
3. ✅ 安装需要的 Agent
4. ✅ 启动 OpenACP 服务
5. ✅ 在 Hermes 中使用 `openacp:*` worker

## 相关文档

- [OpenACP 官方文档](https://github.com/Open-ACP/OpenACP)
- [ACP 协议规范](https://agentclientprotocol.com)
- [Hermes ACP 插件](./README.md)
