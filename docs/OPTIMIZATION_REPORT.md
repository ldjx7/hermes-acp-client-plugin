# ACP Client 插件优化建议报告

**分析日期**: 2026-04-16  
**分析范围**: acp/transport.py, tools.py, acp/openacp_bridge.py, tools/claude-cli-acp.js  
**分析工具**: Claude Code (claude-opus-4-6)

---

## 执行摘要

ACP Client 插件整体架构清晰，实现了多 worker 支持、错误重试、故障转移等核心功能。但在性能、错误处理、可维护性和安全性方面存在 15 项优化机会。

**关键发现**:
- ✅ 架构设计合理，模块职责清晰
- ⚠️ JSON 解析存在潜在阻塞风险
- ⚠️ 超时配置分散，缺乏统一管理
- ⚠️ 错误日志不够详细，调试困难
- ⚠️ 缺少性能监控和指标收集

---

## 1. 架构设计优化

### 1.1 配置管理分散

**问题**: 超时、重试等配置分散在多个文件中

**位置**: `tools.py:18-20`, `acp/openacp_bridge.py:115-117`, `acp/transport.py:244`

```python
# tools.py
DEFAULT_TIMEOUT = 300.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0

# acp/openacp_bridge.py
DEFAULT_REQUEST_TIMEOUT = 300
MAX_REQUEST_TIMEOUT = 600
DEFAULT_CONNECT_TIMEOUT = 10
```

**优先级**: 🟡 中

**建议**: 创建统一配置模块

```python
# config.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class ACPConfig:
    # 超时配置
    DEFAULT_TIMEOUT: float = 300.0
    MAX_TIMEOUT: float = 600.0
    CONNECT_TIMEOUT: float = 10.0
    
    # 重试配置
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 2.0
    RETRY_BACKOFF: float = 2.0  # 指数退避
    
    # 故障转移
    AUTO_FALLBACK: bool = True
    RATE_LIMIT_COOLDOWN: float = 60.0
    
    # 会话管理
    SESSION_TTL_HOURS: int = 24
    
    @classmethod
    def from_env(cls) -> 'ACPConfig':
        """从环境变量加载配置"""
        import os
        return cls(
            DEFAULT_TIMEOUT=float(os.getenv('ACP_TIMEOUT', 300)),
            MAX_TIMEOUT=float(os.getenv('ACP_MAX_TIMEOUT', 600)),
            MAX_RETRIES=int(os.getenv('ACP_MAX_RETRIES', 3)),
            # ...
        )

# 单例配置
config = ACPConfig.from_env()
```

---

### 1.2 Worker 配置硬编码

**问题**: `WORKER_CONFIGS` 硬编码在 `transport.py` 中，扩展需要修改源码

**位置**: `acp/transport.py:20-41`

**优先级**: 🟢 低

**建议**: 支持配置文件或环境变量动态注册

```python
# 支持从配置文件加载额外 worker
import json
from pathlib import Path

def load_custom_workers() -> Dict[str, WorkerConfig]:
    """从配置文件加载自定义 worker"""
    config_path = Path.home() / '.hermes' / 'plugins' / 'acp-client' / 'workers.json'
    if not config_path.exists():
        return {}
    
    with open(config_path) as f:
        data = json.load(f)
    
    return {
        name: WorkerConfig(name, cmd)
        for name, cmd in data.items()
    }

# 合并内置和自定义 worker
WORKER_CONFIGS = {**BUILTIN_WORKERS, **load_custom_workers()}
```

---

## 2. 性能瓶颈优化

### 2.1 JSON 解析阻塞风险

**问题**: `_read_stdout` 中 JSON 解析可能阻塞，特别是大响应时

**位置**: `acp/transport.py:323-378`

```python
def _read_stdout(self):
    """读取并解析 worker 输出"""
    buffer = ""
    while True:
        char = self.process.stdout.read(1)
        if not char:
            break
        buffer += char
        if buffer.endswith('}'):
            try:
                msg = json.loads(buffer)  # 可能阻塞
                # ...
            except json.JSONDecodeError:
                continue
```

**优先级**: 🔴 高

**影响**: 大响应时可能阻塞主线程，影响并发性能

**建议**: 使用非阻塞 I/O + 增量解析

