# ACP 流式心跳超时机制设计方案

**问题**: 当前固定超时机制不合理，复杂任务容易超时，且无法判断 Agent 是否还在工作

**日期**: 2026-04-16

---

## 1. 问题分析

### 1.1 当前实现的问题

```python
# tools.py:send() - 当前实现
def send(self, message: ACPMessage, timeout: float = None) -> Optional[Dict]:
    timeout = timeout or self.request_timeout  # 固定 300 秒
    msg_id = str(message.id)
    q = queue.Queue()
    self._pending[msg_id] = q
    
    try:
        return self._send_with_retry(message, msg_id, q, timeout)
    except RequestTimeoutError:
        # ❌ 问题：从发送开始就计时，不管 Agent 是否有输出
        # ❌ 复杂任务（如代码审查、项目分析）可能需要 10+ 分钟
        raise
```

**问题场景**:
1. **复杂代码审查**: Agent 需要读取多个文件，分析 5 分钟后才开始输出
2. **项目重构**: Agent 工作 8 分钟，输出 3 分钟，总 11 分钟 > 300 秒超时
3. **数据分析**: Agent 处理大数据集，中间沉默 3 分钟，但实际在工作

### 1.2 ACP 协议已支持流式通知

```javascript
// claude-cli-acp.js:169-185
// Agent 会持续发送 session/state 通知
sendNotification('session/state', {
    sessionId: sid,
    state: 'running',      // ← 开始处理
    progress: 0.3,         // ← 进度
    message: 'Analyzing...'
});

// 每有进展就发送
sendNotification('session/state', {
    sessionId: sid,
    state: 'running',
    progress: 0.6,
    message: 'Generating code...'
});

// 完成
sendNotification('session/state', {
    sessionId: sid,
    state: 'completed',    // ← 完成
    result: '...'
});
```

**关键发现**: ACP 协议已经支持流式进度通知，但当前实现没有充分利用！

---

## 2. 解决方案：心跳超时机制

### 2.1 核心思路

```
┌─────────────────────────────────────────────────────────────┐
│  传统超时 vs 心跳超时                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  传统超时:                                                   │
│  ├─ 发送请求 ────────────────────× (300s 超时)              │
│  │   (Agent 可能还在工作，但被强制终止)                      │
│                                                              │
│  心跳超时:                                                   │
│  ├─ 发送请求                                                │
│  │   ├─ 收到 running (心跳重置) ✓                           │
│  │   ├─ 收到 progress 0.3 (心跳重置) ✓                      │
│  │   ├─ 收到 progress 0.6 (心跳重置) ✓                      │
│  │   ├─ ... (沉默 45s)                                      │
│  │   └─ × 心跳超时 (无活动 60s)                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 设计参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FIRST_RESPONSE_TIMEOUT` | 30s | 首次响应超时（检测 Agent 是否启动） |
| `HEARTBEAT_TIMEOUT` | 60s | 心跳超时（无活动多久判定失败） |
| `MAX_TOTAL_TIME` | 1800s | 最大总时间（30 分钟，防止无限运行） |
| `PROGRESS_THRESHOLD` | 0.01 | 最小进度变化（<1% 也视为有效心跳） |

---

## 3. 实现方案

### 3.1 心跳监控器

