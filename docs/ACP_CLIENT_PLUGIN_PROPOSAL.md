# Hermes ACP Client Plugin - 当前实现与演进技术方案

## 文档信息

| 项目 | 内容 |
|------|------|
| **项目名称** | hermes-acp-client-plugin |
| **当前版本** | 0.2.1 |
| **文档类型** | 实现说明 + 演进方案 |
| **最后更新** | 2026-04-17 |
| **状态** | 已实现基础架构，待继续增强 |

---

## 1. 文档目标

这份文档不再描述“从零开始如何设计一个 ACP Client 插件”，而是基于当前代码库的真实实现，回答 3 个问题：

1. 当前项目已经实现了什么
2. 当前运行逻辑是如何串起来的
3. 下一步应该沿什么方向继续修正和演进

本文档以代码库当前结构为准，重点覆盖：

- Hermes 插件入口与工具注册
- ACP 消息协议与 stdio 传输
- 会话状态管理
- Service / Repository / Worker Adapter 分层
- 已知设计边界
- 推荐修正方向

---

## 2. 项目定位

Hermes ACP Client Plugin 是一个运行在 Hermes 内部的 **ACP Client 插件**。

它的职责不是充当最终的 AI Agent，而是：

- 从 Hermes 接收任务
- 将任务派发到外部 ACP 兼容 worker
- 跟踪子会话的状态变化
- 将进度和结果回传给 Hermes

当前支持的 worker 注册表包含：

- `gemini`
- `claude`
- `codex`
- `qwen`

这些 worker 通过 `stdio + JSON-RPC 2.0` 形式接入。

---

## 3. 当前实现总览

### 3.1 运行时分层

当前项目已经从“工具函数直接编排一切”的结构，重构为更清晰的 6 层：

```text
Hermes
└─ Plugin Entry
   ├─ plugin.yaml
   └─ __init__.py
      └─ register(ctx)
         └─ 注册 tools + schemas + hook

Tool Layer
└─ tools.py
   └─ 薄入口，只负责把调用转发给 services

Service Layer
├─ services/dispatch_service.py
├─ services/progress_service.py
└─ services/result_service.py

Repository Layer
├─ repositories/session_repository.py
└─ repositories/memory_session_repository.py

Worker Adapter Layer
├─ workers/base.py
└─ workers/registry.py

ACP Infrastructure Layer
├─ acp/protocol.py
├─ acp/transport.py
├─ acp/session_manager.py
└─ acp/hooks.py
```

### 3.2 各层职责

| 层级 | 文件 | 职责 |
|------|------|------|
| 插件入口层 | `plugin.yaml`, `__init__.py`, `schemas.py` | 声明插件、注册工具和参数契约 |
| 工具层 | `tools.py` | Hermes 调用入口，保持轻量，不承载复杂业务逻辑 |
| 服务层 | `services/*.py` | 负责编排派发、查询、取消、清理等核心流程 |
| 仓库层 | `repositories/*.py` | 抽象 session 状态读写，当前落在内存实现 |
| Worker 适配层 | `workers/*.py` | 封装 worker 命令和能力信息 |
| ACP 基础设施层 | `acp/*.py` | 协议消息、传输、会话状态机、hook 注入 |

---

## 4. 当前目录结构

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
│   ├── __init__.py
│   ├── protocol.py
│   ├── transport.py
│   ├── session_manager.py
│   └── hooks.py
├── services/
│   ├── __init__.py
│   ├── dispatch_service.py
│   ├── progress_service.py
│   └── result_service.py
├── repositories/
│   ├── __init__.py
│   ├── session_repository.py
│   └── memory_session_repository.py
├── workers/
│   ├── __init__.py
│   ├── base.py
│   └── registry.py
└── docs/
    ├── ACP_CLIENT_PLUGIN_PROPOSAL.md
    ├── ACP_ERROR_HANDLING.md
    ├── WORKER_COMPARISON.md
    ├── QWEN_ADVANCED_TEST.md
    └── ...