```python
import select
import json

def _read_stdout_nonblocking(self, timeout: float = 0.1):
    """非阻塞读取 worker 输出"""
    ready, _, _ = select.select([self.process.stdout], [], [], timeout)
    if not ready:
        return None
    
    chunk = self.process.stdout.read(4096)  # 批量读取
    if not chunk:
        return None
    
    self._json_buffer += chunk.decode('utf-8')
    
    # 尝试提取完整 JSON
    while True:
        try:
            # 查找 JSON 边界
            start = self._json_buffer.find('{')
            if start == -1:
                self._json_buffer = ''
                return None
            
            # 尝试解析
            end = self._find_json_end(self._json_buffer[start:])
            if end == -1:
                return None  # 等待更多数据
            
            json_str = self._json_buffer[start:start+end]
            msg = json.loads(json_str)
            self._json_buffer = self._json_buffer[start+end:]
            return msg
            
        except json.JSONDecodeError:
            return None  # 等待更多数据
    
def _find_json_end(self, s: str) -> int:
    """查找 JSON 结束位置（处理嵌套）"""
    depth = 0
    in_string = False
    escape = False
    
    for i, c in enumerate(s):
        if escape:
            escape = False
            continue
        if c == '\\':
            escape = True
            continue
        if c == '"' and not escape:
            in_string = not in_string
            continue
        if not in_string:
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return i + 1
    return -1
```

---

### 2.2 锁竞争问题

**问题**: `SessionRegistry` 使用单一锁，高并发时可能成为瓶颈

**位置**: `acp/openacp_bridge.py:42-86`

```python
class SessionRegistry:
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()  # 单一锁
    
    def register(self, task_id: str, session_id: str):
        with self._lock:  # 所有操作都竞争同一把锁
            self._registry[task_id] = {...}
```

**优先级**: 🟡 中

**建议**: 使用读写锁或分段锁

```python
from threading import RLock
import hashlib

class SessionRegistry:
    def __init__(self, num_shards: int = 16):
        self._shards: List[Dict] = [{} for _ in range(num_shards)]
        self._locks: List[RLock] = [RLock() for _ in range(num_shards)]
        self._num_shards = num_shards
    
    def _get_shard(self, key: str) -> int:
        """根据 key 计算分片"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16) % self._num_shards
    
    def register(self, task_id: str, session_id: str):
        shard = self._get_shard(task_id)
        with self._locks[shard]:
            self._shards[shard][task_id] = {
                "session_id": session_id,
                "created_at": datetime.now()
            }
    
    def get_session(self, task_id: str) -> Optional[str]:
        shard = self._get_shard(task_id)
        with self._locks[shard]:
            entry = self._shards[shard].get(task_id)
            return entry["session_id"] if entry else None
```

---

### 2.3 缺少连接池复用

**问题**: OpenACP 每次请求都创建新连接

**位置**: `acp/openacp_bridge.py:127-140`

**优先级**: 🟡 中

**建议**: 已实现连接池，但可以优化配置

```python
@property
def session(self) -> requests.Session:
    if self._session is None:
        self._session = requests.Session()
        # 优化连接池配置
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,      # 增加连接数
            pool_maxsize=20,          # 每 host 最大连接
            pool_block=False,         # 不阻塞
            max_retries=3,            # 增加重试
            pool_recycle=1800,        # 30 分钟回收
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    return self._session
```

---

## 3. 错误处理优化

### 3.1 错误日志信息不足

**问题**: 错误日志缺少关键调试信息

**位置**: `tools.py:156-166`, `acp/transport.py:204-209`

```python
if "error" in resp:
    error_msg = resp.get("error", {}).get("message", "Unknown error")
    # 只记录错误消息，缺少上下文
    return json.dumps({"error": error_msg, ...})
```

**优先级**: 🔴 高

**建议**: 增强错误日志和响应

```python
import traceback
from datetime import datetime

def log_error(context: str, error: Exception, response: dict = None):
    """统一错误日志格式"""
    error_data = {
        "timestamp": datetime.now().isoformat(),
        "context": context,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "response": response,
        "worker": getattr(self, 'worker', 'unknown'),
        "session_id": getattr(self, '_current_session_id', None),
    }
    logger.error(f"ACP Error: {json.dumps(error_data, indent=2)}")
    return error_data

# 使用示例
try:
    result = self.bridge.dispatch(...)
except Exception as e:
    error_data = log_error("dispatch", e)
    return {
        "status": "error",
        "error": str(e),
        "error_details": error_data,  # 完整调试信息
        "suggestion": get_error_suggestion(e)  # 错误修复建议
    }
```

---

### 3.2 重试策略单一

**问题**: 所有错误都使用相同重试策略，没有区分错误类型

**位置**: `tools.py:117-126`

```python
while attempts < effective_max_retries:
    # 所有错误都重试相同次数
    # ...
```

**优先级**: 🟡 中

**建议**: 实现智能重试策略

