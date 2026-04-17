from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict

from acp.session_manager import SessionStatus
from acp.transport import (
    RequestTimeoutError,
    TransportError,
    get_transport,
    initialize_transport,
    shutdown_transport,
)
from repositories import get_session_repository
from workers.registry import get_worker_adapter

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0


class DispatchService:
    def __init__(self, repository=None):
        self._repository = repository or get_session_repository()

    def _extract_error_message(self, response: Dict[str, Any]) -> str:
        error = response.get("error")
        if isinstance(error, dict):
            return error.get("message", str(error))
        return str(error)

    def _apply_prompt_response(self, session_id: str, response: Dict[str, Any]) -> str:
        if "error" in response:
            self._repository.update_session(
                session_id,
                status=SessionStatus.FAILED,
                error=self._extract_error_message(response),
            )
            return SessionStatus.FAILED.value

        if "result" in response:
            self._repository.update_session(
                session_id,
                status=SessionStatus.COMPLETED,
                result=response.get("result"),
                progress=1.0,
                progress_message="Completed",
            )
            return SessionStatus.COMPLETED.value

        self._repository.update_session(session_id, status=SessionStatus.RUNNING)
        return SessionStatus.RUNNING.value

    def handle_notification(self, data: Dict[str, Any]):
        method = data.get("method")
        params = data.get("params", {})

        if method == "session/state":
            session_id = params.get("sessionId")
            state_str = params.get("state")
            message = params.get("message", "")
            progress = params.get("progress")

            status_map = {
                "idle": SessionStatus.PENDING,
                "running": SessionStatus.RUNNING,
                "completed": SessionStatus.COMPLETED,
                "failed": SessionStatus.FAILED,
                "cancelled": SessionStatus.CANCELLED,
            }
            normalized_state = state_str.lower() if isinstance(state_str, str) else "running"
            status = status_map.get(normalized_state, SessionStatus.RUNNING)

            update_data = {"status": status}

            if status == SessionStatus.COMPLETED:
                update_data["result"] = params.get("result")
                update_data["completed_at"] = datetime.now()
            elif status == SessionStatus.FAILED:
                update_data["error"] = message or "Task failed"
                update_data["completed_at"] = datetime.now()
            elif status == SessionStatus.RUNNING:
                update_data["started_at"] = datetime.now()

            if progress is not None:
                update_data["progress"] = float(progress)
            if message:
                update_data["progress_message"] = message

            self._repository.update_session(session_id, **update_data)
            logger.info(
                "Notification: Updated session %s to %s (progress=%s)",
                session_id,
                status.value,
                progress,
            )

        elif method == "session/log":
            session_id = params.get("sessionId")
            log_entry = params.get("entry", {})
            logger.info("Session %s log: %s", session_id, log_entry)

    def ensure_initialized(self, worker: str = "gemini", **kwargs) -> bool:
        try:
            kwargs.setdefault("max_retries", DEFAULT_MAX_RETRIES)
            kwargs.setdefault("retry_delay", DEFAULT_RETRY_DELAY)
            kwargs.setdefault("request_timeout", DEFAULT_TIMEOUT)
            return initialize_transport(on_notification=self.handle_notification, worker=worker, **kwargs)
        except Exception as e:
            logger.error("Failed to initialize transport for %s: %s", worker, e)
            return False

    def dispatch(
        self,
        task: str,
        context: dict | None = None,
        worker: str = "gemini",
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> str:
        try:
            config = {}
            if timeout:
                config["request_timeout"] = timeout
            if max_retries:
                config["max_retries"] = max_retries

            if not self.ensure_initialized(worker=worker, **config):
                return json.dumps(
                    {
                        "error": f"Failed to initialize ACP transport for {worker}",
                        "status": "failed",
                        "worker": worker,
                    }
                )

            adapter = get_worker_adapter(worker)
            transport = get_transport(worker=worker)

            session_name = f"task_{int(time.time())}"
            response = transport.create_session(name=session_name)

            if not response:
                return json.dumps({"error": "No response from worker", "status": "failed"})

            if "error" in response:
                error_message = self._extract_error_message(response)
                return json.dumps({"error": error_message, "status": "failed"})

            session_id = response.get("result", {}).get("sessionId")
            if not session_id:
                return json.dumps({"error": "No sessionId in response", "response": response})

            self._repository.create_session(prompt=task, session_id=session_id, worker=worker)
            logger.info("Created session %s for worker %s", session_id, worker)

            prompt = adapter.build_prompt(task, context)
            response = adapter.normalize_prompt_response(transport.send_prompt(session_id, prompt))

            if not response:
                self._repository.update_session(
                    session_id, status=SessionStatus.FAILED, error="No response from worker"
                )
                return json.dumps(
                    {"error": "No response from worker", "sessionId": session_id, "status": "failed"}
                )

            if "error" in response:
                error_message = self._extract_error_message(response)
                self._repository.update_session(
                    session_id, status=SessionStatus.FAILED, error=error_message
                )
                return json.dumps(
                    {"error": error_message, "sessionId": session_id, "status": "failed"}
                )

            session_status = self._apply_prompt_response(session_id, response)
            logger.info("Dispatched task to session %s with status %s", session_id, session_status)

            return json.dumps(
                {
                    "sessionId": session_id,
                    "status": session_status,
                    "worker": worker,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except RequestTimeoutError as e:
            logger.error("Dispatch timeout: %s", e)
            return json.dumps({"error": str(e), "status": "timeout"})
        except TransportError as e:
            logger.error("Transport error: %s", e)
            return json.dumps({"error": str(e), "status": "transport_error"})
        except Exception as e:
            logger.exception("Error in dispatch")
            return json.dumps({"error": str(e), "status": "failed"})

    def shutdown(self, worker: str | None = None) -> str:
        try:
            shutdown_transport(worker)
            return json.dumps(
                {
                    "status": "shutdown",
                    "worker": worker or "all",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.exception("Error in shutdown")
            return json.dumps({"error": str(e), "status": "error"})


_dispatch_service: DispatchService | None = None


def get_dispatch_service() -> DispatchService:
    global _dispatch_service
    if _dispatch_service is None:
        _dispatch_service = DispatchService()
    return _dispatch_service
