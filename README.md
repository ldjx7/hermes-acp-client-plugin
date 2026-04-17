# Hermes ACP Client Plugin

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Plugin](https://img.shields.io/badge/Hermes-Plugin-orange.svg)](https://github.com/nousresearch/hermes-agent)

> 让 Hermes Agent 将复杂任务派发到独立 ACP worker，并把状态和结果带回主会话。

---

## 简介

Hermes ACP Client Plugin 是一个运行在 Hermes 内部的 **ACP (Agent Client Protocol) Client 插件**。它的职责不是自己完成所有任务，而是：

- 把任务派发到外部 ACP 兼容 worker
- 跟踪子会话执行状态
- 将结果、错误和进度回传给 Hermes
- 在 Hermes 下一次 LLM 调用前自动注入活跃任务摘要

当前代码已经完成一轮内部重构，核心结构为：

- `tools.py`：Hermes 工具薄入口
- `services/`：派发、进度、结果服务
- `repositories/`：会话状态仓库抽象
- `workers/`：worker adapter 与能力注册表
- `acp/`：协议、transport、session manager、hook

详细实现说明见 [docs/ACP_CLIENT_PLUGIN_PROPOSAL.md](docs/ACP_CLIENT_PLUGIN_PROPOSAL.md)。

---

## 快速开始

### 安装

```bash
# 方式 1: 从 GitHub 安装（推荐）
hermes plugins install https://github.com/YOUR_USERNAME/hermes-acp-client-plugin.git

# 方式 2: 本地开发安装
cd /path/to/hermes-acp-client-plugin
ln -s $(pwd) ~/.hermes/plugins/acp-client
```

### 使用示例

```python
# 在 Hermes 会话中调用：

# 1. 派发任务到 Gemini
/acp_dispatch --task "写一个 FastAPI 用户认证模块" --worker gemini

# 2. 查询进度
/acp_progress --task-id abc123

# 3. 获取结果
/acp_result --task-id abc123

# 4. 取消任务
/acp_cancel --task-id abc123
```

`task_id` 传入的就是 `acp_dispatch` 返回的 `sessionId`。

---

## 当前运行逻辑

```text
Hermes
└─ acp_dispatch
   └─ DispatchService
      ├─ initialize transport
      ├─ create ACP session
      ├─ send prompt to worker
      └─ write session state

worker notifications
└─ DispatchService.handle_notification
   └─ repository.update_session

Hermes follow-up calls
├─ acp_progress -> ProgressService
├─ acp_result   -> ResultService
└─ acp_cancel   -> ResultService

before next LLM call
└─ pre_llm_call_hook
   └─ inject active ACP progress summary
```

---

## 项目结构

```text
hermes-acp-client-plugin/
├── plugin.yaml
├── __init__.py
├── schemas.py
├── tools.py
├── README.md
├── requirements.txt
├── src/
│   └── main.py
├── acp/
│   ├── protocol.py
│   ├── transport.py
│   ├── session_manager.py
│   └── hooks.py
├── services/
│   ├── dispatch_service.py
│   ├── progress_service.py
│   └── result_service.py
├── repositories/
│   ├── session_repository.py
│   └── memory_session_repository.py
├── workers/
│   ├── base.py
│   └── registry.py
└── docs/
    ├── ACP_CLIENT_PLUGIN_PROPOSAL.md
    ├── ACP_ERROR_HANDLING.md
    └── WORKER_COMPARISON.md
```

---

## 核心工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `acp_dispatch` | 派发任务到 ACP worker | `task`, `worker`, `timeout`, `max_retries` |
| `acp_progress` | 查询任务进度 | `task_id` |
| `acp_result` | 获取最终结果 | `task_id`, `wait`, `timeout` |
| `acp_cancel` | 取消任务并尽量向 worker 传播取消 | `task_id` |
| `acp_list` | 列出会话 | `active_only` |
| `acp_cleanup` | 清理过期会话 | `max_age_hours` |
| `acp_shutdown` | 关闭一个或全部 worker transport | `worker` |

---

## 配置

### plugin.yaml

```yaml
name: acp-client
version: 0.2.1
description: ACP client for dispatching tasks to AI workers (Gemini/Claude/Codex/Qwen)
provides_tools:
  - acp_dispatch
  - acp_progress
  - acp_result
  - acp_cancel
  - acp_list
  - acp_cleanup
  - acp_shutdown
hooks:
  pre_llm_call: acp.hooks.pre_llm_call_hook
```

### Worker 配置

当前 worker 命令和能力通过 `workers/registry.py` 管理，`acp/transport.py` 从注册表读取命令：

```python
_WORKER_ADAPTERS = {
    "gemini": WorkerAdapter(name="gemini", command=["gemini", "--acp"]),
    "qwen": WorkerAdapter(name="qwen", command=["qwen", "--acp"]),
    "claude": WorkerAdapter(name="claude", command=["claude", "--acp"]),
    "codex": WorkerAdapter(name="codex", command=["codex", "--acp"]),
}
```

---

## 当前边界

当前实现已经能表达完整主链路，但仍有这些工程边界：

- session 状态仍然是内存态，进程重启后不会恢复
- cancel 仍是 best-effort，不保证远程 worker 一定终止
- 同步 result 和异步 notification 仍是两条并存路径
- 当前仓库不保留 committed `tests/` 目录

---

## 推荐下一步

- 增加持久化 repository，例如 SQLite
- 统一“直接返回结果”和“通知完成”两条状态归并路径
- 扩展 worker adapter 能力模型
- 重新建立正式自动化测试策略

---

## 开发路线图

| 阶段 | 状态 | 完成日期 |
|------|------|----------|
| Phase 1: 基础框架 | ✅ 已完成 | 2026-04-13 |
| Phase 2: ACP 协议 + 会话管理 | ✅ 已完成 | 2026-04-13 |
| Phase 3: 进度监听 + 结果回推 | ✅ 已完成 | 2026-04-14 |
| Phase 4: 错误处理 + 日志 | ✅ 已完成 | 2026-04-14 |
| Phase 5: Service / Repository / Worker Adapter 重构 | ✅ 已完成 | 2026-04-17 |
| Phase 6: 持久化与统一事件模型 | 📋 待开始 | - |

---

## 参考资源

- [Hermes Plugin 开发指南](https://hermes-agent.nousresearch.com/docs/developer-guide/build-a-hermes-plugin)
- [Agent Client Protocol Spec](https://github.com/agent-client-protocol)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)
- [Qwen CLI](https://github.com/QwenLM/qwen-cli)
- [技术方案文档](docs/ACP_CLIENT_PLUGIN_PROPOSAL.md)

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**创建日期**: 2026-04-13  
**最后更新**: 2026-04-17  
**版本**: 0.2.1
