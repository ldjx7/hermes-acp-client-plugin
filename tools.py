from services.dispatch_service import get_dispatch_service
from services.progress_service import get_progress_service
from services.result_service import get_result_service


def handle_notification(data):
    """Callback for ACP notifications."""
    return get_dispatch_service().handle_notification(data)


def ensure_initialized(worker: str = "gemini", **kwargs) -> bool:
    """
    Ensure transport is initialized with retry logic.
    
    Args:
        worker: Worker name (gemini/claude/codex)
        **kwargs: Additional transport config (max_retries, retry_delay, request_timeout)
    """
    return get_dispatch_service().ensure_initialized(worker=worker, **kwargs)


def acp_dispatch(task: str, context: dict = None, worker: str = "gemini", 
                 timeout: float = None, max_retries: int = None) -> str:
    """
    Handler for acp_dispatch tool.
    
    派发任务到 ACP worker，支持多平台和错误重试。
    
    Args:
        task: 任务描述
        context: 额外上下文（可选）
        worker: worker 平台 (gemini/claude/codex)，默认 gemini
        timeout: 请求超时（秒）
        max_retries: 最大重试次数
        
    Returns:
        JSON 字符串，包含 sessionId 和状态，或错误信息
    """
    return get_dispatch_service().dispatch(
        task=task,
        context=context,
        worker=worker,
        timeout=timeout,
        max_retries=max_retries,
    )


def acp_progress(task_id: str) -> str:
    """
    Handler for acp_progress tool.
    
    查询任务进度。
    
    Args:
        task_id: 会话 ID
        
    Returns:
        JSON 字符串，包含进度信息
    """
    return get_progress_service().get_progress(task_id)


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
    return get_result_service().get_result(task_id, wait=wait, timeout=timeout)


def acp_cancel(task_id: str) -> str:
    """
    取消正在运行的任务。
    
    Args:
        task_id: 会话 ID
        
    Returns:
        JSON 字符串，包含取消结果
    """
    return get_result_service().cancel(task_id)


def acp_list(active_only: bool = True) -> str:
    """
    列出所有会话。
    
    Args:
        active_only: 是否只显示活跃会话（默认 True）
        
    Returns:
        JSON 字符串，包含会话列表
    """
    return get_progress_service().list_sessions(active_only=active_only)


def acp_cleanup(max_age_hours: float = 24.0) -> str:
    """
    清理旧会话。
    
    Args:
        max_age_hours: 保留的最大年龄（小时），默认 24 小时
        
    Returns:
        JSON 字符串，包含清理结果
    """
    return get_progress_service().cleanup(max_age_hours=max_age_hours)


def acp_shutdown(worker: str = None) -> str:
    """
    关闭 transport。
    
    Args:
        worker: 指定 worker，None 则关闭所有
        
    Returns:
        JSON 字符串，包含关闭结果
    """
    return get_dispatch_service().shutdown(worker=worker)