```

---

## 5. 核心运行逻辑

### 5.1 启动阶段

Hermes 加载插件后：

1. 读取 `plugin.yaml`
2. 调用根级 `__init__.py:register(ctx)`
3. 注册 7 个工具：
   - `acp_dispatch`
   - `acp_progress`
   - `acp_result`
   - `acp_cancel`
   - `acp_list`
   - `acp_cleanup`
   - `acp_shutdown`
4. 注册 `pre_llm_call_hook`

这一步的意义是把 ACP client 能力暴露给 Hermes，同时在每次 LLM 调用前注入活跃任务进度。

---

### 5.2 派发主链路

`acp_dispatch` 的当前调用链如下：

```text
Hermes
└─ tools.acp_dispatch(...)
   └─ DispatchService.dispatch(...)
      ├─ ensure_initialized(worker)
      │  └─ initialize_transport(...)
      │     ├─ get_transport(worker)
      │     ├─ 启动 stdio 子进程
      │     └─ 发送 initialize 请求
      │
      ├─ transport.create_session()
      │  └─ 发送 session/new
      │
      ├─ repository.create_session(...)
      │
      ├─ adapter.build_prompt(...)
      │
      ├─ transport.send_prompt(...)
      │  └─ 发送 session/prompt
      │
      └─ 根据响应执行两种路径
         ├─ 直接 result -> 标记 completed 并写入 result
         └─ error -> 标记 failed 并写入 error
```

### 当前行为特点

- `tools.py` 不再直接操作 transport 或 SessionManager
- `DispatchService` 是派发主链路的唯一编排入口
- prompt 的构造由 Worker Adapter 负责
- 状态写回走 Repository 抽象，不直接耦合到 SessionManager 内部字典

---

### 5.3 通知与状态更新

worker 在运行过程中可能通过通知推送状态变化。

当前通知入口为：

```text
StdioTransport._handle_notification(...)
└─ DispatchService.handle_notification(data)
   └─ repository.update_session(...)
```

当前已显式处理的通知类型有：

- `session/state`
- `session/log`

对于 `session/state`：

- `idle` -> `pending`
- `running` -> `running`
- `completed` -> `completed`
- `failed` -> `failed`
- `cancelled` -> `cancelled`

同时还会更新：

- `progress`
- `progress_message`
- `result`
- `error`
- `started_at`
- `completed_at`

这意味着系统既支持：

- 同步结果返回
- 异步通知回推

但二者目前仍是两条并存路径，而不是统一事件模型。

---

### 5.4 查询与回收逻辑

#### `acp_progress`

```text
tools.acp_progress(task_id)
└─ ProgressService.get_progress(task_id)
   └─ repository.get_progress(task_id)
```

用于返回：

- 状态
- 当前进度
- 进度消息
- 创建时间 / 更新时间

#### `acp_result`

```text
tools.acp_result(task_id, wait, timeout)
└─ ResultService.get_result(...)
   ├─ repository.get_session(task_id)
   └─ repository.wait_for_completion(task_id, timeout)
```

会根据终态补充：

- `success`
- `failure_reason`

#### `acp_cancel`

```text
tools.acp_cancel(task_id)
└─ ResultService.cancel(task_id)
   ├─ repository.get_session(task_id)
   ├─ peek_transport(worker)
   ├─ adapter.get_cancel_handler(transport)
   └─ repository.update_session(... status=cancelled)
```

当前取消策略是 **best-effort**：

- 如果 worker adapter 暴露了 cancel handler，则尝试远程取消
- 如果不支持，则返回 `cancellation_scope=local_only`
- 本地 session 状态始终会标记为 `cancelled`

---

### 5.5 Hook 注入逻辑

`pre_llm_call_hook` 当前负责把“活跃 ACP 任务摘要”插入 Hermes 上下文。

调用链如下：

```text
Hermes LLM Call
└─ pre_llm_call_hook(context)
   └─ ProgressInjector.pre_llm_call(context)
      ├─ repository.list_sessions()
      ├─ 选出 running/pending 的 session
      ├─ 生成摘要消息
      └─ 注入为 system message
