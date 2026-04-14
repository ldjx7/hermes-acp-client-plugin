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

logger = logging.getLogger(__name__)

@dataclass
class WorkerConfig:
    name: str
    command: List[str]

WORKER_CONFIGS = {
    "gemini": WorkerConfig("gemini", ["gemini", "--acp"]),
    "claude": WorkerConfig("claude", ["claude", "--acp"]),
    "codex": WorkerConfig("codex", ["codex", "--acp"]),
    "qwen": WorkerConfig("qwen", ["qwen", "--acp"]),
}

def get_worker_command(worker_name: str) -> List[str]:
    """Return the command for a given worker name."""
    config = WORKER_CONFIGS.get(worker_name.lower())
    if not config:
        logger.warning(f"Unknown worker: {worker_name}, defaulting to gemini")
        return WORKER_CONFIGS["gemini"].command
    return config.command


class TransportError(Exception):
    """Base exception for transport errors."""
    pass


class WorkerNotAvailableError(TransportError):
    """Raised when worker process cannot be started."""
    pass


class RequestTimeoutError(TransportError):
    """Raised when a request times out."""
    pass


class StdioTransport:
    def __init__(self, command: list = None, worker: str = "gemini", 
                 max_retries: int = 3, retry_delay: float = 1.0,
                 request_timeout: float = 60.0):
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
        
        # Notification callback for progress updates
        self._notification_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        # Error tracking
        self._last_stderr_error: Optional[Dict] = None

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
        """Read stdout and dispatch responses/notifications."""
        try:
            while self._running and self.process and self.process.stdout:
                line = self.process.stdout.readline()
                if not line:
                    if self._running:
                        logger.warning(f"Worker {self.worker} stdout closed unexpectedly")
                    break
                try:
                    data = json.loads(line)
                    msg_id = data.get("id")
                    if msg_id is not None:
                        msg_id = str(msg_id)
                        with self._lock:
                            if msg_id in self._pending:
                                self._pending[msg_id].put(data)
                    else:
                        # It's a notification
                        self._handle_notification(data)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from {self.worker}: {e}")
                except Exception as e:
                    logger.warning(f"Error processing response from {self.worker}: {e}")
        except Exception as e:
            if self._running:
                logger.error(f"Fatal error reading stdout from {self.worker}: {e}")
            self._running = False

    def _handle_notification(self, data: Dict[str, Any]):
        """Handle ACP notifications (e.g., session/state)."""
        method = data.get("method", "")
        params = data.get("params", {})
        
        logger.debug(f"Notification from {self.worker}: {method}")
        
        # Notify registered callbacks
        if self._on_notification:
            try:
                self._on_notification(data)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")
        
        for callback in self._notification_callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Error in notification callback: {e}")

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
        """Create a new ACP session."""
        req = NewSessionRequest.create(name=name)
        return self.send(req)

    def send_prompt(self, session_id: str, prompt: str) -> Optional[Dict]:
        """Send a prompt to an existing session."""
        req = PromptRequest.create(session_id=session_id, prompt=prompt)
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
