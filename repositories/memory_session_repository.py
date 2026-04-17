from __future__ import annotations

from typing import Any, Dict, List, Optional

from acp.session_manager import SessionState, get_session_manager

from .session_repository import SessionRepository


class MemorySessionRepository(SessionRepository):
    def __init__(self, manager=None):
        self._manager = manager or get_session_manager()

    def create_session(
        self, prompt: str | None = None, session_id: str | None = None, **metadata: Any
    ) -> SessionState:
        return self._manager.create_session(prompt=prompt, session_id=session_id, **metadata)

    def get_session(self, session_id: str) -> Optional[SessionState]:
        return self._manager.get_session(session_id)

    def update_session(self, session_id: str, **kwargs: Any) -> bool:
        return self._manager.update_session(session_id, **kwargs)

    def delete_session(self, session_id: str) -> bool:
        return self._manager.delete_session(session_id)

    def get_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._manager.get_progress(session_id)

    def wait_for_completion(self, session_id: str, timeout: float | None = None) -> SessionState:
        return self._manager.wait_for_completion(session_id, timeout=timeout)

    def list_sessions(self) -> List[SessionState]:
        with self._manager._rlock:
            return list(self._manager._sessions.values())