```python
# acp/heartbeat_monitor.py
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

@dataclass
class HeartbeatState:
    """心跳状态"""
    request_id: str
    session_id: str
    first_response_received: bool = False
    last_heartbeat: datetime = field(default_factory=datetime.now)
    last_progress: float = 0.0
    current_state: str = "pending"  # pending/running/completed/failed
    progress_message: str = ""
    
    def reset_heartbeat(self):
        """重置心跳计时器"""
        self.last_heartbeat = datetime.now()
    
    def time_since_heartbeat(self) -> float:
        """距离上次心跳的秒数"""
        return (datetime.now() - self.last_heartbeat).total_seconds()
    
    def total_elapsed(self, start_time: datetime) -> float:
        """总耗时"""
        return (datetime.now() - start_time).total_seconds()


class HeartbeatMonitor:
    """
    心跳监控器
    
    监控 ACP 请求的生命周期，基于活动而非固定时间判定超时。
    
    超时策略:
    1. 首次响应超时: 30s 内必须收到第一个 running 状态
    2. 心跳超时: 60s 无活动判定失败
    3. 最大总时间: 1800s (30 分钟) 强制终止
    """
    
    def __init__(
        self,
        first_response_timeout: float = 30.0,
        heartbeat_timeout: float = 60.0,
        max_total_time: float = 1800.0,
        progress_threshold: float = 0.01
    ):
        self.first_response_timeout = first_response_timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.max_total_time = max_total_time
        self.progress_threshold = progress_threshold
        
        self._states: Dict[str, HeartbeatState] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动监控线程"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Heartbeat monitor started")
    
    def stop(self):
        """停止监控"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
        logger.info("Heartbeat monitor stopped")
    
    def register_request(
        self,
        request_id: str,
        session_id: str,
        on_timeout: Callable[[str], None],
        on_progress: Optional[Callable[[str, float, str], None]] = None
    ):
        """
        注册新请求进行监控
        
        Args:
            request_id: 请求 ID
            session_id: 会话 ID
            on_timeout: 超时时回调
            on_progress: 进度更新回调
        """
        with self._lock:
            self._states[request_id] = HeartbeatState(
                request_id=request_id,
                session_id=session_id,
                last_heartbeat=datetime.now()
            )
            self._callbacks[request_id] = {
                'on_timeout': on_timeout,
                'on_progress': on_progress
            }
        logger.debug(f"Registered request {request_id} for heartbeat monitoring")
    
    def heartbeat(self, request_id: str, state: str, progress: float = None, message: str = ""):
        """
        收到心跳（ACP 通知）
        
        Args:
            request_id: 请求 ID
            state: 状态 (running/completed/failed)
            progress: 进度 (0.0-1.0)
            message: 进度消息
        """
        with self._lock:
            if request_id not in self._states:
                return
            
            hb_state = self._states[request_id]
            callbacks = self._callbacks.get(request_id, {})
            
            # 记录首次响应
            if not hb_state.first_response_received and state == "running":
                hb_state.first_response_received = True
                elapsed = hb_state.total_elapsed(hb_state.last_heartbeat)
                logger.info(f"Request {request_id}: First response in {elapsed:.2f}s")
            
            # 检查进度变化（视为有效心跳）
            progress_changed = False
            if progress is not None:
                progress_changed = abs(progress - hb_state.last_progress) > self.progress_threshold
                hb_state.last_progress = progress
            
            # 状态变化也视为心跳
            state_changed = state != hb_state.current_state
            hb_state.current_state = state
            hb_state.progress_message = message
            
            # 重置心跳计时器
            if progress_changed or state_changed or state in ("running", "completed", "failed"):
                old_elapsed = hb_state.time_since_heartbeat()
                hb_state.reset_heartbeat()
                logger.debug(
                    f"Heartbeat reset for {request_id}: "
                    f"state={state}, progress={progress}, message={message}, "
                    f"was silent for {old_elapsed:.1f}s"
                )
                
                # 调用进度回调
                if progress is not None and callbacks.get('on_progress'):
                    try:
                        callbacks['on_progress'](request_id, progress, message)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")
            
            # 完成或失败，清理
            if state in ("completed", "failed"):
                self._cleanup_request(request_id)
    
    def _cleanup_request(self, request_id: str):
        """清理已完成的请求"""
        with self._lock:
            self._states.pop(request_id, None)
            self._callbacks.pop(request_id, None)
        logger.debug(f"Cleaned up completed request {request_id}")
    
    def _monitor_loop(self):
        """监控循环（后台线程）"""
        while self._running:
            time.sleep(1)  # 每秒检查一次
            
            now = datetime.now()
            timeouts = []
            
            with self._lock:
                for request_id, state in list(self._states.items()):
                    callbacks = self._callbacks.get(request_id, {})
                    
                    # 检查首次响应超时
                    if not state.first_response_received:
                        elapsed = state.total_elapsed(state.last_heartbeat)
                        if elapsed > self.first_response_timeout:
                            timeouts.append((
                                request_id,
                                "first_response",
                                f"No response in {elapsed:.1f}s"
                            ))
                            continue
                    
                    # 检查心跳超时
                    silence = state.time_since_heartbeat()
                    if silence > self.heartbeat_timeout:
                        timeouts.append((
                            request_id,
                            "heartbeat",
                            f"No activity for {silence:.1f}s"
                        ))
                        continue
                    
                    # 检查最大总时间
                    total = state.total_elapsed(state.last_heartbeat)
                    if total > self.max_total_time:
                        timeouts.append((
                            request_id,
                            "max_total",
                            f"Exceeded max time {total:.1f}s"
                        ))
                        continue
            
            # 处理超时
            for request_id, timeout_type, message in timeouts:
                logger.warning(f"Timeout [{timeout_type}] for {request_id}: {message}")
                with self._lock:
                    callbacks = self._callbacks.get(request_id, {})
                if callbacks.get('on_timeout'):
                    try:
                        callbacks['on_timeout'](f"{timeout_type}: {message}")
                    except Exception as e:
                        logger.error(f"Timeout callback error: {e}")
                self._cleanup_request(request_id)
    
    def get_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """获取请求状态"""
        with self._lock:
            if request_id not in self._states:
                return None
            
            state = self._states[request_id]
            return {
                "request_id": request_id,
                "session_id": state.session_id,
                "first_response": state.first_response_received,
                "current_state": state.current_state,
                "last_progress": state.last_progress,
                "progress_message": state.progress_message,
                "silence_seconds": state.time_since_heartbeat(),
                "status": "healthy" if state.time_since_heartbeat() < self.heartbeat_timeout / 2 else "warning"
            }


# 全局监控器实例
heartbeat_monitor = HeartbeatMonitor()
```

