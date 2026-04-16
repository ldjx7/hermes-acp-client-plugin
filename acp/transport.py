import subprocess
import threading
import json
import os
import sys
import logging
import queue
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, List
from .protocol import ACPMessage, InitializeRequest, NewSessionRequest, PromptRequest
from .heartbeat_monitor import heartbeat_monitor, HeartbeatMonitor

logger = logging.getLogger(__name__)

@dataclass
class WorkerConfig:
    name: str
    command: List[str]

WORKER_CONFIGS = {
    # Direct ACP workers (native protocol)
    "gemini": WorkerConfig("gemini", ["gemini", "--acp", "--model", "gemini-2.5-flash"]),
    "gemini-pro": WorkerConfig("gemini-pro", ["gemini", "--acp", "--model", "gemini-2.5-pro"]),
    "gemini-3-pro": WorkerConfig("gemini-3-pro", ["gemini", "--acp", "--model", "gemini-3.1-pro-preview"]),
    "qwen": WorkerConfig("qwen", ["qwen", "--acp", "--dangerously-skip-permissions"]),
    
    # ACP via custom adapters
    "claude-cli": WorkerConfig("claude-cli", [
        "node", 
        os.path.expanduser("~/.hermes/plugins/acp-client/tools/claude-cli-acp.js")
    ]),  # ✅ 支持自定义 base URL（第三方代理）
    "codex": WorkerConfig("codex", ["codex", "--acp"]),
    
    # OpenACP bridge workers (unified interface for 28+ agents)
    "openacp:gemini": WorkerConfig("openacp:gemini", ["openacp", "agents", "run", "gemini", "--"]),
    "openacp:claude": WorkerConfig("openacp:claude", ["openacp", "agents", "run", "claude", "--"]),
    "openacp:codex": WorkerConfig("openacp:codex", ["openacp", "agents", "run", "codex", "--"]),
    "openacp:qwen": WorkerConfig("openacp:qwen", ["openacp", "agents", "run", "qwen", "--"]),
    "openacp:cursor": WorkerConfig("openacp:cursor", ["openacp", "agents", "run", "cursor", "--"]),
    "openacp:copilot": WorkerConfig("openacp:copilot", ["openacp", "agents", "run", "copilot", "--"]),
}

# OpenACP supported agents (28+ total)
OPENACP_AGENTS = [
    "gemini", "claude", "codex", "qwen", "cursor", "copilot",
    "goose", "opencode", "openhands", "cline", "blackbox",
    "auto-dev", "crow-cli", "cagent", "fast-agent", "factory-droid",
    "fount", "junie", "kimi-cli", "kiro-cli", "minion-code",
    "mistral-vibe", "openclaw", "pi", "qoder-cli", "stakpak",
    "stdio-bus", "vt-code"
]

def get_worker_command(worker_name: str) -> List[str]:
    """Return the command for a given worker name."""
    config = WORKER_CONFIGS.get(worker_name.lower())
    if not config:
        # Check if it's an OpenACP agent
        if worker_name.lower().startswith("openacp:"):
            agent = worker_name.split(":", 1)[1]
            return ["openacp", "agents", "run", agent, "--"]
        logger.warning(f"Unknown worker: {worker_name}, defaulting to gemini")
        return WORKER_CONFIGS["gemini"].command
    return config.command


def list_openacp_agents() -> List[str]:
    """List all available OpenACP agents."""
    return OPENACP_AGENTS.copy()


def is_openacp_worker(worker_name: str) -> bool:
    """Check if worker uses OpenACP bridge."""
    return worker_name.lower().startswith("openacp:") or worker_name.lower() in OPENACP_AGENTS


def get_gemini_model(worker_name: str) -> str:
    """
    Get Gemini model name from worker name.
    
    Args:
        worker_name: Worker name (e.g., "gemini", "gemini-pro", "gemini-3-pro")
        
    Returns:
        Model name (e.g., "gemini-2.5-flash", "gemini-2.5-pro", "gemini-3.1-pro-preview")
    """
    model_map = {
        "gemini": "gemini-2.5-flash",
        "gemini-flash": "gemini-2.5-flash",
        "gemini-pro": "gemini-2.5-pro",
        "gemini-2.5-flash": "gemini-2.5-flash",
        "gemini-2.5-pro": "gemini-2.5-pro",
        "gemini-3-pro": "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview": "gemini-3.1-pro-preview",
    }
    return model_map.get(worker_name.lower(), "gemini-2.5-flash")