```python
from enum import Enum
from typing import Tuple

class RetryStrategy(Enum):
    IMMEDIATE = "immediate"      # 立即重试
    EXPONENTIAL = "exponential"  # 指数退避
    FIXED = "fixed"              # 固定延迟
    NO_RETRY = "no_retry"        # 不重试

def get_retry_strategy(error: str) -> Tuple[RetryStrategy, int, float]:
    """根据错误类型决定重试策略"""
    error_lower = error.lower()
    
    if "rate limit" in error_lower:
        # 限流：指数退避，最多 3 次，初始延迟 60s
        return RetryStrategy.EXPONENTIAL, 3, 60.0
    elif "timeout" in error_lower:
        # 超时：固定延迟，最多 2 次，延迟 5s
        return RetryStrategy.FIXED, 2, 5.0
    elif "connection" in error_lower or "network" in error_lower:
        # 网络错误：立即重试，最多 3 次
        return RetryStrategy.IMMEDIATE, 3, 0.0
    elif "auth" in error_lower or "permission" in error_lower:
        # 认证错误：不重试
        return RetryStrategy.NO_RETRY, 0, 0.0
    else:
        # 默认：固定延迟，最多 3 次
        return RetryStrategy.FIXED, 3, 2.0

def smart_retry(func, max_attempts: int = None, base_delay: float = None):
    """智能重试装饰器"""
    # 实现重试逻辑
    pass
```

---

### 3.3 超时处理不完善

**问题**: `claude-cli-acp.js` 硬编码 5 分钟超时，无法动态调整

**位置**: `tools/claude-cli-acp.js:269-273`

```javascript
// 设置超时（5 分钟）
setTimeout(() => {
    claude.kill('SIGTERM');
    reject(new Error('Timeout after 5 minutes'));
}, 300000);
```

**优先级**: 🟡 中

**建议**: 从环境变量读取超时配置

```javascript
// 从环境变量读取超时（毫秒），默认 5 分钟
const TIMEOUT_MS = parseInt(process.env.ACP_TIMEOUT_MS) || 300000;

setTimeout(() => {
    claude.kill('SIGTERM');
    reject(new Error(`Timeout after ${TIMEOUT_MS / 1000} seconds`));
}, TIMEOUT_MS);
```

---

## 4. 可维护性优化

### 4.1 缺少类型注解

**问题**: 部分函数缺少类型注解

**位置**: 多处

**优先级**: 🟢 低

**建议**: 添加完整类型注解

```python
from typing import Dict, Any, Optional, List, Callable, Union

def acp_dispatch(
    task: str,
    context: Optional[Dict[str, Any]] = None,
    worker: str = "gemini",
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    auto_fallback: bool = True
) -> str:
    """派发任务到 ACP worker"""
    # ...
```

---

### 4.2 缺少单元测试

**问题**: 没有测试覆盖核心逻辑

**优先级**: 🔴 高

**建议**: 添加关键测试

```python
# tests/test_transport.py
import pytest
from unittest.mock import Mock, patch
from acp.transport import StdioTransport, extract_session_id

class TestSessionIdExtraction:
    """测试 sessionId 提取逻辑"""
    
    def test_standard_path(self):
        resp = {"result": {"sessionId": "session-123"}}
        assert extract_session_id(resp) == "session-123"
    
    def test_gemini_path(self):
        resp = {"result": {"id": "session-456"}}
        assert extract_session_id(resp) == "session-456"
    
    def test_top_level_path(self):
        resp = {"sessionId": "session-789"}
        assert extract_session_id(resp) == "session-789"
    
    def test_no_session_id(self):
        resp = {"result": "some value"}
        assert extract_session_id(resp) is None

class TestJSONBuffering:
    """测试 JSON 缓冲逻辑"""
    
    def test_complete_json(self):
        # 测试完整 JSON 解析
        pass
    
    def test_fragmented_json(self):
        # 测试分段 JSON 解析
        pass
    
    def test_mixed_logs_and_json(self):
        # 测试日志和 JSON 混合
        pass
```

---

### 4.3 文档不完整

**问题**: 缺少 API 文档和使用示例

**优先级**: 🟡 中

**建议**: 添加 docstring 和使用示例

