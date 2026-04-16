# 心跳超时机制 - 设计修正

**日期**: 2026-04-16  
**问题**: 心跳超时过短，错误终止正常任务  
**状态**: ✅ 已修复

---

## 问题根源

### 错误理解

```python
# ❌ 之前的配置
heartbeat_monitor = HeartbeatMonitor(
    first_response_timeout=120.0,  # 2 分钟
    heartbeat_timeout=120.0,       # 2 分钟 - 错误！Claude 思考可能超过这个时间
    max_total_time=1800.0,         # 30 分钟
)
```

**错误逻辑**：
- 用心跳超时**替代**Agent 自己的超时机制
- 假设 2 分钟无输出 = 任务失败
- **实际上**：Claude 复杂任务思考 3-5 分钟是正常的

### 测试结果证明

```
测试：gemini - 代码生成
耗时：120 秒
状态：failed
错误：Heartbeat timeout: first_response: No response in 120.4s

❌ 这不是失败！Gemini 可能正在工作，只是启动慢
```

---

## 正确理解

### 心跳机制的真正用途

```
┌─────────────────────────────────────────────────────────────┐
│ 心跳机制 = 最后防线（检测假死）                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  第一层：Agent 自己的超时                                   │
│  - Claude CLI: 15 分钟                                       │
│  - Gemini CLI: 自带超时                                     │
│  - 这些才是主要的超时判断                                    │
│                                                              │
│  第二层：心跳监控（最后防线）                               │
│  - 检测进程假死（进程在，但卡住）                           │
│  - 检测连接断开（stdout 关闭）                              │
│  - 超时应该很长（10 分钟+）                                 │
│                                                              │
│  关系：                                                      │
│  Agent 超时 (15min) < 心跳超时 (60min)                      │
│  ↑ 先触发                                                    │
└─────────────────────────────────────────────────────────────┘
```

### 正确的工作流程

```
发送请求 → Claude CLI 启动 → 思考/生成 → 输出 → 完成
    ↓           ↓              ↓         ↓       ↓
    │           │              │         │       └─→ 清理监控
    │           │              │         └─→ 心跳重置（有输出）
    │           │              └─→ 正常沉默（不触发超时）
    │           └─→ 启动时间（可能 1-2 分钟）
    └─→ 注册监控

超时判断：
1. Claude CLI 自己超时（15 分钟）→ 返回错误 ✅
2. 进程假死（60 分钟无活动）→ 心跳超时 ✅
```

---

## 修复方案

### 新配置

```python
# acp/heartbeat_monitor.py
heartbeat_monitor = HeartbeatMonitor(
    first_response_timeout=300.0,     # 5 分钟 - 给慢启动 Agent 足够时间
    heartbeat_timeout=600.0,          # 10 分钟 - 仅检测假死
    max_total_time=3600.0,            # 60 分钟 - 由 Agent 自己决定
    progress_threshold=0.01
)
```

### 参数说明

| 参数 | 旧值 | 新值 | 原因 |
|------|------|------|------|
| `first_response_timeout` | 120s | 300s | Gemini/Claude 启动可能很慢 |
| `heartbeat_timeout` | 120s | 600s | Claude 思考时间可能很长 |
| `max_total_time` | 1800s | 3600s | 复杂任务可能需要更久 |

### 设计原则

```
心跳超时 >> Agent 超时

Claude CLI:  15 分钟超时
心跳监控：   60 分钟超时（最后防线）

这样：
- Claude 正常工作时，由 Claude 自己决定何时超时 ✅
- Claude 假死时，心跳机制兜底检测 ✅
- 不会错误终止正常任务 ✅
```

---

## 使用建议

### 默认配置（推荐）

```python
from tools import acp_dispatch

# 无需配置 - 使用默认值
result = acp_dispatch('任务...', worker='claude-cli')

# 心跳机制在后台运行，仅检测假死
```

### 特殊情况

```python
from acp.transport import get_transport

# 快速任务 - 可以缩短超时
transport = get_transport(worker='gemini')
transport.first_response_timeout = 60.0   # 1 分钟
transport.heartbeat_timeout = 300.0       # 5 分钟

# 超长任务 - 延长超时
transport = get_transport(worker='claude-cli')
transport.max_total_time = 7200.0         # 2 小时
```

---

## 验证测试

### 预期行为

| 场景 | 预期行为 | 超时时间 |
|------|----------|----------|
| Claude 简单任务 | 正常完成 | 5-10 秒 |
| Claude 复杂任务 | 正常完成 | 1-5 分钟 |
| Claude 思考中 | 等待（不超时） | 3-5 分钟正常 |
| Claude API 错误 | 返回错误 | 立即 |
| Claude 进程假死 | 心跳超时 | 10 分钟 |
| Gemini 启动慢 | 等待（不超时） | 2-3 分钟正常 |

### 测试命令

```bash
# 测试复杂任务（应该正常完成，不超时）
python3 -c "
from tools import acp_dispatch
result = acp_dispatch(
    '写一个完整的 Python 项目，包含文档和测试',
    worker='claude-cli',
    timeout=600
)
print(result)
"

# 预期：
# - Claude 思考 2-3 分钟 → 正常
# - 开始输出 → 心跳重置
# - 完成 → 清理监控
```

---

## 总结

### 核心修正

| 概念 | 之前 | 现在 |
|------|------|------|
| 心跳超时用途 | 主要超时判断 | 最后防线（检测假死） |
| 超时优先级 | 心跳 > Agent | Agent > 心跳 |
| 超时时间 | 2 分钟 | 10 分钟 |
| 设计哲学 | 严格限制 | 宽松兜底 |

### 设计原则

```
1. Agent 自己的超时机制是主要的
2. 心跳机制是最后防线（检测假死）
3. 心跳超时 >> Agent 超时
4. 宁可等待，不要错误终止
```

### 文档更新

- [x] `docs/HEARTBEAT_TIMEOUT_FIX.md` - 本修正文档
- [ ] `docs/HEARTBEAT_USAGE_GUIDE.md` - 需要更新配置部分
- [ ] `docs/OPTIMIZATION_REPORT_V2.md` - 需要更新优先级

---

**感谢用户的正确指导！** 🙏

**修复者**: AI Assistant  
**修复日期**: 2026-04-16  
**状态**: ✅ 已完成