class TransportError(Exception):
    """Base exception for transport errors."""
    pass


class WorkerNotAvailableError(TransportError):
    """Raised when worker process cannot be started."""
    pass


class RequestTimeoutError(TransportError):
    """Raised when a request times out."""
    pass


# OpenACP integration
from .openacp_bridge import OpenACPBridge, TaskResult, AgentError


class OpenACPTransport:
    """
    Transport layer for OpenACP API.
    
    Uses HTTP API instead of direct stdio subprocess.
    """
    
    def __init__(self, agent: str, base_url: str = None, timeout: float = 300.0):
        """
        Initialize OpenACP transport.
        
        Args:
            agent: Agent name (gemini, claude, codex, etc.)
            base_url: OpenACP daemon URL (optional)
            timeout: Request timeout in seconds
        """
        self.agent = agent
        self.base_url = base_url
        self.timeout = timeout
        self.bridge = OpenACPBridge(base_url=base_url)
        self._current_task_id: Optional[str] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize connection to OpenACP.
        
        Returns:
            True if initialized successfully
        """
        try:
            # Ensure daemon is running
            if not self.bridge.daemon_manager.ensure_running():
                logger.error("Failed to start OpenACP daemon")
                return False
            
            # List agents to verify connection
            agents = self.bridge.list_agents()
            logger.info(f"Connected to OpenACP, {len(agents)} agents available")
            
            self._initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenACP: {e}")
            return False
    
    def send_prompt(self, prompt: str, session_id: str = None) -> Dict[str, Any]:
        """
        Send prompt to agent.
        
        Args:
            prompt: Prompt text
            session_id: Optional session ID for continuation
            
        Returns:
            ACP-formatted response
        """
        if not self._initialized:
            if not self.initialize():
                return {"status": "error", "error": "Failed to initialize"}
        
        import uuid
        self._current_task_id = str(uuid.uuid4())
        
        try:
            result = self.bridge.dispatch(
                agent=self.agent,
                prompt=prompt,
                task_id=self._current_task_id,
                timeout=int(self.timeout)
            )
            
            if result.status == "success":
                return {
                    "status": "success",
                    "output": result.output,
                    "session_id": result.session_id,
                    "task_id": result.task_id
                }
            else:
                return {
                    "status": "error",
                    "error": result.error,
                    "task_id": result.task_id
                }
                
        except AgentError as e:
            logger.error(f"Agent error: {e}")
            return {"status": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get result of a task.
        
        Args:
            task_id: Task ID from send_prompt()
            
        Returns:
            Result dict or None
        """
        result = self.bridge.get_result(task_id)
        if result:
            return {
                "status": result.status,
                "output": result.output,
                "error": result.error,
                "session_id": result.session_id
            }
        return None
    
    def cancel(self, task_id: str) -> bool:
        """Cancel a running task."""
        return self.bridge.cancel(task_id)
    
    def close(self):
        """Close the transport."""
        self._initialized = False
        self._current_task_id = None