---

### 3.2 集成到 Transport 层

```python
# acp/transport.py - 修改 StdioTransport 类

from .heartbeat_monitor import heartbeat_monitor, HeartbeatMonitor

class StdioTransport:
    def __init__(
        self,
        command: list = None,
        worker: str = "gemini",
        max_retries: int = 3,
        retry_delay: float = 2.0,
        request_timeout: float = 300.0,
        # 新增心跳参数
        heartbeat_timeout: float = 60.0,
        first_response_timeout: float = 30.0,
        max_total_time: float = 1800.0
    ):
        # ... 现有初始化代码 ...
        
        # 心跳配置
        self.heartbeat_timeout = heartbeat_timeout
        self.first_response_timeout = first_response_timeout
        self.max_total_time = max_total_time
        
        # 确保监控器运行
        heartbeat_monitor.start()
    
    def send_prompt(self, session_id: str, prompt: str) -> Optional[Dict]:
        """发送提示并启用心跳监控"""
        req = PromptRequest.create(session_id=session_id, prompt=prompt)
        
        # 生成请求 ID
        request_id = str(req.id)
        
        # 创建完成事件（用于等待结果）
        import threading
        result_event = threading.Event()
        result_data = {}
        
        def on_timeout(reason: str):
            result_data['error'] = f"Heartbeat timeout: {reason}"
            result_data['status'] = 'failed'
            result_event.set()
        
        def on_progress(request_id: str, progress: float, message: str):
            logger.info(f"Progress: {progress*100:.1f}% - {message}")
            # 可选：实时更新会话状态
            manager = get_session_manager()
            manager.update_session(
                session_id,
                progress=progress,
                progress_message=message
            )
        
        # 注册心跳监控
        heartbeat_monitor.register_request(
            request_id=request_id,
            session_id=session_id,
            on_timeout=on_timeout,
            on_progress=on_progress
        )
        
        # 发送请求（修改 _send_with_retry 使用心跳）
        return self._send_with_heartbeat(
            req, request_id, result_event, result_data
        )
    
    def _send_with_heartbeat(
        self,
        message: ACPMessage,
        request_id: str,
        result_event: threading.Event,
        result_data: dict
    ) -> Optional[Dict]:
        """使用心跳监控发送消息"""
        msg_id = str(message.id)
        q = queue.Queue()
        
        with self._lock:
            self._pending[msg_id] = q
        
        # 发送消息
        try:
            json_data = message.to_json() + "\n"
            self.process.stdin.write(json_data)
            self.process.stdin.flush()
        except Exception as e:
            return {"error": str(e), "status": "failed"}
        
        # 等待结果（带心跳监控）
        while not result_event.is_set():
            try:
                # 短时间等待，让心跳监控有机会检查
                response = q.get(timeout=5)
                
                # 收到完整响应，清理监控
                heartbeat_monitor._cleanup_request(request_id)
                return response
                
            except queue.Empty:
                # 检查是否超时
                if result_data.get('error'):
                    return result_data
        
        # 超时
        return result_data
    
    def _handle_notification(self, data: dict):
        """处理 ACP 通知（心跳来源）"""
        method = data.get("method")
        params = data.get("params", {})
        
        if method == "session/state":
            session_id = params.get("sessionId")
            state = params.get("state", "running")
            progress = params.get("progress")
            message = params.get("message", "")
            
            # 找到对应的请求 ID（需要反向查找）
            request_id = self._find_request_id(session_id)
            if request_id:
                heartbeat_monitor.heartbeat(
                    request_id=request_id,
                    state=state,
                    progress=progress,
                    message=message
                )
        
        # ... 现有通知处理逻辑 ...
```

