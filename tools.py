import json
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from acp.transport import get_transport, initialize_transport, TransportError, RequestTimeoutError, shutdown_transport
from acp.session_manager import get_session_manager, SessionStatus
from acp.hooks import pre_llm_call_hook, register_hooks
from acp.worker_manager import get_worker_manager, initialize_workers, WorkerStatus

logger = logging.getLogger(__name__)

# 初始化 Worker 管理器
initialize_workers()

# 全局配置
DEFAULT_TIMEOUT = 300.0  # 从 120 改为 300 秒
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0  # 从 1.0 改为 2.0 秒


def handle_notification(data):
    """Callback for ACP notifications."""
    method = data.get("method")
    params = data.get("params", {})
    
    if method == "session/state":
        session_id = params.get("sessionId")
        state_str = params.get("state")
        message = params.get("message", "")
        progress = params.get("progress")
        
        manager = get_session_manager()
        status_map = {
            "idle": SessionStatus.PENDING,
            "running": SessionStatus.RUNNING,
            "completed": SessionStatus.COMPLETED,
            "failed": SessionStatus.FAILED,
            "cancelled": SessionStatus.CANCELLED
        }
        status = status_map.get(state_str.lower(), SessionStatus.RUNNING)
        
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
            
        manager.update_session(session_id, **update_data)
        logger.info(f"Notification: Updated session {session_id} to {status.value} (progress={progress})")
    
    elif method == "session/log":
        # 处理日志通知
        session_id = params.get("sessionId")
        log_entry = params.get("entry", {})
        logger.info(f"Session {session_id} log: {log_entry}")


def ensure_initialized(worker: str = "gemini", **kwargs) -> bool:
    """
    Ensure transport is initialized with retry logic.
    
    Args:
        worker: Worker name (gemini/claude/codex)
        **kwargs: Additional transport config (max_retries, retry_delay, request_timeout)
    """
    try:
        kwargs.setdefault("max_retries", DEFAULT_MAX_RETRIES)
        kwargs.setdefault("retry_delay", DEFAULT_RETRY_DELAY)
        kwargs.setdefault("request_timeout", DEFAULT_TIMEOUT)
        return initialize_transport(on_notification=handle_notification, worker=worker, **kwargs)
    except Exception as e:
        logger.error(f"Failed to initialize transport for {worker}: {e}")
        return False


