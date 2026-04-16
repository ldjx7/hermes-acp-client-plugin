文件写入被拒绝。以下是完整的优化报告 v3.0：

---

# ACP Client 插件优化报告 v3.0

**分析日期**: 2026-04-16 | **代码总量**: 2,481 行 Python + 349 行 JavaScript

## 执行摘要

v3.0 基于全部源码逐行审计，聚焦**真实代码缺陷**。心跳监控器从 ~300 行简化至 239 行（纯进度反馈），设计方向正确。但简化过程遗留了死代码和一个严重逻辑 bug，加上 Claude CLI 适配器的双重响应问题。

| 维度 | v2.0 | v3.0 | 变化 |
|------|------|------|------|
| 心跳机制 | 300行，含超时 | 239行，纯进度 | 简化正确 |
| 高优先级问题 | 0 项 | **3 项** | 新发现 |
| 中优先级问题 | 2 项 | 4 项 | 调整 |
| 低优先级问题 | 5 项 | 3 项 | 精简 |
| 总体评分 | 8.6/10 | **7.8/10** | 下调 |

---

## 1. 架构分析

### 模块全景
```
tools.py              (520行) - acp_dispatch 入口
tools/claude-cli-acp.js (349行) - Claude CLI ACP 适配器
acp/protocol.py        (89行) - JSON-RPC 协议
acp/transport.py      (769行) - StdioTransport + OpenACPTransport
acp/session_manager.py (133行) - 会话状态
acp/heartbeat_monitor.py (239行) - 心跳监控（简化版）
acp/worker_manager.py  (355行) - Worker管理与故障转移
acp/openacp_bridge.py  (452行) - OpenACP HTTP桥接
acp/daemon_manager.py  (184行) - daemon进程管理
acp/hooks.py           (183行) - pre_llm_call 钩子
```

**优点**: 多Worker架构清晰，Stdio/HTTP两种传输解耦良好，心跳简化方向正确，OpenACP异常分层合理（6种异常类型）

---

## 2. 发现的问题

### 高优先级 (3项)

#### 3.1 `_send_with_heartbeat` 无限循环
**`acp/transport.py:647-665`**

`while not result_event.is_set()` 永远不会通过 `result_event` 退出——没有任何代码调用 `result_event.set()`。如果 Worker 崩溃且未发送响应，此循环永远运行，造成线程泄漏。

```python
while not result_event.is_set():    # 永远不会被 set()
    try:
        response = q.get(timeout=5)  # 唯一出口
        return response
    except queue.Empty:
        pass  # 永远不退出
```

**修复**: 将条件改为 `while self._running`，并在循环内检查 `self.process.poll() is not None`（进程已退出时返回错误）。

---

#### 3.2 Claude CLI 双重响应
**`tools/claude-cli-acp.js:175-219` + `290-334`**

`handleSessionPrompt` 在 `callClaudeCLI` resolve 后发送响应（188-195行），而 `callClaudeCLI` 内部的 `claude.on('close')` 也用相同 `id` 发送响应（293-310行）。同一请求收到**两次 JSON-RPC 响应**。

**修复**: `callClaudeCLI` 的 `on('close')` 只 `resolve(output.trim())`，不调用 `sendResponse`，让 `handleSessionPrompt` 统一发送。

---

#### 3.3 StdioTransport 遗留死代码
**`acp/transport.py:247-267`**

简化心跳后，`heartbeat_timeout`、`first_response_timeout`、`max_total_time` 三个参数仍在 `__init__` 中接受和存储，但**从未被读取**。误导调用方以为超时仍生效。

**修复**: 删除这三个参数及赋值。

---

### 中优先级 (4项)

#### 3.4 `acp_cleanup` 迭代时修改字典
**`tools.py:458-461`** — 遍历 `sessions.items()` 同时调用 `delete_session`，Python 3 会抛 `RuntimeError`。修复：先收集ID再删除。

#### 3.5 `dispatch_with_fallback` 与 `acp_dispatch` 重复
**`worker_manager.py:238-307` vs `tools.py:88-267`** — 两处都实现了 Worker选择+故障转移+重试，且形成循环依赖。建议保留 `acp_dispatch` 作唯一入口。

#### 3.6 `wait_for_completion` 忙等待
**`session_manager.py:120-130`** — `while True: sleep(0.5)` 轮询。应改用 `threading.Event.wait(timeout)`。

#### 3.7 直接访问 `_sessions` 私有属性
**`hooks.py:59`、`tools.py:412`** — 多处直接访问 `manager._sessions`。应添加 `list_sessions()` 公开方法。

---

### 低优先级 (3项)

| # | 问题 | 位置 |
|---|------|------|
| 3.8 | Worker 模型名称可能过期 | `worker_manager.py:327-329` |
| 3.9 | 超时配置分散在5个文件 | 多处 |
| 3.10 | stderr 缓冲逻辑不清晰 | `transport.py:307-340` |

---

## 3. 与之前报告的差异

### v1.0/v2.0 建议的重新评估

| 之前建议 | v3.0 判定 | 理由 |
|----------|-----------|------|
| JSON 非阻塞解析（中） | **不需要** | `readline()` 在独立守护线程中，不阻塞主线程 |
| 分段锁 SessionRegistry（中） | **不需要** | 并发量远未达到单锁瓶颈 |
| Prometheus 指标（低） | **移除** | 过度工程化，`worker_manager` 已有基础指标 |
| 智能重试策略（中） | **降级** | 当前退避 `delay*(attempt+1)` 足够 |
| 插件钩子（低） | **已存在** | `acp/hooks.py` 已实现 `pre_llm_call` |

### v3.0 新发现及原因

| 问题 | 为何之前未发现 |
|------|----------------|
| `_send_with_heartbeat` 无限循环 | v2.0 有超时判断保底，简化后暴露 |
| Claude CLI 双重响应 | 需对比两函数完整执行路径 |
| `acp_cleanup` 字典并发修改 | 需跟踪 `delete_session` 副作用 |
| 死代码（超时参数） | 简化心跳后新产生的遗留 |

---

## 4. 优化建议汇总

### 推荐执行顺序

**立即修复（2.5h）**:
1. `_send_with_heartbeat` 添加进程存活检查 + `_running` 退出条件
2. Claude CLI `callClaudeCLI` 只 resolve/reject，不发 sendResponse
3. 删除 `StdioTransport` 未使用的超时参数

**本周修复（3h）**:
4. `acp_cleanup` 先收集再删除
5. 删除 `dispatch_with_fallback` 重复逻辑
6. `wait_for_completion` 改用 `threading.Event`
7. 添加 `SessionManager.list_sessions()`

**可选（4.5h）**:
8. 更新模型名称
9. 配置统一
10. stderr 缓冲清理

---

## 5. 总结

| 维度 | v2.0 | v3.0 | 说明 |
|------|------|------|------|
| 功能完整性 | 9/10 | 9/10 | 核心功能齐全 |
| 稳定性 | 9/10 | **7/10** | 无限循环+双重响应 |
| 性能 | 8/10 | 8/10 | 忙等待可优化 |
| 代码质量 | 8/10 | **7/10** | 死代码、重复、私有访问 |
| 架构设计 | — | 8/10 | 模块清晰，心跳简化正确 |

**总体: 7.8/10** — 修复3项高优先级问题仅需2.5小时，建议立即执行。