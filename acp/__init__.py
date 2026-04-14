"""
ACP Client Plugin for Hermes Agent

Provides tools for dispatching tasks to ACP-compatible AI workers:
- Gemini CLI (--acp)
- Claude Code (--acp)
- Codex (--acp)

Usage:
    from acp.transport import get_transport, initialize_transport
    from acp.session_manager import get_session_manager
    from acp.hooks import pre_llm_call_hook, register_hooks
"""

from .transport import (
    StdioTransport,
    get_transport,
    initialize_transport,
    shutdown_transport,
    get_worker_command,
    WORKER_CONFIGS,
    TransportError,
    WorkerNotAvailableError,
    RequestTimeoutError,
)

from .session_manager import (
    SessionManager,
    SessionState,
    SessionStatus,
    get_session_manager,
)

from .protocol import (
    ACPMessage,
    InitializeRequest,
    NewSessionRequest,
    PromptRequest,
    MessageType,
)

from .hooks import (
    ProgressInjector,
    get_progress_injector,
    pre_llm_call_hook,
    register_hooks,
)

__version__ = "0.2.0"
__all__ = [
    # Transport
    "StdioTransport",
    "get_transport",
    "initialize_transport",
    "shutdown_transport",
    "get_worker_command",
    "WORKER_CONFIGS",
    "TransportError",
    "WorkerNotAvailableError",
    "RequestTimeoutError",
    # Session
    "SessionManager",
    "SessionState",
    "SessionStatus",
    "get_session_manager",
    # Protocol
    "ACPMessage",
    "InitializeRequest",
    "NewSessionRequest",
    "PromptRequest",
    "MessageType",
    # Hooks
    "ProgressInjector",
    "get_progress_injector",
    "pre_llm_call_hook",
    "register_hooks",
]