---

### 3.3 修改 Claude Adapter 发送更多心跳

```javascript
// tools/claude-cli-acp.js - 增强进度通知

async function handleSessionPrompt(id, params) {
    const { sessionId: sid, prompt } = params;
    
    // 提取提示文本
    const promptText = prompt.map(p => {
        if (typeof p === 'string') return p;
        if (p.type === 'text') return p.text;
        return '';
    }).join('\\n');
    
    log(`Processing prompt: ${promptText.substring(0, 50)}...`);
    
    // 发送初始状态
    sendNotification('session/state', {
        sessionId: sid || sessionId,
        state: 'running',
        progress: 0.0,
        message: 'Starting...'
    });
    
    try {
        // 创建子进程时监听输出
        const claude = spawn('claude', args, {
            env: {
                ...process.env,
                ANTHROPIC_API_KEY: config.apiKey,
                ANTHROPIC_BASE_URL: config.baseUrl
            },
            stdio: ['ignore', 'pipe', 'pipe']
        });
        
        let output = '';
        let lastProgress = 0;
        let lastActivity = Date.now();
        
        // 监听 stdout - 每有输出就发送心跳
        claude.stdout.on('data', (data) => {
            const text = data.toString();
            output += text;
            
            // 估算进度（基于输出长度，简单但有效）
            const estimatedProgress = Math.min(0.9, output.length / 50000);
            if (estimatedProgress - lastProgress > 0.1) {
                lastProgress = estimatedProgress;
                sendNotification('session/state', {
                    sessionId: sid || sessionId,
                    state: 'running',
                    progress: lastProgress,
                    message: `Generating response... (${Math.round(lastProgress * 100)}%)`
                });
            }
            
            lastActivity = Date.now();
        });
        
        // 监听 stderr - 日志也视为活动
        claude.stderr.on('data', (data) => {
            log(`stderr: ${data.toString().trim()}`);
            lastActivity = Date.now();
        });
        
        // 定期检查活动（每 10 秒）
        const activityCheck = setInterval(() => {
            const silence = Date.now() - lastActivity;
            if (silence > 10000 && silence < 55000) {
                // 10-55 秒无输出，发送保持活动通知
                sendNotification('session/state', {
                    sessionId: sid || sessionId,
                    state: 'running',
                    progress: lastProgress,
                    message: 'Still processing...'
                });
            }
        }, 10000);
        
        claude.on('close', (code) => {
            clearInterval(activityCheck);
            
            if (code === 0) {
                // 完成
                sendNotification('session/state', {
                    sessionId: sid || sessionId,
                    state: 'completed',
                    progress: 1.0,
                    result: output.trim(),
                    message: 'Task completed successfully'
                });
                
                sendResponse({
                    jsonrpc: '2.0',
                    id: id,
                    result: {
                        result: output.trim(),
                        stopReason: 'end_turn'
                    }
                });
            } else {
                // 失败
                sendNotification('session/state', {
                    sessionId: sid || sessionId,
                    state: 'failed',
                    progress: lastProgress,
                    error: `claude exited with code ${code}`,
                    message: 'Task failed'
                });
                
                sendResponse({
                    jsonrpc: '2.0',
                    id: id,
                    error: {
                        code: -32000,
                        message: `claude exited with code ${code}`
                    }
                });
            }
        });
        
    } catch (error) {
        log(`Error: ${error.message}`);
        
        sendNotification('session/state', {
            sessionId: sid || sessionId,
            state: 'failed',
            error: error.message,
            message: error.message
        });
        
        sendResponse({
            jsonrpc: '2.0',
            id: id,
            error: {
                code: -32000,
                message: error.message
            }
        });
    }
}
```

---

## 4. 使用示例

