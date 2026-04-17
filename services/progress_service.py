from __future__ import annotations

import json
import logging
from datetime import datetime

from acp.session_manager import SessionStatus
from repositories import get_session_repository

logger = logging.getLogger(__name__)


class ProgressService:
    def __init__(self, repository=None):
        self._repository = repository or get_session_repository()

    def get_progress(self, task_id: str) -> str:
        try:
            progress = self._repository.get_progress(task_id)

            if not progress:
                return json.dumps({"error": f"Session {task_id} not found", "status": "not_found"})

            session = self._repository.get_session(task_id)
            if session:
                progress["created_at"] = session.created_at.isoformat() if session.created_at else None
                progress["updated_at"] = session.updated_at.isoformat() if session.updated_at else None

            return json.dumps(progress)

        except Exception as e:
            logger.exception("Error in get_progress")
            return json.dumps({"error": str(e), "status": "error"})

    def list_sessions(self, active_only: bool = True) -> str:
        try:
            result = []
            for session in self._repository.list_sessions():
                if active_only and session.status not in (SessionStatus.RUNNING, SessionStatus.PENDING):
                    continue

                result.append(
                    {
                        "session_id": session.session_id,
                        "status": session.status.value,
                        "progress": session.progress,
                        "prompt": (
                            session.prompt[:50] + "..."
                            if session.prompt and len(session.prompt) > 50
                            else session.prompt
                        ),
                        "created_at": session.created_at.isoformat() if session.created_at else None,
                    }
                )

            result.sort(key=lambda item: item["created_at"] or "", reverse=True)
            return json.dumps({"sessions": result, "total": len(result), "active_only": active_only})

        except Exception as e:
            logger.exception("Error in list_sessions")
            return json.dumps({"error": str(e), "status": "error"})

    def cleanup(self, max_age_hours: float = 24.0) -> str:
        try:
            now = datetime.now()
            cleaned = []

            for session in self._repository.list_sessions():
                if session.created_at:
                    age = now - session.created_at
                    if age.total_seconds() > max_age_hours * 3600:
                        self._repository.delete_session(session.session_id)
                        cleaned.append(session.session_id)

            logger.info("Cleaned up %s old sessions", len(cleaned))
            return json.dumps(
                {
                    "cleaned_count": len(cleaned),
                    "cleaned_sessions": cleaned,
                    "max_age_hours": max_age_hours,
                }
            )

        except Exception as e:
            logger.exception("Error in cleanup")
            return json.dumps({"error": str(e), "status": "error"})


_progress_service: ProgressService | None = None


def get_progress_service() -> ProgressService:
    global _progress_service
    if _progress_service is None:
        _progress_service = ProgressService()
    return _progress_service
