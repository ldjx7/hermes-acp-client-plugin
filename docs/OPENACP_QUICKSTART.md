# OpenACP 快速开始

## 🚀 开箱即用

OpenACP 已集成到 Hermes ACP 插件中，**无需任何配置**即可使用！

Hermes 会自动启动 OpenACP 后台服务，您只需要指定 worker 名称。

## 使用方式

### 基础用法

```python
# 使用 Gemini via OpenACP
acp_dispatch({
    "task": "写一个 Python 快速排序函数",
    "worker": "openacp:gemini",
    "timeout": 300
})
```

### 可用的 Agent

```python
# Gemini
worker="openacp:gemini"

# Claude
worker="openacp:claude"

# Codex
worker="openacp:codex"

# Qwen
worker="openacp:qwen"

# Cursor
worker="openacp:cursor"

# GitHub Copilot
worker="openacp:copilot"
```

### 完整示例

```python
from hermes.tools import acp_dispatch, acp_result

# 派发任务
result = acp_dispatch({
    "task": "创建一个 Flask Hello World 应用",
    "worker": "openacp:gemini",
    "timeout": 300
})

# 获取任务 ID
task_id = result["task_id"]

# 稍后获取结果
output = acp_result({"task_id": task_id})
print(output)
```

## 工作原理

```
Hermes 启动
    ↓
检测到 openacp:* worker
    ↓
自动检查 OpenACP daemon
    ↓
未运行 → 自动启动 (openacp start --daemon)
已运行 → 直接连接
    ↓
使用 API 模式通信
```

## 性能

| 指标 | 数值 |
|------|------|
| 首次启动延迟 | ~2-5 秒（自动启动 daemon） |
| 后续请求延迟 | ~500-800ms |
| 并发支持 | ✅ 支持 |

## 故障排除

### 问题：首次请求超时

**原因**: OpenACP daemon 正在首次启动

**解决**: 等待 5-10 秒后重试，后续请求会很快

### 问题：找不到 openacp 命令

**原因**: OpenACP 未安装

**解决**:
```bash
npm install -g @openacp/cli
```

### 问题：Agent 不可用

**原因**: 该 Agent 未安装

**解决**:
```bash
openacp agents install gemini
```

## 高级配置

如需配置外部 OpenACP 实例，设置环境变量：

```bash
export OPENACP_DAEMON_URL=http://localhost:8080
```

详见 [高级配置](./OPENACP_ADVANCED.md)

## 支持的 Agent

OpenACP 支持 28+ AI 编码 Agent，详见 [支持的 Agent 列表](./OPENACP_AGENTS.md)

## 下一步

- 📚 [查看支持的 Agent 列表](./OPENACP_AGENTS.md)
- ⚙️ [高级配置指南](./OPENACP_ADVANCED.md)
- 🔧 [故障排除](./OPENACP_TROUBLESHOOTING.md)
