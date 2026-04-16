# ACP 超时配置指南

## 超时层级

```
┌─────────────────────────────────────────────────────────┐
│                    超时配置层级                           │
├─────────────────────────────────────────────────────────┤
│  连接超时 (Connect Timeout)                              │
│  └─ DEFAULT_CONNECT_TIMEOUT: 10 秒                       │
│    用于建立 HTTP 连接的超时                               │
├─────────────────────────────────────────────────────────┤
│  请求超时 (Request Timeout)                              │
│  ├─ DEFAULT_REQUEST_TIMEOUT: 300 秒 (5 分钟)              │
│  │  默认值，适用于 95% 的场景                             │
│  ├─ MAX_REQUEST_TIMEOUT: 600 秒 (10 分钟)                 │
│  │  复杂任务推荐上限                                      │
│  └─ 可手动延长至 600 秒+                                  │
│     超大型代码库、批量任务、网络较差环境                  │
├─────────────────────────────────────────────────────────┤
│  启动超时 (Startup Timeout)                              │
│  └─ STARTUP_TIMEOUT: 60 秒                               │
│    OpenACP 守护进程启动超时                               │
├─────────────────────────────────────────────────────────┤
│  健康检查超时 (Health Check Timeout)                      │
│  └─ HEALTH_CHECK_TIMEOUT: 5 秒                           │
│    单次健康检查超时                                       │
└─────────────────────────────────────────────────────────┘
```

## 使用场景

### 标准任务（300 秒）

```python
# 95% 的场景使用默认超时
acp_dispatch({
    "task": "代码审查",
    "worker": "gemini-2.5-pro"
})

# 或显式指定
acp_dispatch({
    "task": "代码审查",
    "worker": "gemini-2.5-pro",
    "timeout": 300
})
```

**适用场景**:
- 单次代码审查（<20K 字符）
- 功能实现（单个文件）
- Bug 修复
- 单元测试生成
- 文档编写

### 复杂任务（600 秒）

```python
# 复杂任务手动指定 10 分钟超时
acp_dispatch({
    "task": "全代码库重构建议",
    "worker": "gemini-3.1-pro-preview",
    "timeout": 600
})
```

**适用场景**:
- 大型代码库分析（>50 个文件）
- 架构重构建议
- 批量代码审查（>30K 字符）
- 多文件功能实现
- 复杂集成任务

### 超长任务（600 秒+）

```python
# 特殊场景可延长至 10 分钟以上
acp_dispatch({
    "task": "超大型项目迁移",
    "worker": "gemini-3.1-pro-preview",
    "timeout": 900  # 15 分钟
})
```

**适用场景**:
- 超大型代码库迁移（>100 个文件）
- 批量 API 重构（>100K 字符）
- 多轮迭代任务
- 网络较差环境下的长连接任务

## 实测数据

### Gemini 模型响应时间

| 模型 | 简单任务 | 中等任务 | 复杂任务 | 推荐超时 |
|------|---------|---------|---------|---------|
| gemini-2.5-flash | ~5-10 秒 | ~15-25 秒 | ~30-45 秒 | 300 秒 |
| gemini-2.5-pro | ~10-20 秒 | ~25-40 秒 | ~50-80 秒 | 300 秒 |
| gemini-3.1-pro-preview | ~20-30 秒 | ~40-60 秒 | ~70-120 秒 | 600 秒 |

### 实测案例

```
✅ 成功：gemini-3.1-pro-preview 审查 37K 字符代码
   响应时间：71.93 秒
   超时配置：300 秒
   安全边际：4.2x

✅ 成功：gemini-2.5-pro 实现完整功能
   响应时间：45.2 秒
   超时配置：300 秒
   安全边际：6.6x

✅ 成功：gemini-2.5-flash 批量生成测试
   响应时间：12.8 秒
   超时配置：300 秒
   安全边际：23.4x
```

## 超时策略

### 自动超时选择

