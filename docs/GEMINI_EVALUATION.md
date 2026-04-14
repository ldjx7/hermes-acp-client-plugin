# Hermes ACP Client Plugin 技术评估报告

## 1. 可行性分析 (Feasibility Analysis)

### 1.1 协议基础 (Protocol Foundation)
- **结论：高度可行。**
- **理由**：Hermes 已经具备成熟的 ACP Server 实现（`acp_adapter/server.py`），这意味着底层的 `acp` Python 包已经集成。开发 Client 插件只需利用现有的消息类型（`InitializeRequest`, `PromptRequest` 等）进行封装，无需从零开发协议栈。
- **一致性**：ACP 协议的标准化（JSON-RPC 2.0）确保了与其他符合规范的 Agent（如 Gemini CLI）的互操作性。

### 1.2 插件架构 (Plugin Architecture)
- **结论：可行，但需注意异步处理。**
- **理由**：Hermes 的插件系统允许定义 `tools` 和 `hooks`。
- **挑战**：ACP 通信本质上是异步流（Streaming/Events），而 Hermes 的工具调用通常是同步阻塞的。
- **对策**：采用“发后即返 + 轮询/回调”模式。`acp_dispatch` 立即返回 `session_id`，而后台线程处理 ACP 消息流并更新内部状态机。

### 1.3 环境依赖
- **结论：可行。**
- **理由**：利用 `plugin.yaml` 中的 `requires_env` 可以优雅地处理 API Key 和后端路径配置。

---

## 2. Gemini CLI 替代 Codex ACP 的修正方案

### 2.1 为什么要替代 Codex？
- **生态集成**：Gemini CLI 拥有更强的上下文处理能力（1M+ tokens）和多模态理解。
- **工具链优势**：Gemini CLI 本身就是为开发者设计的终端 Agent，支持文件读写、搜索、Shell 执行等，更适合作为“代码执行 worker”。
- **协议兼容**：Gemini CLI 可以作为 ACP 兼容的 stdio server 运行，对接极其简单。

### 2.2 修正后的架构图 (Revised Architecture)
```
┌─────────────────┐             ┌─────────────────────┐
│  Hermes Agent   │             │   Gemini CLI        │
│ (ACP Client)    │   Stdio     │   (ACP Worker)      │
│ ┌─────────────┐ │  JSON-RPC   │ ┌─────────────────┐ │
│ │acp_dispatch ├─┼────────────>│ │ Execution Engine│ │
│ └─────────────┘ │             │ └─────────────────┘ │
└─────────────────┘             └─────────────────────┘
```

### 2.3 核心变更
- **Worker 类型**：将默认 worker 从 `codex` 修改为 `gemini-cli`。
- **启动模式**：`gemini-cli` 将通过 `stdio` 模式启动作为子进程，由插件管理生命周期。
- **能力映射**：利用 Gemini CLI 的 `codebase_investigator` 和 `generalist` 子 agent 来处理复杂的子任务。

---

## 3. Phase 1 实现步骤 (Phase 1 Implementation Steps)

Phase 1 的目标是实现 **“成功派发并获取初步响应”**。

### Step 1: 插件骨架与环境配置
- [ ] 创建目录：`~/.hermes/plugins/acp-client/`
- [ ] 编写 `plugin.yaml`：声明 `gemini-cli` 路径和必要的 Google API Keys。
- [ ] 初始化 `__init__.py`：注册工具。

### Step 2: 抽象 ACP 传输层 (Transport Layer)
- [ ] 实现 `StdioTransport`：负责 `gemini-cli --acp-server` 子进程的启动、读写和标准错误流捕获。
- [ ] 实现 `ACPMessageSerializer`：封装协议规范中的消息转换。

### Step 3: `acp_dispatch` 工具实现
- [ ] 定义 Schema：支持 `task`, `model`, `priority` 参数。
- [ ] 实现 Handler：启动 Gemini CLI 进程 -> `initialize` -> `new_session` -> `prompt`。
- [ ] 返回 `session_id` 给父会话，并建立 Session 状态追踪。

### Step 4: 冒烟测试
- [ ] 编写测试脚本，模拟 Hermes 调用 `acp_dispatch` 派发简单任务（如 "Hello World"）。
- [ ] 验证 Gemini CLI 进程是否被正确拉起并返回了 ACP 响应。

---

## 4. 结论与建议
方案在技术上完全成立。建议在 Phase 1 阶段优先解决 **“进程生命周期管理”** 问题，防止 `acp_dispatch` 产生大量孤儿进程。同时，建议 `gemini-cli` 采用 `is_background=true` 的逻辑进行封装，以匹配异步任务的需求。

---
*评估者：Gemini CLI (Autonomous Engineering Agent)*
*日期：2026-04-13*
