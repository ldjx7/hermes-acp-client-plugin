# Worker 故障转移指南

> **自动切换可用模型，避免速率限制和错误**

---

## 📖 概述

ACP Client Plugin 支持**自动故障转移**功能，当检测到以下情况时会自动切换到其他可用的 Worker：

- ⚠️ **速率限制** (Rate Limit)
- ❌ **认证错误**
- 🔌 **Worker 离线**
- ⏱️ **超时错误**

---

## 🚀 快速开始

### 基本使用

```python
# 默认启用自动故障转移
/acp_dispatch --task "写一个 Python 函数" --worker gemini
```

如果 Gemini 速率受限，会自动尝试 Claude → Codex → Qwen

### 禁用故障转移

```python
# 强制使用特定 Worker
/acp_dispatch --task "写一个 Python 函数" --worker gemini --auto_fallback false
```

---

## 📊 Worker 状态

### 查询所有 Worker 状态

```python
/acp_worker_status
```

**返回示例：**

```json
{
  "total_workers": 4,
  "available": 3,
  "rate_limited": 1,
  "offline": 0,
  "recommended_worker": "claude",
  "workers": {
    "gemini": {
      "name": "gemini",
      "status": "rate_limited",
      "model": "gemini-2.5-flash",
      "success_rate": 95.2,
      "avg_response_time": 28.78,
      "rate_limit_reset": "2026-04-14T12:15:00"
    },
    "claude": {
      "name": "claude",
      "status": "available",
      "model": "claude-sonnet-4",
      "success_rate": 98.5,
      "avg_response_time": 15.32
    },
    "codex": {
      "name": "codex",
      "status": "available",
      "model": "codex-1",
      "success_rate": 92.1,
      "avg_response_time": 45.67
    },
    "qwen": {
      "name": "qwen",
      "status": "available",
      "model": "qwen3.5-plus",
      "success_rate": 85.0,
      "avg_response_time": 120.45
    }
  }
}
```

---

## 🔍 Worker 状态说明

| 状态 | 说明 | 行为 |
|------|------|------|
| `available` | 可用 | 正常派发任务 |
| `rate_limited` | 速率限制 | 跳过，直到冷却时间结束 |
| `error` | 错误 | 跳过，等待手动恢复 |
| `offline` | 离线 | 跳过，无法使用 |

---

## ⚙️ 自动故障转移逻辑

### 1. 速率限制检测

系统会检测以下错误关键词：

```python
rate_limit_indicators = [
    "rate limit",
    "too many requests",
    "quota exceeded",
    "resource exhausted",
    "429",
    "throttl",
]
```

### 2. 故障转移流程

```
任务派发 → 首选 Worker (Gemini)
           ↓
      速率限制错误
           ↓
   标记为 rate_limited
           ↓
   选择下一个可用 Worker (Claude)
           ↓
      成功派发 ✅
```

### 3. 冷却时间

- **默认冷却**: 60 秒
- **可配置**: `worker_manager._rate_limit_cooldown`

冷却时间后，Worker 状态自动恢复为 `available`

---

## 📈 使用场景

### 场景 1: 高频调用避免速率限制

```python
# 批量处理多个任务
for i in range(10):
    result = acp_dispatch(
        task=f"处理任务 {i}",
        auto_fallback=True  # 自动切换到可用 Worker
    )
```

### 场景 2: 关键任务确保成功

```python
# 重要任务，允许最多 5 次重试
result = acp_dispatch(
    task="关键业务逻辑",
    max_retries=5,
    timeout=300
)
```

### 场景 3: 优先使用特定模型

```python
# 优先使用 Claude，失败则 fallback
result = acp_dispatch(
    task="复杂代码审查",
    worker="claude",  # 首选
    auto_fallback=True  # 失败则切换
)
```

---

## 🛠️ 配置选项

### 修改默认 Worker 顺序

编辑 `acp/worker_manager.py`:

```python
self._fallback_order = ["gemini", "claude", "codex", "qwen"]
# 改为：
self._fallback_order = ["claude", "gemini", "codex", "qwen"]
```

### 修改冷却时间

```python
self._rate_limit_cooldown = 120  # 120 秒
```

### 添加自定义 Worker

```python
# 在 WORKER_CONFIGS 中添加
WORKER_CONFIGS = {
    "gemini": WorkerConfig("gemini", ["gemini", "--acp"]),
    "custom": WorkerConfig("custom", ["custom-cli", "--acp"]),
}
```

---

## 📊 监控和日志

### 日志输出

```
INFO: Attempting dispatch to gemini (attempt 1/3)
WARNING: Rate limit on gemini, trying next worker...
INFO: Attempting dispatch to claude (attempt 2/3)
INFO: Dispatched task to session abc123 on claude
```

### 查询历史统计

```python
# 获取 Worker 管理器
from acp.worker_manager import get_worker_manager

manager = get_worker_manager()
summary = manager.get_status_summary()

print(f"总请求数：{manager._workers['gemini'].total_requests}")
print(f"失败请求数：{manager._workers['gemini'].failed_requests}")
print(f"成功率：{(1 - manager._workers['gemini'].failed_requests / manager._workers['gemini'].total_requests) * 100}%")
```

---

## 🎯 最佳实践

### 1. 启用自动故障转移（推荐）

```python
# 默认就是 True，建议保持
acp_dispatch(task="...", auto_fallback=True)
```

### 2. 设置合理的超时

```python
# Gemini/Claude: 90-120 秒
# Qwen: 300 秒+
acp_dispatch(task="...", worker="qwen", timeout=300)
```

### 3. 定期检查 Worker 状态

```python
# 在批量任务前检查
status = acp_worker_status()
# 选择推荐的 Worker
```

### 4. 监控成功率

```python
# 如果某个 Worker 成功率持续低于 80%，考虑调整顺序
manager = get_worker_manager()
for name, info in manager.get_all_workers().items():
    if info["success_rate"] < 80:
        print(f"警告：{name} 成功率过低")
```

---

## 🔧 故障排除

### 问题 1: 所有 Worker 都不可用

**原因**: 全部速率限制或离线

**解决**:
```python
# 检查状态
status = acp_worker_status()

# 等待冷却时间
# 或手动重置
manager = get_worker_manager()
for worker in manager._workers.values():
    worker.status = WorkerStatus.AVAILABLE
```

### 问题 2: 故障转移不生效

**检查**:
1. `auto_fallback=True` 是否设置
2. 错误是否被正确识别为速率限制
3. Worker 管理器是否初始化

**调试**:
```python
from acp.worker_manager import get_worker_manager

manager = get_worker_manager()
print(manager.get_status_summary())
```

### 问题 3: 模型信息未更新

**原因**: ACP 响应中缺少 `_meta.model_usage`

**解决**: 检查 Worker 的 ACP 协议兼容性

---

## 📝 API 参考

### WorkerManager 类

```python
class WorkerManager:
    def register_worker(name: str, model: str = None)
    def get_available_worker(exclude: List[str] = None) -> Optional[str]
    def mark_success(worker: str, response_time: float, model: str = None)
    def mark_error(worker: str, error: str, is_rate_limit: bool = False)
    def mark_offline(worker: str)
    def get_worker_info(worker: str) -> Optional[Dict]
    def get_all_workers() -> Dict[str, Dict]
    def get_status_summary() -> Dict
    def is_rate_limit_error(error_message: str) -> bool
```

### 工具函数

```python
def get_worker_manager() -> WorkerManager
def initialize_workers()
def get_worker_status() -> str
```

---

**最后更新**: 2026-04-14  
**版本**: 1.0.0
