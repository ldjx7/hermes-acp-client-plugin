# Hermes ACP Client Plugin

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Hermes Plugin](https://img.shields.io/badge/Hermes-Plugin-orange.svg)](https://github.com/nousresearch/hermes-agent)

> **让 Hermes Agent 拥有"分身"能力** —— 派发任务到独立的 AI Agent 子会话，实时监听进度，自动回收结果。

---

## 📖 简介

Hermes ACP Client Plugin 实现了 **ACP (Agent Client Protocol)** 客户端，使 Hermes 能够：

- 🚀 **派发子会话** - 将复杂任务派发到独立的 AI Agent（Gemini/Claude/Codex）
- 📊 **监听进度** - 实时接收子会话的执行状态和进度更新
- ✅ **结果回推** - 自动将子会话结果写回父会话

### 为什么需要 ACP？

| 场景 | 传统方式 | ACP 方式 |
|------|----------|----------|
| 复杂代码生成 | 单次请求，上下文有限 | 子会话独立处理，1M+ 上下文 |
| 代码审查 | 占用主会话 token | 子会话完成，主会话继续其他任务 |
| 多步骤任务 | 顺序执行，耗时长 | 并行派发，异步回收 |

### Worker 性能对比

| Worker | 成功率 | 平均耗时 | 推荐场景 |
|--------|--------|----------|----------|
| **Gemini CLI** | 100% (5/5) | 28.78s | 代码生成、审查、算法 |
| Qwen CLI | 20% (1/5) | 244s+ | 简单任务（需 300s+ 超时） |
| Claude | 待测试 | - | - |
| Codex | 待测试 | - | - |

---

## 🚀 快速开始

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
/acp_progress --session-id abc123

# 3. 获取结果
/acp_result --session-id abc123
```

### 完整工作流

```
用户请求 → Hermes → acp_dispatch → Gemini 子会话
                              ↓
                          执行任务 (代码生成/审查/分析)
                              ↓
                          实时进度更新 ← acp_progress
                              ↓
                          完成 → acp_result → 返回给 Hermes
```

---

## 📁 项目结构

```
hermes-acp-client-plugin/
├── acp/                          # 核心 ACP 模块
│   ├── __init__.py
│   ├── protocol.py               # ACP 协议消息 (JSON-RPC 2.0)
│   ├── session_manager.py        # 会话生命周期管理
│   └── transport.py              # Stdio 传输层
├── docs/                         # 文档
│   ├── WORKER_COMPARISON.md      # Worker 性能对比
│   ├── ACP_ERROR_HANDLING.md     # 错误处理指南
│   └── QWEN_ADVANCED_TEST.md     # Qwen 兼容性报告
├── tests/                        # 测试套件
│   ├── test_gemini_acp.py        # Gemini ACP 测试
│   ├── test_qwen_acp.py          # Qwen ACP 测试
│   └── test_advanced_v2.py       # 高级任务测试
├── tools.py                      # Hermes 工具定义
├── schemas.py                    # 工具参数 Schema
├── plugin.yaml                   # 插件配置
├── README.md                     # 本文件
└── requirements.txt              # 依赖
```

---

## 🛠️ 核心工具

| 工具 | 功能 | 参数 |
|------|------|------|
| `acp_dispatch` | 派发任务到 ACP worker | `task`, `worker`, `timeout`, `auto_fallback` |
| `acp_progress` | 查询任务进度 | `session_id` |
| `acp_result` | 获取最终结果 | `session_id`, `wait`, `timeout` |
| `acp_worker_status` | **查询 Worker 状态** | - |
| `acp_cancel` | 取消任务 | `session_id` |
| `acp_list` | 列出会话 | `active_only` |
| `acp_cleanup` | 清理旧会话 | `max_age_hours` |

### 工具调用示例

```yaml
# acp_dispatch
action: acp_dispatch
args:
  task: "实现一个二分查找算法，包含类型注解和单元测试"
  worker: gemini
  timeout: 120

# acp_progress
action: acp_progress
args:
  session_id: "08433c12-097b-4091-b467-a480fffb700e"

# acp_result
action: acp_result
args:
  session_id: "08433c12-097b-4091-b467-a480fffb700e"
```

---

## 📊 测试结果

### Gemini ACP 测试 (5/5 成功)

| 测试项目 | 结果 | 耗时 |
|----------|------|------|
| 代码生成 (email_validator) | ✅ | 84.01s |
| 代码审查 (security) | ✅ | 15.86s |
| 算法实现 (binary_search) | ✅ | 16.75s |
| 简单对话 (hello) | ✅ | 17.88s |
| 文件操作 (read_file) | ✅ | 9.38s |

**总计**: 5/5 成功 | 平均耗时: 28.78s

详细报告：[docs/WORKER_COMPARISON.md](docs/WORKER_COMPARISON.md)

---

## 🔧 配置

### plugin.yaml

```yaml
name: acp-client
version: 1.0.0
description: ACP (Agent Client Protocol) client for Hermes Agent
author: Hermes Agent
tools:
  - acp_dispatch
  - acp_progress
  - acp_result
dependencies:
  - python >= 3.9
```

### Worker 配置

在 `acp/transport.py` 中配置 Worker：

```python
WORKER_CONFIGS = {
    "gemini": {"cmd": "gemini", "args": ["--acp"]},
    "qwen": {"cmd": "qwen", "args": ["--acp", "--dangerously-skip-permissions"]},
    "claude": {"cmd": "claude", "args": ["--acp", "--stdio"]},
    "codex": {"cmd": "codex", "args": ["--acp"]},
}
```

---

## 🧪 运行测试

```bash
# Gemini ACP 测试
python3 tests/test_gemini_acp.py

# Qwen ACP 测试
python3 tests/test_qwen_acp.py

# 高级任务测试
python3 tests/test_advanced_v2.py
```

测试输出保存在 `tests/output/` 目录。

---

## 📝 开发路线图

| 阶段 | 状态 | 完成日期 |
|------|------|----------|
| Phase 1: 基础框架 | ✅ 已完成 | 2026-04-13 |
| Phase 2: ACP 协议 + 会话管理 | ✅ 已完成 | 2026-04-13 |
| Phase 3: 进度监听 + 结果回推 | ✅ 已完成 | 2026-04-14 |
| Phase 4: 错误处理 + 日志 | ✅ 已完成 | 2026-04-14 |
| Phase 5: 测试 + 文档 | ✅ 已完成 | 2026-04-14 |
| Phase 6: Claude/Codex 支持 | 📋 待开始 | - |

---

## 🔗 参考资源

- [Hermes Plugin 开发指南](https://hermes-agent.nousresearch.com/docs/developer-guide/build-a-hermes-plugin)
- [Agent Client Protocol Spec](https://github.com/agent-client-protocol)
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)
- [Qwen CLI](https://github.com/QwenLM/qwen-cli)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**创建日期**: 2026-04-13  
**最后更新**: 2026-04-14  
**版本**: 1.0.0