def acp_dispatch(task: str, context: dict = None, worker: str = "gemini", 
                 timeout: float = None, max_retries: int = None, 
                 auto_fallback: bool = True) -> str:
    """
    Handler for acp_dispatch tool.
    
    派发任务到 ACP worker，支持多平台、错误重试和自动故障转移。
    
    Args:
        task: 任务描述
        context: 额外上下文（可选）
        worker: worker 平台 (gemini/claude/codex)，默认 gemini
        timeout: 请求超时（秒）
        max_retries: 最大重试次数
        auto_fallback: 是否自动故障转移（默认 True）
        
    Returns:
        JSON 字符串，包含 sessionId 和状态，或错误信息
    """
    try:
        # 配置参数
        config = {}
        if timeout:
            config["request_timeout"] = timeout
        if max_retries:
            config["max_retries"] = max_retries
        
        worker_manager = get_worker_manager() if auto_fallback else None
        exclude_workers = []
        attempts = 0
        effective_max_retries = max_retries or DEFAULT_MAX_RETRIES
        
        while attempts < effective_max_retries:
            # 选择 Worker
            current_worker = worker if attempts == 0 else None
            if auto_fallback and worker_manager:
                if not current_worker or current_worker in exclude_workers:
                    current_worker = worker_manager.get_available_worker(exclude=exclude_workers)
                    if not current_worker:
                        return json.dumps({
                            "error": "No available workers",
                            "status": "failed",
                            "worker_status": worker_manager.get_status_summary(),
                        })
            
            # 初始化传输
            if not ensure_initialized(worker=current_worker, **config):
                if worker_manager:
                    worker_manager.mark_offline(current_worker)
                exclude_workers.append(current_worker)
                attempts += 1
                continue
            
            transport = get_transport(worker=current_worker)
            manager = get_session_manager()
            start_time = time.time()
            
            # 1. 创建会话
            session_name = f"task_{int(time.time())}"
            resp = transport.create_session(name=session_name)
            
            if not resp:
                if worker_manager:
                    worker_manager.mark_error(current_worker, "No response", is_rate_limit=False)
                exclude_workers.append(current_worker)
                attempts += 1
                continue
            
            if "error" in resp:
                error_msg = resp.get("error", {}).get("message", "Unknown error") if isinstance(resp.get("error"), dict) else str(resp.get("error"))
                if worker_manager:
                    is_rate_limit = worker_manager.is_rate_limit_error(error_msg)
                    worker_manager.mark_error(current_worker, error_msg, is_rate_limit=is_rate_limit)
                exclude_workers.append(current_worker)
                attempts += 1
                if is_rate_limit and auto_fallback:
                    logger.warning(f"Rate limit on {current_worker}, trying next worker...")
                    continue
                return json.dumps({"error": error_msg, "status": "failed", "worker": current_worker})
            
            # 修复：兼容多种 sessionId 提取路径
            # Gemini ACP 可能返回不同的响应格式
            session_id = None
            
            # 路径 1: 标准 ACP - resp.result.sessionId
            if not session_id and "result" in resp:
                session_id = resp["result"].get("sessionId")
            
            # 路径 2: Gemini 可能直接返回 sessionId 在 result 中
            if not session_id and "result" in resp and isinstance(resp["result"], dict):
                session_id = resp["result"].get("id")  # 某些实现使用 id 而非 sessionId
            
            # 路径 3: 某些实现可能直接返回 sessionId 在顶层
            if not session_id:
                session_id = resp.get("sessionId") or resp.get("id")
            
            # 路径 4: 如果还是没有，尝试从 params 中提取（用于通知回调）
            if not session_id and "params" in resp:
                session_id = resp["params"].get("sessionId")
            
            if not session_id:
                logger.error(f"Failed to extract sessionId from response: {resp}")
                if worker_manager:
                    worker_manager.mark_error(current_worker, "No sessionId in response", is_rate_limit=False)
                return json.dumps({
                    "error": "No sessionId in response",
                    "response": resp,
                    "worker": current_worker,
                    "response_keys": list(resp.keys()) if isinstance(resp, dict) else None
                })
            
            # 注册到管理器
            manager.create_session(prompt=task, session_id=session_id)
            logger.info(f"Created session {session_id} for worker {current_worker}")
            
            # 2. 发送提示
            prompt = task
            if context:
                prompt += f"\n\nContext:\n{json.dumps(context, indent=2)}"
            
            resp = transport.send_prompt(session_id, prompt)
            
            if not resp:
                manager.update_session(session_id, status=SessionStatus.FAILED, error="No response from worker")
                if worker_manager:
                    worker_manager.mark_error(current_worker, "No response", is_rate_limit=False)
                return json.dumps({"error": "No response from worker", "sessionId": session_id, "status": "failed", "worker": current_worker})
            
            if "error" in resp:
                error_msg = resp.get("error", {}).get("message", "Unknown error") if isinstance(resp.get("error"), dict) else str(resp.get("error"))
                manager.update_session(session_id, status=SessionStatus.FAILED, error=error_msg)
                if worker_manager:
                    is_rate_limit = worker_manager.is_rate_limit_error(error_msg)
                    worker_manager.mark_error(current_worker, error_msg, is_rate_limit=is_rate_limit)
                if is_rate_limit and auto_fallback and attempts < effective_max_retries - 1:
                    logger.warning(f"Rate limit on {current_worker}, retrying with different worker...")
                    exclude_workers.append(current_worker)
                    attempts += 1
                    continue
                return json.dumps({"error": error_msg, "sessionId": session_id, "status": "failed", "worker": current_worker})
            
            # 成功
            response_time = time.time() - start_time
            if worker_manager:
                # 从响应中提取模型信息
                model = None
                if "result" in resp:
                    result = resp["result"]
                    # 路径 1: result._meta.quota.model_usage
                    quota = result.get("_meta", {}).get("quota", {})
                    model_usage = quota.get("model_usage", [])
                    if model_usage:
                        model = model_usage[0].get("model")
                    # 路径 2: result._meta.model_usage (备用)
                    if not model:
                        model_usage = result.get("_meta", {}).get("model_usage", [])
                        if model_usage:
                            model = model_usage[0].get("model")
                
                worker_manager.mark_success(current_worker, response_time, model)
            
            # 更新状态为运行中
            manager.update_session(session_id, status=SessionStatus.RUNNING)
            logger.info(f"Dispatched task to session {session_id} on {current_worker}")
            
            return json.dumps({
                "sessionId": session_id, 
                "status": "dispatched",
                "worker": current_worker,
                "attempt": attempts + 1,
                "timestamp": datetime.now().isoformat()
            })
        
        # 所有尝试都失败
        return json.dumps({
            "error": f"Failed after {attempts} attempts",
            "status": "failed",
            "attempted_workers": exclude_workers,
            "worker_status": worker_manager.get_status_summary() if worker_manager else None,
        })
        
    except RequestTimeoutError as e:
        logger.error(f"Dispatch timeout: {e}")
        return json.dumps({"error": str(e), "status": "timeout"})
    except TransportError as e:
        logger.error(f"Transport error: {e}")
        return json.dumps({"error": str(e), "status": "transport_error"})
    except Exception as e:
        logger.exception("Error in acp_dispatch")
        return json.dumps({"error": str(e), "status": "failed"})


