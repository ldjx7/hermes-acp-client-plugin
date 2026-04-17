from __future__ import annotations

import json
import logging
from datetime import datetime

from acp.session_manager import SessionStatus
from acp.transport import peek_transport
from repositories import get_session_repository
from workers.registry import get_worker_adapter

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0


class ResultService:
    def __init__(self, repository=None):
        self._repository = repository or get_session_repository()

    def get_result(self, task_id: str, wait: bool = True, timeout: float | None = None) -> str:
        try:
            session = self._repository.get_session(task_id)
            if not session:
                return json.dumps({"error": f"Session {task_id} not found", "status": "not_found"})

            if not wait:
                return json.dumps(session.to_dict())

            effective_timeout = timeout or DEFAULT_TIMEOUT
            session = self._repository.wait_for_completion(task_id, timeout=effective_timeout)
            result = session.to_dict()

            if session.status == SessionStatus.COMPLETED:
                result["success"] = True
            elif session.status == SessionStatus.FAILED:
                result["success"] = False
                result["failure_reason"] = session.error or "Unknown error"
            elif session.status == SessionStatus.CANCELLED:
                result["success"] = False
                result["failure_reason"] = "Task cancelled"
            elif session.status == SessionStatus.RUNNING:
                result["success"] = False
                result["failure_reason"] = f"Timeout after {effective_timeout}s"

            return json.dumps(result)

        except Exception as e:
            logger.exception("Error in get_result")
            return json.dumps({"error": str(e), "status": "error"})

    def cancel(self, task_id: str) -> str:
        try:
            session = self._repository.get_session(task_id)
            if not session:
                return json.dumps({"error": f"Session {task_id} not found", "status": "not_found"})

            if session.status not in (SessionStatus.RUNNING, SessionStatus.PENDING):
                return json.dumps(
                    {
                        "error": f"Cannot cancel session in {session.status.value} state",
                        "status": "invalid_state",
                    }
                )

            cancellation_scope = "local_only"
            worker = session.metadata.get("worker") if session.metadata else None
            transport = peek_transport(worker) if worker else None
            adapter = get_worker_adapter(worker or "gemini")

            if transport:
                cancel_handler = adapter.get_cancel_handler(transport)
                if cancel_handler:
                    try:
                        cancel_response = cancel_handler(task_id)
                        if not cancel_response or "error" not in cancel_response:
                            cancellation_scope = "remote"
                    except Exception as e:
                        logger.warning("Remote cancel failed for %s: %s", task_id, e)

            self._repository.update_session(task_id, status=SessionStatus.CANCELLED)
            logger.info("Cancelled session %s", task_id)

            return json.dumps(
                {
                    "sessionId": task_id,
                    "status": "cancelled",
                    "cancellation_scope": cancellation_scope,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as e:
            logger.exception("Error in cancel")
            return json.dumps({"error": str(e), "status": "error"})


_result_service: ResultService | None = None


def get_result_service() -> ResultService:
    global _result_service
    if _result_service is None:
        _result_service = ResultService()
    return _result_service