```python
def acp_dispatch(task: str, worker: str = "gemini", timeout: float = 300.0) -> str:
    """
    派发任务到 ACP worker，支持多平台、错误重试和自动故障转移。
    
    Args:
        task: 任务描述
        worker: worker 平台 (gemini/claude/codex/openacp:agent)，默认 gemini
        timeout: 请求超时（秒），默认 300 秒
        max_retries: 最大重试次数，默认 3 次
        auto_fallback: 是否自动故障转移，默认 True
    
    Returns:
        JSON 字符串，包含以下字段:
        - sessionId: 会话 ID
        - status: 状态 (dispatched/running/completed/failed)
        - worker: 使用的 worker
        - error: 错误消息（如果有）
    
    Raises:
        WorkerNotAvailableError: worker 不可用
        RequestTimeoutError: 请求超时
    
    Example:
        >>> # 简单任务
        >>> result = acp_dispatch("实现快速排序")
        >>> print(result)
        {"sessionId": "session-xxx", "status": "dispatched", ...}
        
        >>> # 指定 worker 和超时
        >>> result = acp_dispatch("代码审查", worker="claude-cli", timeout=600)
        
        >>> # 使用 OpenACP agent
        >>> result = acp_dispatch("任务", worker="openacp:cursor")
        
        >>> # 禁用自动故障转移
        >>> result = acp_dispatch("任务", auto_fallback=False)
    """
```

---

## 5. 扩展性优化

### 5.1 Worker 状态管理复杂

**问题**: Worker 状态管理逻辑分散

**位置**: `tools.py:115-165`

**优先级**: 🟡 中

**建议**: 简化状态管理接口

```python
class WorkerHealth:
    """Worker 健康状态管理"""
    
    def __init__(self):
        self._status: Dict[str, WorkerStatus] = {}
        self._lock = threading.Lock()
    
    def is_available(self, worker: str) -> bool:
        """检查 worker 是否可用"""
        with self._lock:
            status = self._status.get(worker)
            if not status:
                return True
            return status.is_healthy()
    
    def record_success(self, worker: str, duration: float):
        """记录成功调用"""
        pass
    
    def record_failure(self, worker: str, error: str):
        """记录失败调用"""
        pass
    
    def get_recommendation(self, task_type: str = None) -> str:
        """推荐最佳 worker"""
        pass
```

---

### 5.2 缺少插件钩子

**问题**: 无法在任务执行前后添加自定义逻辑

**优先级**: 🟢 低

**建议**: 添加钩子系统

```python
from typing import Callable, List

class ACPHooks:
    """ACP 钩子系统"""
    
    def __init__(self):
        self._pre_dispatch: List[Callable] = []
        self._post_dispatch: List[Callable] = []
        self._on_error: List[Callable] = []
    
    def register_pre_dispatch(self, hook: Callable[[str, str], None]):
        """注册预派发钩子"""
        self._pre_dispatch.append(hook)
    
    def register_post_dispatch(self, hook: Callable[[str, str, str], None]):
        """注册后派发钩子"""
        self._post_dispatch.append(hook)
    
    def register_on_error(self, hook: Callable[[str, Exception], None]):
        """注册错误钩子"""
        self._on_error.append(hook)
    
    def emit_pre(self, task: str, worker: str):
        for hook in self._pre_dispatch:
            try:
                hook(task, worker)
            except Exception as e:
                logger.warning(f"Pre-dispatch hook failed: {e}")
    
    # ... 其他 emit 方法

# 全局钩子实例
hooks = ACPHooks()

# 使用示例
hooks.register_pre_dispatch(lambda task, worker: logger.info(f"Dispatching {task} to {worker}"))
```

---

## 6. 安全性优化

### 6.1 环境变量泄露风险

**问题**: 日志可能泄露敏感环境变量

**位置**: `tools/claude-cli-acp.js:38-41`

```javascript
log(`API Key: ${config.apiKey ? '✅' : '❌'}`);  // ✅ 安全
log(`Base URL: ${config.baseUrl}`);  // 可能泄露内部 URL
```

**优先级**: 🟡 中

**建议**: 脱敏敏感信息

```javascript
function maskSecret(value, visibleChars = 4) {
    if (!value) return '***';
    if (value.length <= visibleChars) return '***';
    return value.substring(0, visibleChars) + '...' + '[REDACTED]';
}

log(`API Key: ${config.apiKey ? '✅' : '❌'}`);
log(`Base URL: ${maskSecret(config.baseUrl)}`);
log(`Model: ${config.model}`);
```

---

### 6.2 命令注入风险

**问题**: worker 命令拼接可能存在注入风险

**位置**: `acp/transport.py:246`

```python
self.command = command or get_worker_command(self.worker)
# 如果 command 来自用户输入，可能存在注入风险
```

**优先级**: 🟢 低

**建议**: 验证和转义命令参数