def acp_progress(task_id: str) -> str:
    """
    Handler for acp_progress tool.
    
    查询任务进度。
    
    Args:
        task_id: 会话 ID
        
    Returns:
        JSON 字符串，包含进度信息
    """
    try:
        manager = get_session_manager()
        progress = manager.get_progress(task_id)
        
        if not progress:
            return json.dumps({"error": f"Session {task_id} not found", "status": "not_found"})
        
        # 添加额外信息
        session = manager.get_session(task_id)
        if session:
            progress["created_at"] = session.created_at.isoformat() if session.created_at else None
            progress["updated_at"] = session.updated_at.isoformat() if session.updated_at else None
        
        return json.dumps(progress)
        
    except Exception as e:
        logger.exception("Error in acp_progress")
        return json.dumps({"error": str(e), "status": "error"})


def acp_result(task_id: str, wait: bool = True, timeout: float = None) -> str:
    """
    Handler for acp_result tool.
    
    获取任务结果，可选择等待完成。
    
    Args:
        task_id: 会话 ID
        wait: 是否等待完成（默认 True）
        timeout: 等待超时（秒），默认 120 秒
        
    Returns:
        JSON 字符串，包含任务结果
    """
    try:
        manager = get_session_manager()
        session = manager.get_session(task_id)
        
        if not session:
            return json.dumps({"error": f"Session {task_id} not found", "status": "not_found"})
        
        # 如果不需要等待，直接返回当前状态
        if not wait:
            return json.dumps(session.to_dict())
        
        # 等待完成
        effective_timeout = timeout or DEFAULT_TIMEOUT
        session = manager.wait_for_completion(task_id, timeout=effective_timeout)
        
        result = session.to_dict()
        
        # 根据状态添加额外信息
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
        logger.exception("Error in acp_result")
        return json.dumps({"error": str(e), "status": "error"})