```

当前实现已经修复了重复堆叠问题：

- 老的 ACP 进度 system message 会被替换
- 不会在上下文中无限追加重复进度块

---

## 6. 关键设计决策

### 6.1 工具层保持薄入口

这是当前代码里最重要的结构性改进之一。

优点：

- Hermes 对外接口保持稳定
- 内部重构不会影响工具签名
- 更容易给 service 层补测试或替换实现

代价：

- service 层数量变多
- 需要统一 service 之间的边界和共享依赖

---

### 6.2 引入 Repository 抽象

虽然底层仍是 `SessionManager` 内存实现，但 Repository 抽象已经把“状态访问方式”和“状态存储位置”分开了。

这为后续改造成以下实现提供了落点：

- SQLite Repository
- JSON 文件 Repository
- Redis Repository

当前价值不在于功能变强，而在于后续演进成本下降。

---

### 6.3 引入 Worker Adapter Registry

当前 worker 命令和能力通过 `workers/registry.py` 管理，而不是散落在多个模块中。

当前 adapter 已承载：

- worker 名称
- 启动命令
- 能力声明：
  - `supports_cancel`
  - `supports_stream_updates`
- prompt 构造入口
- prompt response 规范化入口

这一步虽然还比较轻，但已经是后续兼容多个 CLI 的正确方向。

---

## 7. 当前设计的优点

### 7.1 结构明显比早期方案更清晰

当前实现已经从“一个大工具文件直接处理所有逻辑”，进化为可维护的分层结构。

### 7.2 Hermes 接入点稳定

插件入口和工具签名很薄，后续内部怎么重构，对 Hermes 来说都不需要改接口。

### 7.3 Worker 可扩展性更好

继续接入其他 ACP 兼容 CLI 时，不需要再改 transport 的核心职责，只需补 adapter。

### 7.4 为持久化和恢复留出了接口

虽然还没实现持久化，但 Repository 已经把这个口子开出来了。

---

## 8. 当前设计的边界与问题

### 8.1 Session 仍然是内存态

这是当前最明显的系统边界。

后果：

- 进程重启后 session 全丢
- 无法恢复历史任务
- 无法实现真正的跨进程恢复或 crash recovery

影响等级：高。

---

### 8.2 通知模型仍不统一

当前有两条状态完成路径：

1. `session/prompt` 直接返回 result
2. worker 通过 `session/state` 通知异步完成

这在功能上可用，但在架构上意味着：

- 终态进入系统的来源不统一
- future streaming / chunk merge / transcript 处理会更复杂

---

### 8.3 cancel 语义仍偏弱

虽然结构上已经支持通过 adapter 探测取消能力，但大多数 worker 当前仍是：

- 本地状态可取消
- 远程 worker 未必真的被终止

这会带来“UI 显示已取消，但子进程可能还在工作”的语义偏差。

---

### 8.4 transport 的错误处理仍是启发式

当前 stderr JSON 错误解析是为了兼容现有 CLI 行为做的实用方案，但它不是严格协议保证。

潜在风险：

- stderr 输出格式变化会导致错误解析失效
- stdout / stderr 混杂行为可能随 worker 升级而改变

---

### 8.5 当前仓库不保留 committed tests 目录

目前项目仓库里不再保留 committed `tests/` 目录。

这意味着：

- 文档和实现需要更强调可读性与结构化
- 若继续推进生产化，应重新建立一套正式的自动化测试策略

这不是立即阻塞项，但属于工程化缺口。

---

## 9. 推荐修正方向

下面按优先级给出建议。

### 9.1 P0：补持久化 Repository

目标：

- 让 session 至少可以跨进程保留
- 为 crash recovery 和运维可观测性打基础

推荐最小实现：

- 新增 `SqliteSessionRepository`
- 将当前 `MemorySessionRepository` 保留为默认开发实现
- 通过配置切换 repository backend

推荐理由：

- 改动集中在 repository 层
- 不需要推翻现有 service 层
- 投入小，收益大

---

### 9.2 P0：统一状态事件模型

目标：

- 不再分别处理“同步结果完成”和“异步通知完成”
- 所有终态都走统一事件写回路径

建议做法：

- 在 `DispatchService` 内增加统一的“状态归并函数”
- 对 direct result 也包装成内部统一事件对象后再更新 repository

这样后续要接流式 chunk、完整 transcript、token usage 时，不需要再加第三条路径。

---

### 9.3 P1：增强 Worker Adapter

当前 adapter 还比较轻，下一步建议补这些能力：

- `normalize_notification(data)`
- `extract_progress(data)`
- `extract_final_result(data)`
- `supports_resume`
- `supports_session_restore`

这样可以把 worker 差异继续从 service/transport 中剥离出去。

---

### 9.4 P1：收紧状态机

虽然 `SessionStatus` 已经定义了状态枚举，但状态流转本身还比较宽松。

建议显式限制：

- `pending -> running`
- `running -> completed`
- `running -> failed`
- `running -> cancelled`
- `pending -> cancelled`

禁止无意义回跳，比如：

- `completed -> running`
- `failed -> running`

这能减少通知乱序时的状态污染。

---

### 9.5 P2：重新建立正式测试策略

当前更适合做两层测试：

#### 单元测试

覆盖：

- service 层行为
- repository 语义
- worker adapter 选择和能力声明
- hook 注入逻辑

#### 集成测试

覆盖：

- transport 与本地 mock worker 的 JSON-RPC 通信
- 不直接依赖真实第三方 CLI

这样可以避免把测试体系绑死在外部模型环境上。

---

## 10. 建议演进路线图

### 阶段 A：稳定内核

- 增加持久化 repository
- 统一状态归并路径
- 收紧状态机

### 阶段 B：增强多 worker 兼容

- 扩展 worker adapter 能力
- 明确每个 worker 的能力矩阵
- 统一 streaming / log / result 提取

### 阶段 C：工程化补齐

- 补单元测试与 mock integration 测试
- 增加结构化日志
- 补 session 导出 / 诊断能力

---

## 11. 当前结论

当前项目已经不再是“纯概念方案”。

它已经具备：

- Hermes 插件入口
- 可用的工具注册
- ACP 协议消息建模
- stdio worker 通信
- 本地 session 管理
- service / repository / worker adapter 三层结构
- 进度 hook 注入

从架构判断，它现在处于：

> **基础实现已成型，核心方向正确，但仍需补持久化、统一事件模型和工程化测试，才能走向稳定可维护版本。**

这也是本文档建议的后续修正主线。

---

## 12. 附录：当前主时序图（文本版）

```text
[Hermes 启动]
  └─ 读取 plugin.yaml
      ├─ 注册工具
      └─ 注册 pre_llm_call_hook

[用户发起任务]
  └─ Hermes 调用 tools.acp_dispatch(...)
      └─ DispatchService.dispatch(...)
          ├─ initialize_transport(...)
          ├─ create_session()
          ├─ repository.create_session(...)
          ├─ adapter.build_prompt(...)
          ├─ send_prompt(...)
          └─ 写回 completed / failed / running

[worker 异步通知]
  └─ StdioTransport._handle_notification(...)
      └─ DispatchService.handle_notification(...)
          └─ repository.update_session(...)

[用户查询]
  ├─ acp_progress -> ProgressService -> repository
  ├─ acp_result   -> ResultService   -> repository
  └─ acp_cancel   -> ResultService   -> transport + repository

[Hermes 再次调用 LLM 前]
  └─ pre_llm_call_hook
      └─ ProgressInjector
          └─ repository.list_sessions()
              └─ 注入系统消息摘要
```