### 4.1 简单任务（快速完成）

```python
from tools import acp_dispatch

# 简单任务 - 通常 10-30 秒完成
result = acp_dispatch(
    "巴黎是哪个国家的首都？",
    worker="claude-cli",
    # 心跳机制会自动适应 - 首次响应 30s，心跳 60s
)
print(result)
# ✅ 正常返回，不会被过早超时
```

### 4.2 复杂任务（长时间运行）

```python
# 复杂代码审查 - 可能需要 10 分钟
result = acp_dispatch(
    """
    请审查这个项目的代码质量：
    1. 检查所有 Python 文件的代码风格
    2. 识别潜在的性能问题
    3. 提出重构建议
    4. 生成详细报告
    """,
    worker="claude-cli",
    # 心跳机制允许长时间运行，只要有活动就不会超时
)
print(result)
# ✅ 只要 Agent 持续输出，就不会超时
```

### 4.3 自定义心跳参数

```python
from acp.transport import get_transport

# 获取 transport 并自定义心跳参数
transport = get_transport(worker="claude-cli")
transport.heartbeat_timeout = 120.0  # 2 分钟心跳超时
transport.max_total_time = 3600.0    # 1 小时最大时间

result = transport.send_prompt(session_id, "复杂任务...")
```

### 4.4 进度回调

```python
from acp.session_manager import get_session_manager

def on_progress(session_id, progress, message):
    print(f"\\r[{progress*100:5.1f}%] {message}", end="", flush=True)

manager = get_session_manager()
manager.register_progress_callback(on_progress)

result = acp_dispatch("任务...", worker="claude-cli")
# 输出：[ 45.3%] Analyzing code structure...
```

---

## 5. 优势对比

| 特性 | 传统超时 | 心跳超时 |
|------|----------|----------|
| **首次响应检测** | ❌ 无法区分 | ✅ 30s 内必须响应 |
| **长时间任务** | ❌ 容易超时 | ✅ 有活动就不超时 |
| **假死检测** | ❌ 无法检测 | ✅ 60s 无活动判定失败 |
| **进度可见** | ❌ 黑盒 | ✅ 实时进度更新 |
| **配置复杂度** | ✅ 简单 | 🟡 稍复杂但合理 |
| **资源浪费** | ❌ 可能过早终止 | ✅ 充分利用时间 |

---

## 6. 实施步骤

### 阶段 1: 基础心跳监控 (1-2 天)
- [ ] 创建 `heartbeat_monitor.py`
- [ ] 集成到 `StdioTransport`
- [ ] 修改 `send_prompt` 使用心跳
- [ ] 基础测试

### 阶段 2: 增强 Adapter (1 天)
- [ ] 修改 `claude-cli-acp.js` 发送进度
- [ ] 测试输出监听
- [ ] 验证心跳通知

### 阶段 3: 优化和文档 (1 天)
- [ ] 调整超时参数
- [ ] 添加使用示例
- [ ] 更新文档

**总工时**: 3-4 天

---

## 7. 测试计划

### 测试场景

| 场景 | 预期行为 | 验证方法 |
|------|----------|----------|
| 快速任务 (<10s) | 正常完成 | 计时 <10s |
| 中速任务 (1-3min) | 正常完成 | 持续进度更新 |
| 慢速任务 (5-15min) | 正常完成 | 不超时，有输出 |
| Agent 假死 | 60s 后超时 | 判定失败 |
| 无首次响应 | 30s 后超时 | 判定失败 |
| 超长任务 (>30min) | 1800s 后超时 | 强制终止 |

### 测试命令

```bash
# 测试心跳监控
cd /root/.hermes/plugins/acp-client
python3 tests/test_heartbeat.py

# 测试长时间任务
python3 -c "
from tools import acp_dispatch
result = acp_dispatch(
    '写一个 1000 行的完整 Python 项目，包含文档和测试',
    worker='claude-cli',
    timeout=1800
)
print(result)
"
```

---

## 8. 总结

**核心改进**:
1. ✅ 从"固定超时"改为"活动超时"
2. ✅ 实时进度可见
3. ✅ 检测 Agent 假死
4. ✅ 支持超长任务

**预期收益**:
- 复杂任务成功率提升 80%+
- 用户可看到实时进度
- 减少不必要的超时重试
- 更好的资源利用

**下一步**: 实施阶段 1，创建心跳监控器
