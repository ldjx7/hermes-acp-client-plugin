"""
Heartbeat Monitor for ACP Transport

Simplified version: Only responsible for progress feedback, no timeout judgment.
Timeout is handled by Agent itself (Claude CLI 15 minutes, Gemini CLI has its own timeout).

Features:
- Real-time progress callback (user can see task progress)
- Process hang detection (log only, no termination)
- Request cleanup (release resources after completion)
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class HeartbeatState:
    """Heartbeat state for a request"""
    request_id: str
    session_id: str
    last_heartbeat: datetime = field(default_factory=datetime.now)
    last_progress: float = 0.0
    current_state: str = "pending"
    progress_message: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    
    def reset_heartbeat(self):
        """Reset heartbeat timer"""
        self.last_heartbeat = datetime.now()
    
    def time_since_heartbeat(self) -> float:
        """Seconds since last heartbeat"""
        return (datetime.now() - self.last_heartbeat).total_seconds()
    
    def total_elapsed(self) -> float:
        """Total elapsed time"""
        return (datetime.now() - self.start_time).total_seconds()


class HeartbeatMonitor:
    """
    Heartbeat Monitor (Simplified)
    
    Only responsible for progress feedback, no timeout judgment.
    Timeout is handled by Agent itself.
    """
    
    def __init__(self, progress_threshold: float = 0.01):
        self.progress_threshold = progress_threshold
        
        self._states: Dict[str, HeartbeatState] = {}
        self._callbacks: Dict[str, Dict[str, Callable]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start monitoring thread"""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            logger.debug("Heartbeat monitor started")
    
    def stop(self):
        """Stop monitoring"""
        with self._lock:
            if not self._running:
                return
            self._running = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
        logger.debug("Heartbeat monitor stopped")
    
    def register_request(
        self,
        request_id: str,
        session_id: str,
        on_progress: Optional[Callable[[str, float, str], None]] = None
    ):
        """
        Register a new request for monitoring
        
        Args:
            request_id: Request ID
            session_id: Session ID
            on_progress: Progress update callback
        """
        with self._lock:
            self._states[request_id] = HeartbeatState(
                request_id=request_id,
                session_id=session_id,
                last_heartbeat=datetime.now(),
                start_time=datetime.now()
            )
            self._callbacks[request_id] = {
                'on_progress': on_progress
            }
        logger.debug(f"Registered request {request_id} for monitoring (session={session_id})")
    
    def heartbeat(self, request_id: str, state: str, progress: float = None, message: str = ""):
        """
        Receive heartbeat (ACP notification)
        
        Args:
            request_id: Request ID
            state: State (running/completed/failed)
            progress: Progress (0.0-1.0)
            message: Progress message
        """
        need_cleanup = False
        
        with self._lock:
            if request_id not in self._states:
                logger.debug(f"Heartbeat for unknown request {request_id}, ignoring")
                return
            
            hb_state = self._states[request_id]
            callbacks = self._callbacks.get(request_id, {})
            
            # Check progress change
            progress_changed = False
            if progress is not None:
                progress_changed = abs(progress - hb_state.last_progress) > self.progress_threshold
                if progress_changed:
                    hb_state.last_progress = progress
            
            # State change
            state_changed = state != hb_state.current_state
            hb_state.current_state = state
            hb_state.progress_message = message
            
            # Reset heartbeat timer (reset on any activity)
            if progress_changed or state_changed or state in ("running", "completed", "failed"):
                old_elapsed = hb_state.time_since_heartbeat()
                hb_state.reset_heartbeat()
                logger.debug(
                    f"Heartbeat reset for {request_id}: "
                    f"state={state}, progress={progress}, message='{message}', "
                    f"was silent for {old_elapsed:.1f}s"
                )
                
                # Call progress callback
                if progress is not None and callbacks.get('on_progress'):
                    try:
                        callbacks['on_progress'](request_id, progress, message)
                    except Exception as e:
                        logger.warning(f"Progress callback error: {e}")
            
            # Mark for cleanup on completion or failure
            if state in ("completed", "failed"):
                elapsed = hb_state.total_elapsed()
                logger.info(f"Request {request_id} {state} (total time: {elapsed:.1f}s)")
                need_cleanup = True
        
        # Cleanup outside lock to avoid deadlock
        if need_cleanup:
            self._cleanup_request(request_id)
    
    def _cleanup_request(self, request_id: str):
        """Clean up completed request"""
        with self._lock:
            self._states.pop(request_id, None)
            self._callbacks.pop(request_id, None)
        logger.debug(f"Cleaned up completed request {request_id}")
    
    def _monitor_loop(self):
        """Monitoring loop (background thread) - log only, no termination"""
        while self._running:
            time.sleep(5)  # Check every 5 seconds
            
            # Copy state list to reduce lock holding time
            with self._lock:
                states_copy = [(rid, st) for rid, st in self._states.items()]
            
            for request_id, state in states_copy:
                # Check if already cleaned up
                with self._lock:
                    if request_id not in self._states:
                        continue
                
                silence = state.time_since_heartbeat()
                total = state.total_elapsed()
                
                # Log only, no termination
                if silence > 300:  # 5 minutes no activity
                    logger.info(f"{request_id}: Long silence ({silence:.0f}s), may be slow task")
                if total > 600:  # 10 minutes total time
                    logger.info(f"{request_id}: Running ({total:.0f}s), progress={state.last_progress*100:.0f}%")
    
    def get_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get request status"""
        with self._lock:
            if request_id not in self._states:
                return None
            
            state = self._states[request_id]
            
            return {
                "request_id": request_id,
                "session_id": state.session_id,
                "current_state": state.current_state,
                "last_progress": state.last_progress,
                "progress_message": state.progress_message,
                "silence_seconds": round(state.time_since_heartbeat(), 1),
                "total_elapsed": round(state.total_elapsed(), 1),
            }


# Global monitor instance (singleton)
heartbeat_monitor = HeartbeatMonitor(progress_threshold=0.01)


# Convenience functions
def start_monitoring():
    """Start heartbeat monitoring"""
    heartbeat_monitor.start()


def stop_monitoring():
    """Stop heartbeat monitoring"""
    heartbeat_monitor.stop()


def get_monitor() -> HeartbeatMonitor:
    """Get global monitor instance"""
    return heartbeat_monitor
