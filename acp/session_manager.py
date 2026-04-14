import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

class SessionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class SessionState:
    session_id: str
    status: SessionStatus = SessionStatus.PENDING
    progress: float = 0.0
    progress_message: str = ""
    result: Any = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    prompt: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "prompt": self.prompt,
        }
    
    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()

class SessionManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SessionManager, cls).__new__(cls)
                cls._instance._sessions = {}
                cls._instance._rlock = threading.RLock()
            return cls._instance

    def create_session(self, prompt: str = None, session_id: str = None, **metadata) -> SessionState:
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]
        with self._rlock:
            session = SessionState(
                session_id=session_id,
                status=SessionStatus.PENDING,
                prompt=prompt,
                metadata=metadata
            )
            self._sessions[session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Optional[SessionState]:
        with self._rlock:
            return self._sessions.get(session_id)
    
    def update_session(self, session_id: str, **kwargs) -> bool:
        with self._rlock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            
            if "status" in kwargs:
                new_status = kwargs["status"]
                if isinstance(new_status, str):
                    new_status = SessionStatus(new_status)
                
                if new_status == SessionStatus.RUNNING and not session.started_at:
                    session.started_at = datetime.now()
                elif new_status in (SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED):
                    if not session.completed_at:
                        session.completed_at = datetime.now()
                kwargs["status"] = new_status
            
            session.update(**kwargs)
            return True

    def delete_session(self, session_id: str) -> bool:
        with self._rlock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def get_progress(self, session_id: str) -> Optional[Dict]:
        session = self.get_session(session_id)
        if not session:
            return None
        return {
            "session_id": session_id,
            "status": session.status.value,
            "progress": session.progress,
            "progress_message": session.progress_message,
        }

    def wait_for_completion(self, session_id: str, timeout: float = None) -> SessionState:
        start = time.time()
        while True:
            session = self.get_session(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            if session.status in (SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED):
                return session
            if timeout and (time.time() - start) > timeout:
                return session
            time.sleep(0.5)

def get_session_manager() -> SessionManager:
    return SessionManager()