class StdioTransport:
    def __init__(self, command: list = None, worker: str = "gemini", 
                 max_retries: int = 3, retry_delay: float = 2.0,
                 request_timeout: float = 300.0,  # 300 秒，Gemini 建议的合理值
                 max_wait_timeout: float = 900.0):  # 900 秒（15 分钟）兜底超时
        self.worker = worker.lower()
        self.command = command or get_worker_command(self.worker)
        self.process: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._pending: Dict[str, queue.Queue] = {}
        self._running = False
        self._initialized = False
        self._on_notification: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Retry configuration
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout
        
        # 兜底超时（15 分钟）
        self.max_wait_timeout = max_wait_timeout
        
        # Notification callback for progress updates
        self._notification_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Error tracking
        self._last_stderr_error: Optional[Dict] = None
        
        # 心跳监控映射：session_id -> request_id
        self._session_to_request: Dict[str, str] = {}
        
        # 确保心跳监控器运行
        heartbeat_monitor.start()

    def start(self, on_notification: Optional[Callable[[Dict[str, Any]], None]] = None) -> bool:
        self._on_notification = on_notification
        with self._lock:
            if self.process:
                return True
            try:
                logger.info(f"Starting ACP server for worker '{self.worker}' with command: {' '.join(self.command)}")
                self.process = subprocess.Popen(
                    self.command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                self._running = True
                threading.Thread(target=self._read_errors, daemon=True).start()
                threading.Thread(target=self._read_stdout, daemon=True).start()
                return True
            except FileNotFoundError as e:
                logger.error(f"Worker '{self.worker}' not found: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to start ACP server for worker '{self.worker}': {e}")
                return False

    def _read_errors(self):
        """Read stderr from worker process and parse JSON errors."""
        try:
            error_buffer = ""
            for line in self.process.stderr:
                if not self._running:
                    break
                if line.strip():
                    error_line = line.strip()
                    logger.error(f"ACP-Server ({self.worker}): {error_line}")
                    
                    # Try to parse JSON errors from stderr
                    error_buffer += error_line
                    if error_buffer.startswith('{') or 'jsonrpc' in error_buffer:
                        try:
                            # Try to extract JSON from the buffer
                            if error_buffer.endswith('}'):
                                error_data = json.loads(error_buffer)
                                if "error" in error_data or "code" in error_data:
                                    logger.error(f"Parsed JSON error: {error_data}")
                                    # Store for later retrieval
                                    with self._lock:
                                        self._last_stderr_error = error_data
                                error_buffer = ""
                        except json.JSONDecodeError:
                            pass  # Keep buffering
                    elif error_buffer and not error_line.endswith('}'):
                        # Continue buffering
                        pass
                    else:
                        error_buffer = ""
        except Exception as e:
            if self._running:
                logger.error(f"Error reading stderr from {self.worker}: {e}")

    def _read_stdout(self):
        """
        Read stdout and dispatch responses/notifications.
        
        兼容不同 ACP 实现的输出格式：
        - 标准 ACP: 每行一个完整的 JSON-RPC 消息
        - Gemini/Claude: 可能混合日志输出和 JSON 消息
        """
        try:
            json_buffer = ""
            while self._running and self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if not line:
                    if self._running:
                        logger.warning(f"Worker {self.worker} stdout closed unexpectedly")
                    break
                
                line = line.rstrip('\n\r')
                if not line:
                    continue
                
                # 快速检查：是否是日志行（不以 { 开头）
                if not line.startswith('{'):
                    # 可能是日志输出，记录但不报错
                    if "ACP" in line or "Starting" in line or "Claude" in line or "Gemini" in line:
                        logger.debug(f"Worker log: {line[:100]}")
                    continue
                
                # 尝试解析 JSON
                json_buffer += line
                
                # 检查是否是完整的 JSON 对象（以}结尾）
                if not json_buffer.endswith('}'):
                    # 继续缓冲
                    continue
                
                try:
                    data = json.loads(json_buffer)
                    json_buffer = ""  # 清空缓冲
                    
                    msg_id = data.get("id")
                    if msg_id is not None:
                        msg_id = str(msg_id)
                        with self._lock:
                            if msg_id in self._pending:
                                self._pending[msg_id].put(data)
                            else:
                                logger.debug(f"No pending queue for message id: {msg_id}")
                    else:
                        # It's a notification
                        self._handle_notification(data)
                        
                except json.JSONDecodeError as e:
                    logger.debug(f"Invalid JSON from {self.worker}: {e} (buffer: {json_buffer[:100]})")
                    # 不清空缓冲，等待更多数据
                    if len(json_buffer) > 10000:  # 防止缓冲过大
                        logger.warning(f"JSON buffer too large, clearing")
                        json_buffer = ""
                except Exception as e:
                    logger.warning(f"Error processing response from {self.worker}: {e}")
                    json_buffer = ""
                    
        except Exception as e:
            if self._running:
                logger.error(f"Fatal error reading stdout from {self.worker}: {e}")
            self._running = False

    def _handle_notification(self, data: Dict[str, Any]):
        """Handle ACP notifications (e.g., session/state)."""
        method = data.get("method", "")
        params = data.get("params", {})
        
        logger.info(f"Notification from {self.worker}: {method}")
        logger.info(f"Notification params: {params}")
        
        # 心跳监控：转发 session/state 通知
        if method == "session/state":
            session_id = params.get("sessionId")
            state = params.get("state", "running")
            progress = params.get("progress")
            message = params.get("message", "")
            
            # 找到对应的请求 ID
            request_id = None
            with self._lock:
                request_id = self._session_to_request.get(session_id)
            
            if request_id:
                logger.debug(f"Heartbeat: {request_id} session={session_id} state={state} progress={progress}")
                heartbeat_monitor.heartbeat(
                    request_id=request_id,
                    state=state,
                    progress=progress,
                    message=message
                )
            else:
                logger.debug(f"No request ID found for session {session_id}")
        
        # Notify registered callbacks
        if self._on_notification:
            try:
                logger.debug(f"Calling primary notification callback")
                self._on_notification(data)
            except Exception as e:
                logger.error(f"Error in primary notification callback: {e}")
                import traceback
                traceback.print_exc()
        
        for i, callback in enumerate(self._notification_callbacks):
            try:
                logger.debug(f"Calling callback {i}")
                callback(data)
            except Exception as e:
                logger.error(f"Error in notification callback {i}: {e}")

    def send(self, message: ACPMessage, timeout: float = None) -> Optional[Dict]:
        """Send a message with retry logic."""
        if not self.process or not self._running:
            raise TransportError("Transport not running")
        
        timeout = timeout or self.request_timeout
        msg_id = str(message.id)
        q = queue.Queue()
        
        with self._lock:
            self._pending[msg_id] = q
        
        try:
            return self._send_with_retry(message, msg_id, q, timeout)
        except RequestTimeoutError:
            # Check if there was a stderr error
            with self._lock:
                if self._last_stderr_error:
                    error = self._last_stderr_error
                    self._last_stderr_error = None  # Clear after reading
                    return {"error": error, "id": msg_id}
            raise
        finally:
            with self._lock:
                if msg_id in self._pending:
                    del self._pending[msg_id]

    def _send_with_retry(self, message: ACPMessage, msg_id: str, 
                         q: queue.Queue, timeout: float) -> Optional[Dict]:
        """Send message with retry logic."""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                json_data = message.to_json() + "\n"
                self.process.stdin.write(json_data)
                self.process.stdin.flush()
                
                try:
                    response = q.get(timeout=timeout)
                    if attempt > 0:
                        logger.info(f"Request {msg_id} succeeded on attempt {attempt + 1}")
                    return response
                except queue.Empty:
                    last_error = RequestTimeoutError(f"Request {msg_id} timed out after {timeout}s")
                    logger.warning(f"Request {msg_id} timed out (attempt {attempt + 1}/{self.max_retries})")
                    
            except BrokenPipeError as e:
                last_error = TransportError(f"Broken pipe: {e}")
                logger.error(f"Broken pipe on attempt {attempt + 1}: {e}")
            except Exception as e:
                last_error = TransportError(f"Send failed: {e}")
                logger.error(f"Send failed on attempt {attempt + 1}: {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
        
        raise last_error

    def initialize(self) -> bool:
        """Initialize the ACP connection with retry."""
        if self._initialized:
            return True
        
        for attempt in range(self.max_retries):
            try:
                req = InitializeRequest()
                resp = self.send(req, timeout=self.request_timeout)
                if resp and "result" in resp:
                    self._initialized = True
                    logger.info(f"ACP transport initialized for {self.worker}")
                    return True
                logger.warning(f"Initialize failed (attempt {attempt + 1}): {resp}")
            except Exception as e:
                logger.error(f"Initialize error (attempt {attempt + 1}): {e}")
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)
        
        return False

    def create_session(self, name: str = "default") -> Optional[Dict]:
        """
        Create a new ACP session.
        
        兼容不同 ACP 实现的响应格式：
        - 标准 ACP: {"result": {"sessionId": "..."}}
        - Gemini: 可能直接返回 {"id": "...", "result": {...}}
        - 某些实现：sessionId 可能在 params 中（通过通知回调）
        
        Returns:
            包含会话信息的字典，或 None/错误信息
        """
        req = NewSessionRequest.create(name=name)
        response = self.send(req)
        
        if not response:
            return None
        
        # 如果响应已经包含 sessionId，直接返回
        if response.get("sessionId") or response.get("id"):
            return response
        
        # 如果响应包含 result，检查是否有 sessionId
        if "result" in response and isinstance(response["result"], dict):
            result = response["result"]
            if "sessionId" in result or "id" in result:
                return response
        
        # 某些 ACP 实现（如 Gemini）可能不需要显式创建会话
        # 它们会在第一次 prompt 时自动创建会话
        # 这种情况下，我们返回一个特殊标记
        if "error" in response:
            error_msg = response.get("error", {}).get("message", "")
            if "session" in error_msg.lower() or "not found" in error_msg.lower():
                # Gemini 可能不支持 session/new，需要特殊处理
                logger.warning(f"Worker may not support explicit session creation: {error_msg}")
                # 返回一个虚拟 session_id，实际会话会在 send_prompt 时创建
                return {"result": {"sessionId": "auto-created"}}
        
        return response
    
    def send_prompt(self, session_id: str, prompt: str) -> Optional[Dict]:
        """Send a prompt to an existing session."""
        req = PromptRequest.create(session_id=session_id, prompt=prompt)
        
        # 生成请求 ID
        request_id = str(req.id)
        
        # 创建完成事件（用于等待结果）
        result_event = threading.Event()
        result_data = {}
        
        def on_progress(request_id: str, progress: float, message: str):
            logger.info(f"Progress [{request_id}]: {progress*100:.1f}% - {message}")
            # 实时更新会话状态
            try:
                from .session_manager import get_session_manager
                manager = get_session_manager()
                manager.update_session(
                    session_id,
                    progress=progress,
                    progress_message=message
                )
            except Exception as e:
                logger.debug(f"Failed to update session progress: {e}")
        
        # 注册心跳监控（只监控进度，不超时）
        heartbeat_monitor.register_request(
            request_id=request_id,
            session_id=session_id,
            on_progress=on_progress
        )
        
        # 记录 session -> request 映射（用于通知处理）
        with self._lock:
            self._session_to_request[session_id] = request_id
        
        # 发送请求
        return self._send_with_heartbeat(
            req, request_id, session_id, result_event, result_data
        )
    
    def _send_with_heartbeat(
        self,
        message: ACPMessage,
        request_id: str,
        session_id: str,
        result_event: threading.Event,
        result_data: dict
    ) -> Optional[Dict]:
        """发送消息并等待结果（心跳监控只负责进度）"""
        msg_id = str(message.id)
        q = queue.Queue()
        
        with self._lock:
            self._pending[msg_id] = q
        
        # 发送消息
        try:
            json_data = message.to_json() + "\n"
            self.process.stdin.write(json_data)
            self.process.stdin.flush()
            logger.debug(f"Sent message {msg_id} to worker {self.worker}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            heartbeat_monitor._cleanup_request(request_id)
            return {"error": str(e), "status": "failed"}
        
        # 等待结果（带兜底超时）
        start_time = time.time()
        while self._running:  # ✅ 使用 _running 标志，避免无限循环
            # ✅ 检查是否超过兜底超时（15 分钟）
            elapsed = time.time() - start_time
            if elapsed > self.max_wait_timeout:
                logger.warning(
                    f"Timeout after {elapsed:.1f}s (max: {self.max_wait_timeout}s). "
                    f"Worker: {self.worker}, Session: {session_id}"
                )
                heartbeat_monitor._cleanup_request(request_id)
                with self._lock:
                    self._session_to_request.pop(session_id, None)
                return {
                    "error": f"Timeout after {elapsed:.1f}s (max: {self.max_wait_timeout}s)",
                    "status": "timeout",
                    "elapsed": elapsed
                }
            
            try:
                # 短时间等待，让心跳监控有机会更新进度
                response = q.get(timeout=5)
                
                # 收到完整响应，清理监控
                heartbeat_monitor._cleanup_request(request_id)
                with self._lock:
                    self._session_to_request.pop(session_id, None)
                return response
                
            except queue.Empty:
                # ✅ 检查进程是否还在运行
                if self.process and self.process.poll() is not None:
                    logger.error(f"Worker {self.worker} crashed (exit code: {self.process.poll()})")
                    heartbeat_monitor._cleanup_request(request_id)
                    with self._lock:
                        self._session_to_request.pop(session_id, None)
                    return {
                        "error": f"Worker {self.worker} crashed",
                        "status": "failed",
                        "exit_code": self.process.poll()
                    }
                # 进程还在运行，继续等待
        
        # self._running = False，退出循环
        logger.warning(f"Transport stopped while waiting for response")
        with self._lock:
            self._session_to_request.pop(session_id, None)
        return {"error": "Transport stopped", "status": "failed"}
    
    def send_prompt_auto(self, prompt: str, system_prompt: str = None) -> Optional[Dict]:
        """
        发送提示并自动管理会话。
        
        适用于不支持显式会话创建的 ACP 实现（如 Gemini）。
        
        Args:
            prompt: 提示文本
            system_prompt: 可选的系统提示
        
        Returns:
            响应字典
        """
        # 先尝试创建会话
        session_resp = self.create_session(name="auto-session")
        
        if session_resp and ("sessionId" in session_resp or "id" in session_resp or 
                            (session_resp.get("result") and 
                             ("sessionId" in session_resp["result"] or "id" in session_resp["result"]))):
            # 提取 sessionId
            session_id = (session_resp.get("sessionId") or 
                         session_resp.get("id") or 
                         session_resp.get("result", {}).get("sessionId") or
                         session_resp.get("result", {}).get("id"))
            
            if session_id:
                return self.send_prompt(session_id, prompt)
        
        # 如果会话创建失败，尝试直接发送（某些实现支持）
        logger.info("Session creation failed or not supported, trying direct prompt...")
        req = PromptRequest.create(session_id="default", prompt=prompt, system_prompt=system_prompt)
        return self.send(req)

    def register_notification_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register a callback for ACP notifications."""
        self._notification_callbacks.append(callback)

    def unregister_notification_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Unregister a notification callback."""
        if callback in self._notification_callbacks:
            self._notification_callbacks.remove(callback)

    def stop(self):
        """Stop the transport and clean up resources."""
        self._running = False
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Worker {self.worker} did not terminate gracefully, killing...")
                    self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping worker {self.worker}: {e}")
            finally:
                self.process = None
        
        # Clear pending requests
        with self._lock:
            for q in self._pending.values():
                try:
                    q.put_nowait({"error": "Transport stopped"})
                except:
                    pass
            self._pending.clear()
        
        logger.info(f"Transport stopped for worker {self.worker}")


# Multi-worker Singleton mapping
_transports: Dict[str, StdioTransport] = {}
_transports_lock = threading.Lock()

def get_transport(worker: str = "gemini", **kwargs) -> StdioTransport:
    """Get or create a transport for the specified worker."""
    global _transports
    worker = worker.lower()
    with _transports_lock:
        if worker not in _transports:
            _transports[worker] = StdioTransport(worker=worker, **kwargs)
        return _transports[worker]

def initialize_transport(on_notification=None, worker: str = "gemini", **kwargs) -> bool:
    """Initialize transport for the specified worker."""
    transport = get_transport(worker=worker, **kwargs)
    if not transport.start(on_notification=on_notification):
        return False
    return transport.initialize()

def shutdown_transport(worker: str = None):
    """Shutdown transport(s)."""
    global _transports
    with _transports_lock:
        if worker:
            worker = worker.lower()
            if worker in _transports:
                _transports[worker].stop()
                del _transports[worker]
        else:
            for t in _transports.values():
                t.stop()
            _transports.clear()
