from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from acp.session_manager import SessionState


class SessionRepository(ABC):
    @abstractmethod
    def create_session(
        self, prompt: str | None = None, session_id: str | None = None, **metadata: Any
    ) -> SessionState:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[SessionState]:
        raise NotImplementedError

    @abstractmethod
    def update_session(self, session_id: str, **kwargs: Any) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def wait_for_completion(self, session_id: str, timeout: float | None = None) -> SessionState:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self) -> List[SessionState]:
        raise NotImplementedError
