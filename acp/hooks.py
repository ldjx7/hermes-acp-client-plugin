"""
pre_llm_call 钩子 - 自动注入 ACP 任务进度到 Hermes 上下文

这个模块实现了 Hermes Agent 的 pre_llm_call 钩子，用于：
1. 检查是否有正在运行的 ACP 任务
2. 获取最新进度信息
3. 自动注入到用户消息上下文
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .session_manager import SessionStatus
from repositories import get_session_repository

logger = logging.getLogger(__name__)


class ProgressInjector:
    """
    进度注入器 - 在 LLM 调用前自动注入 ACP 任务进度
    """
    
    def __init__(self):
        self._repository = get_session_repository()
        self._injected_sessions: Dict[str, datetime] = {}
        self._injection_interval = timedelta(seconds=30)  # 最小注入间隔
        self._max_injected_sessions = 5  # 最多同时注入的会话数

    def pre_llm_call(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        在 LLM 调用前处理上下文，注入 ACP 任务进度
        
        Args:
            context: Hermes 上下文，包含 messages、tools 等
            
        Returns:
            更新后的上下文
        """
        # 获取正在运行的会话
        running_sessions = self._get_active_sessions()
        
        if not running_sessions:
            return context
        
        # 构建进度消息
        progress_message = self._build_progress_message(running_sessions)
        
        if progress_message:
            # 注入到系统消息或用户消息
            context = self._inject_message(context, progress_message)
            logger.info(f"Injected progress for {len(running_sessions)} session(s)")
        
        return context

    def _get_active_sessions(self) -> List[Dict]:
        """获取正在运行的会话列表"""
        active = []

        for session in self._repository.list_sessions():
            session_id = session.session_id
            if session.status in (SessionStatus.RUNNING, SessionStatus.PENDING):
                # 检查是否需要更新（避免过于频繁注入）
                last_injected = self._injected_sessions.get(session_id)
                if last_injected and datetime.now() - last_injected < self._injection_interval:
                    continue
                
                active.append({
                    "session_id": session_id,
                    "status": session.status.value,
                    "progress": session.progress,
                    "message": session.progress_message,
                    "prompt": session.prompt[:100] if session.prompt else None,
                    "created_at": session.created_at,
                })
        
        # 限制注入数量
        if len(active) > self._max_injected_sessions:
            active = active[:self._max_injected_sessions]
        
        return active

    def _build_progress_message(self, sessions: List[Dict]) -> Optional[str]:
        """构建进度消息"""
        if not sessions:
            return None
        
        lines = ["\n--- ACP 任务进度 ---"]
        
        for i, session in enumerate(sessions, 1):
            status_emoji = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌",
                "cancelled": "🚫"
            }.get(session["status"], "❓")
            
            progress_pct = int(session["progress"] * 100) if session["progress"] else 0
            
            lines.append(f"{status_emoji} 任务 {i}: {session['session_id']}")
            lines.append(f"   状态：{session['status']} | 进度：{progress_pct}%")
            
            if session["message"]:
                lines.append(f"   {session['message']}")
            
            if session["prompt"]:
                lines.append(f"   任务：{session['prompt']}...")
            
            # 更新注入时间
            self._injected_sessions[session["session_id"]] = datetime.now()
        
        lines.append("----------------------\n")
        
        return "\n".join(lines)

    def _inject_message(self, context: Dict[str, Any], message: str) -> Dict[str, Any]:
        """注入消息到上下文"""
        if "messages" not in context:
            context["messages"] = []

        # Replace previous ACP progress messages instead of stacking duplicates.
        messages = [
            existing
            for existing in context["messages"]
            if not (
                existing.get("role") == "system"
                and "ACP 任务进度" in existing.get("content", "")
            )
        ]

        messages.insert(0, {
            "role": "system",
            "content": message
        })

        context["messages"] = messages
        return context

    def clear_injection_history(self):
        """清除注入历史"""
        self._injected_sessions.clear()


# 全局单例
_injector: Optional[ProgressInjector] = None

def get_progress_injector() -> ProgressInjector:
    """获取进度注入器单例"""
    global _injector
    if _injector is None:
        _injector = ProgressInjector()
    return _injector


def pre_llm_call_hook(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hermes pre_llm_call 钩子函数
    
    在每次 LLM 调用前自动调用，注入 ACP 任务进度
    
    Usage in Hermes config:
        hooks:
          pre_llm_call: acp.hooks.pre_llm_call_hook
    """
    injector = get_progress_injector()
    return injector.pre_llm_call(context)


def register_hooks(ctx):
    """
    注册到 Hermes 钩子系统
    
    Usage:
        from acp.hooks import register_hooks
        register_hooks(hermes_context)
    """
    try:
        ctx.register_hook("pre_llm_call", pre_llm_call_hook)
        logger.info("ACP hooks registered successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to register ACP hooks: {e}")
        return False