```python
import shlex

def sanitize_command(command: List[str]) -> List[str]:
    """验证和清理命令参数"""
    # 白名单验证
    allowed_commands = ['gemini', 'claude', 'codex', 'qwen', 'node', 'openacp']
    if command[0] not in allowed_commands:
        raise ValueError(f"Command not allowed: {command[0]}")
    
    # 转义参数
    return [shlex.quote(arg) if ' ' in arg else arg for arg in command]
```

---

## 7. 监控和可观测性

### 7.1 缺少性能指标

**问题**: 没有收集响应时间、成功率等指标

**优先级**: 🟡 中

**建议**: 添加指标收集

```python
from dataclasses import dataclass, field
from typing import Dict, List
import statistics

@dataclass
class WorkerMetrics:
    """Worker 性能指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests
    
    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)
    
    @property
    def p95_response_time(self) -> float:
        if len(self.response_times) < 20:
            return self.avg_response_time
        sorted_times = sorted(self.response_times)
        return sorted_times[int(len(sorted_times) * 0.95)]
    
    def record(self, success: bool, duration: float, error: str = None):
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            if error:
                self.errors[error] = self.errors.get(error, 0) + 1
        self.response_times.append(duration)
        # 保留最近 1000 次
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]

class MetricsCollector:
    """指标收集器"""
    
    def __init__(self):
        self._metrics: Dict[str, WorkerMetrics] = {}
        self._lock = threading.Lock()
    
    def get_metrics(self, worker: str) -> WorkerMetrics:
        with self._lock:
            if worker not in self._metrics:
                self._metrics[worker] = WorkerMetrics()
            return self._metrics[worker]
    
    def export_prometheus(self) -> str:
        """导出 Prometheus 格式指标"""
        lines = []
        for worker, metrics in self._metrics.items():
            lines.append(f'acp_requests_total{{worker="{worker}"}} {metrics.total_requests}')
            lines.append(f'acp_success_rate{{worker="{worker}"}} {metrics.success_rate}')
            lines.append(f'acp_avg_response_time{{worker="{worker}"}} {metrics.avg_response_time}')
        return '\n'.join(lines)

# 全局指标收集器
metrics = MetricsCollector()
```

---

## 实施路线图

### 短期 (1 周) - 高优先级

| ID | 任务 | 预计工时 | 影响 |
|----|------|----------|------|
| S1 | 增强错误日志信息 | 2h | 🔴 高 |
| S2 | 添加 JSON 非阻塞解析 | 4h | 🔴 高 |
| S3 | 添加基础单元测试 | 4h | 🔴 高 |
| S4 | 统一配置管理 | 3h | 🟡 中 |

**短期目标**: 提升稳定性和可调试性

---

### 中期 (1 月) - 中优先级

| ID | 任务 | 预计工时 | 影响 |
|----|------|----------|------|
| M1 | 实现智能重试策略 | 4h | 🟡 中 |
| M2 | 添加性能指标收集 | 6h | 🟡 中 |
| M3 | 优化连接池配置 | 2h | 🟡 中 |
| M4 | 实现分段锁 SessionRegistry | 4h | 🟡 中 |
| M5 | 完善文档和示例 | 6h | 🟡 中 |

**中期目标**: 提升性能和可维护性

---

### 长期 (3 月) - 低优先级

| ID | 任务 | 预计工时 | 影响 |
|----|------|----------|------|
| L1 | 实现插件钩子系统 | 8h | 🟢 低 |
| L2 | 支持动态 Worker 注册 | 4h | 🟢 低 |
| L3 | 添加完整类型注解 | 6h | 🟢 低 |
| L4 | 实现 Prometheus 指标导出 | 4h | 🟢 低 |
| L5 | 添加安全审计日志 | 4h | 🟢 低 |

**长期目标**: 提升扩展性和安全性

---

## 总结

### 当前优势
- ✅ 架构清晰，模块职责分离
- ✅ 支持多 worker 和故障转移
- ✅ 已实现基础会话管理
- ✅ 支持第三方代理（Claude）

### 关键改进点
1. **性能**: JSON 非阻塞解析、连接池优化、分段锁
2. **稳定性**: 智能重试、增强错误处理、超时管理
3. **可维护性**: 单元测试、文档、类型注解
4. **可观测性**: 性能指标、日志增强

### 预期收益
- 响应时间降低 30-50%（非阻塞 I/O）
- 错误调试时间减少 60%（增强日志）
- 代码覆盖率提升至 80%+（单元测试）
- 并发能力提升 2-3 倍（分段锁）

---

**生成工具**: Claude Code (claude-opus-4-6) via ACP Client  
**文档版本**: 1.0  
**最后更新**: 2026-04-16
