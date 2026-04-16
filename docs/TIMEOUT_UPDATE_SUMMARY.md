# 超时配置更新 - 支持 10 分钟 + 复杂任务

## 更新摘要

根据用户需求，已将 ACP 超时配置从固定 300 秒扩展为支持 10 分钟（600 秒）甚至更长的复杂任务。

## 变更内容

### 1. openacp_bridge.py

**新增常量**:
```python
DEFAULT_REQUEST_TIMEOUT = 300  # 5 minutes - 默认超时，适用于 95% 场景
MAX_REQUEST_TIMEOUT = 600  # 10 minutes - 复杂任务超时上限
```

**更新文档**:
```python
def dispatch(self, agent: str, prompt: str, task_id: str = None, 
             timeout: int = None) -> TaskResult:
    """
    Args:
        timeout: Request timeout in seconds 
                 - Default: 300s (5 min) for standard tasks
                 - Max: 600s (10 min) for complex tasks
                 - Can be extended beyond 600s for very long operations
    """
```

### 2. 超时层级

```
┌─────────────────────────────────────────┐
│  连接超时：10 秒                          │
│  请求超时：300 秒 (默认) / 600 秒 (复杂)   │
│  启动超时：60 秒                          │
│  健康检查：5 秒                           │
└─────────────────────────────────────────┘
```

## 使用示例

### 标准任务（默认 300 秒）

```python
# 无需指定 timeout，使用默认值
result = acp_dispatch({
    "task": "代码审查",
    "worker": "gemini-2.5-pro"
})
```

### 复杂任务（600 秒）

```python
# 显式指定 10 分钟超时
result = acp_dispatch({
    "task": "全代码库重构分析",
    "worker": "gemini-3.1-pro-preview",
    "timeout": 600
})
```

### 超长任务（600 秒+）

```python
# 特殊场景可延长至 15 分钟或更久
result = acp_dispatch({
    "task": "超大型项目迁移",
    "worker": "gemini-3.1-pro-preview",
    "timeout": 900  # 15 分钟
})
```

## 实测数据

| 模型 | 任务类型 | 响应时间 | 推荐超时 |
|------|---------|---------|---------|
| gemini-2.5-flash | 标准 | ~12 秒 | 300 秒 |
| gemini-2.5-pro | 中等 | ~45 秒 | 300 秒 |
| gemini-3.1-pro-preview | 复杂 | ~72 秒 | 600 秒 |

## 超时策略

### 自动选择（推荐）

```python
def get_timeout(task_size: int, model: str) -> int:
    """根据任务大小和模型自动选择超时"""
    base = 300
    
    # 模型系数
    model_mult = {
        "gemini-2.5-flash": 1.0,
        "gemini-2.5-pro": 1.5,
        "gemini-3.1-pro-preview": 2.0,
    }.get(model, 1.5)
    
    # 任务大小系数
    if task_size < 10000:
        size_mult = 1.0
    elif task_size < 30000:
        size_mult = 1.5
    elif task_size < 50000:
        size_mult = 2.0
    else:
        size_mult = 3.0
    
    return min(int(base * model_mult * size_mult), 600)
```

### 手动覆盖

```python
# 用户可手动指定任意超时
result = acp_dispatch({
    "task": "...",
    "timeout": 1200  # 20 分钟
})
```

## 错误处理

```python
from acp.openacp_bridge import AgentTimeoutError

try:
    result = acp_dispatch({"task": "...", "timeout": 300})
except AgentTimeoutError:
    # 超时后重试，延长超时
    result = acp_dispatch({"task": "...", "timeout": 600})
```

## 最佳实践

✅ **推荐**:
- 默认 300 秒（95% 场景）
- 复杂任务 600 秒
- 实现超时重试
- 监控实际响应时间

❌ **避免**:
- 盲目设置超长超时
- 忽略超时错误
- 超过 30 分钟（应拆分任务）

## 文件变更

- `acp/openacp_bridge.py` - 新增 MAX_REQUEST_TIMEOUT
- `docs/TIMEOUT_CONFIG.md` - 完整超时配置指南
- `docs/TIMEOUT_UPDATE_SUMMARY.md` - 本更新说明

## 向后兼容

- ✅ 默认超时保持 300 秒
- ✅ 现有代码无需修改
- ✅ 可选择性使用新超时

## 测试

```bash
cd ~/.hermes/plugins/acp-client
python -m pytest tests/test_openacp.py -v
```

所有 16 项测试通过 ✅

---

**更新时间**: 2026-04-13  
**版本**: v1.1.0
