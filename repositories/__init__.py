from .memory_session_repository import MemorySessionRepository
from .session_repository import SessionRepository

_session_repository: MemorySessionRepository | None = None


def get_session_repository() -> MemorySessionRepository:
    global _session_repository
    if _session_repository is None:
        _session_repository = MemorySessionRepository()
    return _session_repository


__all__ = [
    "SessionRepository",
    "MemorySessionRepository",
    "get_session_repository",
]
