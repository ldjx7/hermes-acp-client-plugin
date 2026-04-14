# ACP Worker 故障转移功能总结

## ✅ 已完成功能

### 1. Worker 管理器 (`acp/worker_manager.py`)

```python
class WorkerManager:
    - 管理 4 个 Worker: gemini, claude, codex, qwen
    - 追踪每个 Worker 的状态、模型、成功率、响应时间
    - 自动检测速率限制错误
    - 60 秒冷却时间后自动恢复
```

### 2. 自动故障转移 (`tools.py`)

```python
def acp_dispatch(
    task: str,
    worker: str = "gemini",
    auto_fallback: bool = True,  # 新增参数
    max_retries: int = 3,
    timeout: float = 120.0
) -> str:
    """
    智能派发任务:
    1. 首选指定 Worker
    2. 失败则自动尝试下一个可用 Worker
    3. 检测速率限制，触发快速切换
    4. 记录每次尝试的模型和响应时间
    """
```

### 3. 状态查询工具 (`acp_worker_status`)

```python
# 调用示例
/acp_worker_status

# 返回
{
  "total_workers": 4,
  "available": 3,
  "rate_limited": 1,
  "recommended_worker": "claude",
  "workers": {
    "gemini": {
      "status": "rate_limited",
      "model": "gemini-2.5-flash",
      "success_rate": 95.2,
      "avg_response_time": 28.78,
      "rate_limit_reset": "2026-04-14T12:15:00"
    },
    ...
  }
}
```

---

## 🎯 使用场景

### 场景 1: 默认使用（推荐）

```python
# 自动故障转移，无需额外配置
/acp_dispatch --task "写一个 Python 函数"
```

**流程**:
```
Gemini (速率限制) → Claude (成功) ✅
```

### 场景 2: 指定首选 Worker

```python
# 优先使用 Claude，失败则 fallback
/acp_dispatch --task "代码审查" --worker claude
```

**流程**:
```
Claude (错误) → Gemini (成功) ✅
```

### 场景 3: 查询状态后决策

```python
# 先查询状态
/acp_worker_status

# 根据返回选择推荐 Worker
/acp_dispatch --task "复杂任务" --worker claude
```

---

## 📊 Worker 状态流转

```
available ──[速率限制]──> rate_limited ──[60 秒]──> available
     │
     └──[错误]──> error ──[手动恢复]──> available
     │
     └──[离线]──> offline ──[手动恢复]──> available
```

---

## 🔍 速率限制检测

支持检测以下错误：

```python
rate_limit_indicators = [
    "rate limit",          # 标准速率限制
    "too many requests",   # HTTP 429
    "quota exceeded",      # 配额超限
    "resource exhausted",  # 资源耗尽
    "429",                 # HTTP 状态码
    "throttl",             # 限流 (throttling)
]
```

---

## 🛠️ 配置选项

### 修改 Worker 优先级

```python
# acp/worker_manager.py
self._fallback_order = ["claude", "gemini", "codex", "qwen"]
# Claude 优先
```

### 修改冷却时间

```python
# acp/worker_manager.py
self._rate_limit_cooldown = 120  # 120 秒
```

### 禁用故障转移

```python
# 强制使用特定 Worker
/acp_dispatch --task "xxx" --worker gemini --auto_fallback false
```

---

## 📈 监控指标

### Worker 级别

| 指标 | 说明 |
|------|------|
| `status` | 当前状态 |
| `model` | 使用的模型 |
| `success_rate` | 成功率 (%) |
| `avg_response_time` | 平均响应时间 (秒) |
| `rate_limit_reset` | 速率限制解除时间 |

### 全局级别

| 指标 | 说明 |
|------|------|
| `total_workers` | Worker 总数 |
| `available` | 可用数量 |
| `rate_limited` | 速率限制数量 |
| `offline` | 离线数量 |
| `recommended_worker` | 推荐使用的 Worker |

---

## 🧪 测试建议

### 测试 1: 模拟速率限制

```python
# 手动标记为速率限制
from acp.worker_manager import get_worker_manager

manager = get_worker_manager()
manager.mark_error("gemini", "Rate limit exceeded", is_rate_limit=True)

# 派发任务，应该自动切换到 Claude
result = acp_dispatch(task="测试任务")
```

### 测试 2: 验证状态查询

```bash
# 查询状态
python3 -c "
from acp.worker_manager import get_worker_status
import json
print(json.loads(get_worker_status()))
"
```

### 测试 3: 完整流程测试

```python
# 连续派发多个任务
for i in range(5):
    result = acp_dispatch(task=f"任务 {i}")
    print(f"任务 {i}: {json.loads(result)['worker']}")
```

---

## 📝 更新日志

### v0.2.2 (2026-04-14)

**新增**:
- ✅ WorkerManager 类
- ✅ 自动故障转移逻辑
- ✅ 速率限制检测
- ✅ acp_worker_status 工具
- ✅ 模型信息提取

**修改**:
- 🔄 acp_dispatch 支持 auto_fallback 参数
- 🔄 plugin.yaml 注册新工具
- 🔄 README 更新文档

**文档**:
- 📄 docs/WORKER_FAILOVER.md 完整指南

---

## 🚀 下一步

### 已完成
- ✅ Worker 状态管理
- ✅ 自动故障转移
- ✅ 速率限制检测
- ✅ 状态查询工具

### 待完成
- 📋 Claude/Codex 实际测试
- 📋 负载均衡策略
- 📋 自定义 Worker 配置
- 📋 Webhook 通知（速率限制时）

---

## 🔗 相关文档

- [Worker 故障转移指南](docs/WORKER_FAILOVER.md)
- [Worker 性能对比](docs/WORKER_COMPARISON.md)
- [错误处理指南](docs/ACP_ERROR_HANDLING.md)

---

**仓库**: https://github.com/ldjx7/hermes-acp-client-plugin  
**版本**: 0.2.2  
**最后更新**: 2026-04-14