def acp_cancel(task_id: str) -> str:
    """
    取消正在运行的任务。
    
    Args:
        task_id: 会话 ID
        
    Returns:
        JSON 字符串，包含取消结果
    """
    try:
        manager = get_session_manager()
        session = manager.get_session(task_id)
        
        if not session:
            return json.dumps({"error": f"Session {task_id} not found", "status": "not_found"})
        
        if session.status not in (SessionStatus.RUNNING, SessionStatus.PENDING):
            return json.dumps({
                "error": f"Cannot cancel session in {session.status.value} state",
                "status": "invalid_state"
            })
        
        manager.update_session(task_id, status=SessionStatus.CANCELLED)
        logger.info(f"Cancelled session {task_id}")
        
        return json.dumps({
            "sessionId": task_id,
            "status": "cancelled",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.exception("Error in acp_cancel")
        return json.dumps({"error": str(e), "status": "error"})


def acp_list(active_only: bool = True) -> str:
    """
    列出所有会话。
    
    Args:
        active_only: 是否只显示活跃会话（默认 True）
        
    Returns:
        JSON 字符串，包含会话列表
    """
    try:
        manager = get_session_manager()
        
        # ✅ 使用公开方法 list_sessions()，不直接访问私有属性
        session_ids = manager.list_sessions()
        
        result = []
        for session_id in session_ids:
            session = manager.get_session(session_id)
            if not session:
                continue
            if active_only and session.status not in (SessionStatus.RUNNING, SessionStatus.PENDING):
                continue
            
            result.append({
                "session_id": session_id,
                "status": session.status.value,
                "progress": session.progress,
                "prompt": session.prompt[:50] + "..." if session.prompt and len(session.prompt) > 50 else session.prompt,
                "created_at": session.created_at.isoformat() if session.created_at else None,
            })
        
        # 按创建时间排序
        result.sort(key=lambda x: x["created_at"] or "", reverse=True)
        
        return json.dumps({
            "sessions": result,
            "total": len(result),
            "active_only": active_only
        })
        
    except Exception as e:
        logger.exception("Error in acp_list")
        return json.dumps({"error": str(e), "status": "error"})


def acp_cleanup(max_age_hours: float = 24.0) -> str:
    """
    清理旧会话。
    
    Args:
        max_age_hours: 保留的最大年龄（小时），默认 24 小时
        
    Returns:
        JSON 字符串，包含清理结果
    """
    try:
        manager = get_session_manager()
        
        now = datetime.now()
        cleaned = []
        
        # ✅ 使用公开方法 list_sessions()，不直接访问私有属性
        all_sessions = manager.list_sessions()
        
        # 先收集要删除的 ID，再统一删除（避免迭代时修改字典）
        to_delete = []
        for session_id in all_sessions:
            session = manager.get_session(session_id)
            if session and session.created_at:
                age = now - session.created_at
                if age.total_seconds() > max_age_hours * 3600:
                    to_delete.append(session_id)
        
        # 统一删除
        for session_id in to_delete:
            manager.delete_session(session_id)
            cleaned.append(session_id)
        
        logger.info(f"Cleaned up {len(cleaned)} old sessions")
        
        return json.dumps({
            "cleaned_count": len(cleaned),
            "cleaned_sessions": cleaned,
            "max_age_hours": max_age_hours
        })
        
    except Exception as e:
        logger.exception("Error in acp_cleanup")
        return json.dumps({"error": str(e), "status": "error"})


def acp_shutdown(worker: str = None) -> str:
    """
    关闭 transport。
    
    Args:
        worker: 指定 worker，None 则关闭所有
        
    Returns:
        JSON 字符串，包含关闭结果
    """
    try:
        shutdown_transport(worker)
        return json.dumps({
            "status": "shutdown",
            "worker": worker or "all",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.exception("Error in acp_shutdown")
        return json.dumps({"error": str(e), "status": "error"})


def acp_worker_status() -> str:
    """
    获取所有 Worker 的状态信息。
    
    返回每个 Worker 的：
    - 状态（available/rate_limited/error/offline）
    - 使用的模型
    - 成功率
    - 平均响应时间
    - 速率限制重置时间
    
    Returns:
        JSON 字符串，包含所有 Worker 的状态摘要
    """
    try:
        from acp.worker_manager import get_worker_status
        return get_worker_status()
    except Exception as e:
        logger.exception("Error in acp_worker_status")
        return json.dumps({"error": str(e), "status": "error"})