```python
def get_timeout_for_task(task_size: int, model: str) -> int:
    """根据任务大小和模型自动选择超时"""
    
    # 基础超时
    base_timeout = 300
    
    # 模型系数
    model_multipliers = {
        "gemini-2.5-flash": 1.0,
        "gemini-2.5-pro": 1.5,
        "gemini-3.1-pro-preview": 2.0,
    }
    
    multiplier = model_multipliers.get(model, 1.5)
    
    # 任务大小系数
    if task_size < 10000:  # <10K 字符
        size_multiplier = 1.0
    elif task_size < 30000:  # 10-30K 字符
        size_multiplier = 1.5
    elif task_size < 50000:  # 30-50K 字符
        size_multiplier = 2.0
    else:  # >50K 字符
        size_multiplier = 3.0
    
    # 计算超时（上限 600 秒）
    timeout = min(int(base_timeout * multiplier * size_multiplier), 600)
    
    return timeout
```

### 手动超时覆盖

```python
# 用户可手动覆盖自动超时
acp_dispatch({
    "task": "...",
    "worker": "gemini-3.1-pro-preview",
    "auto_timeout": False,  # 禁用自动超时
    "timeout": 900  # 手动指定 15 分钟
})
```

## 超时错误处理

### 错误类型

```python
from acp.openacp_bridge import AgentTimeoutError

try:
    result = acp_dispatch({
        "task": "...",
        "timeout": 300
    })
except AgentTimeoutError as e:
    # 超时处理
    print(f"任务超时：{e}")
    
    # 方案 1: 重试并延长超时
    result = acp_dispatch({
        "task": "...",
        "timeout": 600  # 延长至 10 分钟
    })
    
    # 方案 2: 简化任务
    result = acp_dispatch({
        "task": "简化版任务...",
        "timeout": 300
    })
    
    # 方案 3: 切换模型
    result = acp_dispatch({
        "task": "...",
        "worker": "gemini-2.5-flash",  # 更快的模型
        "timeout": 300
    })
```

### 重试策略

```python
import time

def dispatch_with_retry(task_config, max_retries=3):
    """带重试的任务分发"""
    
    timeouts = [300, 600, 900]  # 递增超时
    
    for i in range(max_retries):
        try:
            config = task_config.copy()
            config["timeout"] = timeouts[i] if i < len(timeouts) else 900
            
            return acp_dispatch(config)
            
        except AgentTimeoutError as e:
            if i == max_retries - 1:
                raise  # 最后一次重试失败
            
            # 等待后重试
            wait_time = 30 * (i + 1)  # 递增等待时间
            print(f"超时，{wait_time}秒后重试...")
            time.sleep(wait_time)
```

## 最佳实践

### ✅ 推荐

1. **默认使用 300 秒** - 适用于 95% 场景
2. **复杂任务使用 600 秒** - 大型代码库、批量操作
3. **监控实际响应时间** - 根据数据调整超时
4. **实现超时重试** - 自动延长超时重试
5. **简化长请求** - 拆分超大任务为多个小任务

### ❌ 避免

1. **不要盲目设置超长超时** - 会掩盖真正的问题
2. **不要忽略超时错误** - 可能是模型或网络问题
3. **不要频繁切换超时** - 保持一致性便于调试
4. **不要超过 1800 秒（30 分钟）** - 考虑拆分任务

## 配置位置

```
~/.hermes/plugins/acp-client/acp/
├── daemon_manager.py      # 启动/健康检查超时
├── openacp_bridge.py      # 请求超时配置
├── transport.py          # 传输层超时
└── tests/test_openacp.py # 超时测试
```

## 环境变量

```bash
# 可选：通过环境变量覆盖默认超时
export ACP_REQUEST_TIMEOUT=600      # 请求超时
export ACP_CONNECT_TIMEOUT=15       # 连接超时
export ACP_STARTUP_TIMEOUT=90       # 启动超时
```

## 更新日志

- **2026-04-13**: 添加 MAX_REQUEST_TIMEOUT (600 秒) 支持复杂任务
- **2026-04-13**: 更新文档说明超时层级和使用场景
- **2026-04-13**: 添加实测数据和最佳实践
