"""
OpenACP Bridge for Hermes ACP Plugin

Provides unified API access to 28+ AI agents via OpenACP.
"""

import requests
import logging
import uuid
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
try:
    from .daemon_manager import DaemonManager, ensure_daemon_running
except ImportError:
    from daemon_manager import DaemonManager, ensure_daemon_running

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of an agent task."""
    task_id: str
    session_id: str
    status: str  # "success", "error", "timeout", "cancelled"
    output: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None


class SessionRegistry:
    """
    Maps Hermes task_id to OpenACP session_id.
    
    Thread-safe implementation with automatic cleanup of old entries.
    """
    
    MAX_AGE_HOURS = 24  # 会话记录保留时间
    
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}  # task_id -> {session_id, created_at}
        self._lock = threading.Lock()
    
    def register(self, task_id: str, session_id: str):
        """Register a task-session mapping."""
        with self._lock:
            self._registry[task_id] = {
                "session_id": session_id,
                "created_at": datetime.now()
            }
            logger.debug(f"Registered task {task_id} -> session {session_id}")
            self._cleanup_old_entries()
    
    def get_session(self, task_id: str) -> Optional[str]:
        """Get session_id for a task."""
        with self._lock:
            entry = self._registry.get(task_id)
            if entry:
                return entry["session_id"]
            return None
    
    def unregister(self, task_id: str):
        """Remove a task-session mapping."""
        with self._lock:
            if task_id in self._registry:
                del self._registry[task_id]
                logger.debug(f"Unregistered task {task_id}")
    
    def clear(self):
        """Clear all registrations."""
        with self._lock:
            self._registry.clear()
    
    def _cleanup_old_entries(self):
        """Remove entries older than MAX_AGE_HOURS."""
        cutoff = datetime.now() - timedelta(hours=self.MAX_AGE_HOURS)
        old_keys = [
            k for k, v in self._registry.items()
            if v["created_at"] < cutoff
        ]
        for k in old_keys:
            del self._registry[k]
            logger.debug(f"Cleaned up old task entry: {k}")


class ExceptionMapper:
    """Maps OpenACP errors to Hermes exceptions."""
    
    @staticmethod
    def map_error(error: str, status_code: int = None) -> Exception:
        """
        Map OpenACP error to appropriate Hermes exception.
        
        Args:
            error: Error message from OpenACP
            status_code: HTTP status code if available
            
        Returns:
            Appropriate exception instance
        """
        error_lower = error.lower() if error else ""
        
        # Timeout
        if "timeout" in error_lower or status_code == 408:
            return AgentTimeoutError(f"Agent execution timed out: {error}")
        
        # Rate limit
        if "rate limit" in error_lower or status_code == 429:
            return AgentRateLimitError(f"Agent rate limit exceeded: {error}")
        
        # Not found
        if "not found" in error_lower or status_code == 404:
            return AgentNotFoundError(f"Agent or session not found: {error}")
        
        # Authentication
        if "auth" in error_lower or status_code == 401:
            return AgentAuthError(f"Agent authentication failed: {error}")
        
        # Execution error
        if status_code and status_code >= 500:
            return AgentServerError(f"Agent server error ({status_code}): {error}")
        
        # Default
        return AgentExecutionError(f"Agent execution failed: {error}")


class OpenACPBridge:
    """
    Unified bridge to OpenACP API.
    
    Automatically manages daemon lifecycle.
    
    Timeout Configuration:
    - DEFAULT_REQUEST_TIMEOUT: 300s (5 min) - Standard tasks
    - MAX_REQUEST_TIMEOUT: 600s (10 min) - Complex tasks
    - Can be extended per-request for very long operations
    """
    
    DEFAULT_REQUEST_TIMEOUT = 300  # 5 minutes - 默认超时，适用于 95% 场景
    MAX_REQUEST_TIMEOUT = 600  # 10 minutes - 复杂任务超时上限
    DEFAULT_CONNECT_TIMEOUT = 10  # 10 seconds - 标准连接超时
    
    def __init__(self, base_url: str = None, daemon_manager: DaemonManager = None):
        """
        Initialize OpenACP bridge.
        
        Args:
            base_url: OpenACP daemon URL (optional, uses env var or default)
            daemon_manager: Optional DaemonManager instance
        """
        self.base_url = base_url
        self.daemon_manager = daemon_manager or DaemonManager(base_url)
        self.session_registry = SessionRegistry()
        self._session: Optional[requests.Session] = None
        self._lock = threading.Lock()
    
    @property
    def session(self) -> requests.Session:
        """Lazy-load requests session with connection pooling."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Hermes-ACP-Plugin"
            })
            # 配置连接池
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=5,
                pool_maxsize=10,
                pool_block=False,
                max_retries=2
            )
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session
    
    def close(self):
        """Close the bridge and release resources."""
        with self._lock:
            if self._session:
                self._session.close()
                self._session = None
            self.session_registry.clear()
    
    def dispatch(self, agent: str, prompt: str, task_id: str = None, 
                 timeout: int = None) -> TaskResult:
        """
        Dispatch a task to an AI agent.
        
        Args:
            agent: Agent name (gemini, claude, codex, etc.)
            prompt: Task prompt
            task_id: Optional task ID (generated if not provided)
            timeout: Request timeout in seconds 
                     - Default: 300s (5 min) for standard tasks
                     - Max: 600s (10 min) for complex tasks
                     - Can be extended beyond 600s for very long operations
        
        Returns:
            TaskResult with status and output
        """
        timeout = timeout or self.DEFAULT_REQUEST_TIMEOUT
        
        # Ensure daemon is running
        if not self.daemon_manager.ensure_running():
            return TaskResult(
                task_id=task_id or str(uuid.uuid4()),
                session_id="",
                status="error",
                error="Failed to start OpenACP daemon",
                created_at=datetime.now()
            )
        
        # Generate task ID if not provided
        if not task_id:
            task_id = str(uuid.uuid4())
        
        try:
            logger.info(f"Dispatching to {agent}: {prompt[:50]}...")
            
            # Create session and dispatch task
            payload = {
                "agent": agent,
                "prompt": prompt,
                "timeout": timeout
            }
            
            response = self.session.post(
                f"{self.base_url or self.daemon_manager.base_url}/api/sessions",
                json=payload,
                timeout=(self.DEFAULT_CONNECT_TIMEOUT, timeout + 30)
            )
            
            if response.status_code not in [200, 201]:
                raise ExceptionMapper.map_error(
                    response.text or f"HTTP {response.status_code}",
                    response.status_code
                )
            
            result_data = response.json()
            session_id = result_data.get("sessionId", "")
            
            # Register session
            self.session_registry.register(task_id, session_id)
            
            logger.info(f"Task {task_id} dispatched to {agent} (session: {session_id})")
            
            return TaskResult(
                task_id=task_id,
                session_id=session_id,
                status="success",
                output=result_data.get("output", ""),
                error=None,
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to dispatch task: {e}")
            if isinstance(e, (AgentTimeoutError, AgentRateLimitError, AgentNotFoundError, 
                            AgentAuthError, AgentExecutionError, AgentServerError)):
                raise
            return TaskResult(
                task_id=task_id,
                session_id="",
                status="error",
                error=str(e),
                created_at=datetime.now()
            )
    
    def get_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get result of a task.
        
        Args:
            task_id: Task ID from dispatch()
            
        Returns:
            TaskResult or None if not found
        """
        session_id = self.session_registry.get_session(task_id)
        if not session_id:
            logger.warning(f"Task {task_id} not found in registry")
            return None
        
        try:
            response = self.session.get(
                f"{self.base_url or self.daemon_manager.base_url}/api/sessions/{session_id}",
                timeout=(self.DEFAULT_CONNECT_TIMEOUT, 30)
            )
            
            if response.status_code == 404:
                return None
            
            if response.status_code != 200:
                raise ExceptionMapper.map_error(
                    response.text or f"HTTP {response.status_code}",
                    response.status_code
                )
            
            result_data = response.json()
            state = result_data.get("state", "unknown")
            
            # Map state to status
            if state == "completed":
                status = "success"
            elif state == "failed":
                status = "error"
            elif state == "cancelled":
                status = "cancelled"
            else:
                status = "running"
            
            return TaskResult(
                task_id=task_id,
                session_id=session_id,
                status=status,
                output=result_data.get("output", ""),
                error=result_data.get("error"),
                created_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to get result: {e}")
            return TaskResult(
                task_id=task_id,
                session_id=session_id or "",
                status="error",
                error=str(e),
                created_at=datetime.now()
            )
    
    def cancel(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        session_id = self.session_registry.get_session(task_id)
        if not session_id:
            logger.warning(f"Cannot cancel task {task_id}: not found")
            return False
        
        try:
            response = self.session.post(
                f"{self.base_url or self.daemon_manager.base_url}/api/sessions/{session_id}/cancel",
                timeout=(self.DEFAULT_CONNECT_TIMEOUT, 30)
            )
            
            if response.status_code == 200:
                logger.info(f"Cancelled task {task_id}")
                return True
            else:
                logger.error(f"Failed to cancel task {task_id}: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error cancelling task: {e}")
            return False
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """
        List all available agents.
        
        Returns:
            List of agent information
        """
        # Ensure daemon is running
        if not self.daemon_manager.ensure_running():
            return []
        
        try:
            response = self.session.get(
                f"{self.base_url or self.daemon_manager.base_url}/api/agents",
                timeout=(self.DEFAULT_CONNECT_TIMEOUT, 30)
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("agents", [])
            return []
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []


# Custom exceptions
class AgentError(Exception):
    """Base exception for agent errors."""
    pass

class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""
    pass

class AgentRateLimitError(AgentError):
    """Raised when agent rate limit is exceeded."""
    pass

class AgentNotFoundError(AgentError):
    """Raised when agent or session is not found."""
    pass

class AgentAuthError(AgentError):
    """Raised when agent authentication fails."""
    pass

class AgentExecutionError(AgentError):
    """Raised when agent execution fails."""
    pass

class AgentServerError(AgentError):
    """Raised when agent server returns an error."""
    pass


# Convenience functions
_default_bridge: Optional[OpenACPBridge] = None


def get_bridge() -> OpenACPBridge:
    """Get default OpenACPBridge instance."""
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = OpenACPBridge()
    return _default_bridge


def dispatch(agent: str, prompt: str, task_id: str = None) -> TaskResult:
    """Dispatch task using default bridge."""
    return get_bridge().dispatch(agent, prompt, task_id)


def get_result(task_id: str) -> Optional[TaskResult]:
    """Get result using default bridge."""
    return get_bridge().get_result(task_id)


def cancel(task_id: str) -> bool:
    """Cancel task using default bridge."""
    return get_bridge().cancel(task_id)


def list_agents() -> List[Dict[str, Any]]:
    """List agents using default bridge."""
    return get_bridge().list_agents()
