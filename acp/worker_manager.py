#!/usr/bin/env python3
"""
Worker Manager - 管理多个 ACP Worker 的状态和故障转移

功能:
- 获取 Worker 信息 (模型、速率限制、使用状态)
- 监控 Worker 健康状态
- 自动故障转移 (速率限制时切换到备用 Worker)
- 负载均衡
"""

import json
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class WorkerStatus(Enum):
    """Worker 状态"""
    AVAILABLE = "available"
    BUSY = "busy"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    OFFLINE = "offline"


@dataclass
class WorkerInfo:
    """Worker 信息"""
    name: str
    status: WorkerStatus = WorkerStatus.AVAILABLE
    model: Optional[str] = None
    last_used: Optional[datetime] = None
    total_requests: int = 0
    failed_requests: int = 0
    rate_limit_reset: Optional[datetime] = None
    error_message: Optional[str] = None
    avg_response_time: float = 0.0
    _response_times: List[float] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "model": self.model,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": round((1 - self.failed_requests / max(self.total_requests, 1)) * 100, 1),
            "avg_response_time": round(self.avg_response_time, 2),
            "rate_limit_reset": self.rate_limit_reset.isoformat() if self.rate_limit_reset else None,
            "error_message": self.error_message,
        }


class WorkerManager:
    """
    Worker 管理器
    
    管理多个 ACP Worker 的状态，支持自动故障转移和负载均衡。
    """
    
    def __init__(self):
        self._workers: Dict[str, WorkerInfo] = {}
        self._default_worker = "gemini"
        self._fallback_order = ["gemini", "claude", "codex", "qwen"]
        self._rate_limit_cooldown = 60  # 速率限制后冷却时间 (秒)
        
        # 初始化已知 Worker
        for worker_name in self._fallback_order:
            self._workers[worker_name] = WorkerInfo(name=worker_name)
    
    def register_worker(self, name: str, model: str = None):
        """注册 Worker"""
        if name not in self._workers:
            self._workers[name] = WorkerInfo(name=name, model=model)
            self._fallback_order.append(name)
        elif model:
            self._workers[name].model = model
        logger.info(f"Registered worker: {name} (model: {model or 'unknown'})")
    
    def get_available_worker(self, exclude: List[str] = None) -> Optional[str]:
        """
        获取可用的 Worker
        
        Args:
            exclude: 排除的 Worker 列表
        
        Returns:
            可用的 Worker 名称，如果没有则返回 None
        """
        exclude = exclude or []
        
        for worker_name in self._fallback_order:
            if worker_name in exclude:
                continue
            
            worker = self._workers.get(worker_name)
            if not worker:
                continue
            
            # 检查状态
            if worker.status == WorkerStatus.OFFLINE:
                continue
            
            # 检查速率限制
            if worker.status == WorkerStatus.RATE_LIMITED:
                if worker.rate_limit_reset and datetime.now() < worker.rate_limit_reset:
                    continue
                else:
                    # 冷却时间已过，重置状态
                    worker.status = WorkerStatus.AVAILABLE
                    worker.rate_limit_reset = None
            
            return worker_name
        
        return None
    
    def mark_success(self, worker: str, response_time: float, model: str = None):
        """标记请求成功"""
        if worker not in self._workers:
            return
        
        info = self._workers[worker]
        info.total_requests += 1
        info.last_used = datetime.now()
        info.status = WorkerStatus.AVAILABLE
        
        if model:
            info.model = model
        
        # 更新平均响应时间
        info._response_times.append(response_time)
        if len(info._response_times) > 100:
            info._response_times = info._response_times[-100:]
        info.avg_response_time = sum(info._response_times) / len(info._response_times)
        
        logger.debug(f"Worker {worker} success (response_time: {response_time:.2f}s)")
    
    def mark_error(self, worker: str, error: str, is_rate_limit: bool = False):
        """
        标记请求错误
        
        Args:
            worker: Worker 名称
            error: 错误信息
            is_rate_limit: 是否为速率限制错误
        """
        if worker not in self._workers:
            return
        
        info = self._workers[worker]
        info.total_requests += 1
        info.failed_requests += 1
        info.error_message = error
        
        if is_rate_limit:
            info.status = WorkerStatus.RATE_LIMITED
            info.rate_limit_reset = datetime.now() + timedelta(seconds=self._rate_limit_cooldown)
            logger.warning(f"Worker {worker} rate limited. Cooldown until {info.rate_limit_reset}")
        else:
            info.status = WorkerStatus.ERROR
            logger.error(f"Worker {worker} error: {error}")
    
    def mark_offline(self, worker: str):
        """标记 Worker 离线"""
        if worker not in self._workers:
            return
        
        self._workers[worker].status = WorkerStatus.OFFLINE
        logger.warning(f"Worker {worker} marked as offline")
    
    def get_worker_info(self, worker: str) -> Optional[Dict[str, Any]]:
        """获取 Worker 信息"""
        if worker not in self._workers:
            return None
        return self._workers[worker].to_dict()
    
    def get_all_workers(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Worker 信息"""
        return {name: info.to_dict() for name, info in self._workers.items()}
    
    def get_status_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        available = [w for w in self._workers.values() if w.status == WorkerStatus.AVAILABLE]
        rate_limited = [w for w in self._workers.values() if w.status == WorkerStatus.RATE_LIMITED]
        offline = [w for w in self._workers.values() if w.status == WorkerStatus.OFFLINE]
        
        return {
            "total_workers": len(self._workers),
            "available": len(available),
            "rate_limited": len(rate_limited),
            "offline": len(offline),
            "recommended_worker": self.get_available_worker(),
            "workers": self.get_all_workers(),
        }
    
    def get_available_models(self) -> Dict[str, Optional[str]]:
        """
        获取所有可用 Worker 的模型信息
        
        Returns:
            字典 {worker_name: model_name}
        """
        return {
            name: info.model 
            for name, info in self._workers.items()
            if info.status == WorkerStatus.AVAILABLE
        }
    
    def is_rate_limit_error(self, error_message: str) -> bool:
        """
        判断是否为速率限制错误
        
        常见速率限制错误:
        - 429 Too Many Requests
        - Rate limit exceeded
        - Quota exceeded
        - Resource exhausted
        """
        error_lower = error_message.lower()
        rate_limit_indicators = [
            "rate limit",
            "too many requests",
            "quota exceeded",
            "resource exhausted",
            "429",
            "throttl",
        ]
        
        return any(indicator in error_lower for indicator in rate_limit_indicators)
    
    def dispatch_with_fallback(
        self,
        task: str,
        preferred_worker: str = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        派发任务，支持自动故障转移
        
        Args:
            task: 任务描述
            preferred_worker: 首选 Worker
            max_retries: 最大重试次数
            **kwargs: 传递给 acp_dispatch 的参数
        
        Returns:
            派发结果
        """
        from tools import acp_dispatch
        
        exclude = []
        attempts = 0
        
        while attempts < max_retries:
            # 选择 Worker
            if preferred_worker and preferred_worker not in exclude:
                worker = preferred_worker
            else:
                worker = self.get_available_worker(exclude)
                if not worker:
                    return {
                        "error": "No available workers",
                        "status": "failed",
                        "worker_status": self.get_status_summary(),
                    }
            
            logger.info(f"Attempting dispatch to {worker} (attempt {attempts + 1}/{max_retries})")
            
            # 派发任务
            result_str = acp_dispatch(task=task, worker=worker, **kwargs)
            result = json.loads(result_str)
            
            # 检查是否成功
            if "sessionId" in result and "error" not in result:
                self.mark_success(worker, kwargs.get("timeout", 120))
                result["worker"] = worker
                result["attempt"] = attempts + 1
                return result
            
            # 失败处理
            error = result.get("error", "Unknown error")
            is_rate_limit = self.is_rate_limit_error(error)
            
            self.mark_error(worker, error, is_rate_limit)
            exclude.append(worker)
            attempts += 1
            
            if is_rate_limit:
                logger.warning(f"Rate limit on {worker}, trying next available worker...")
            else:
                logger.warning(f"Error on {worker}: {error}")
        
        # 所有尝试都失败
        return {
            "error": f"Failed after {max_retries} attempts",
            "status": "failed",
            "last_error": error,
            "worker_status": self.get_status_summary(),
        }


# 全局 Worker 管理器实例
_manager: Optional[WorkerManager] = None


def get_worker_manager() -> WorkerManager:
    """获取全局 Worker 管理器"""
    global _manager
    if _manager is None:
        _manager = WorkerManager()
    return _manager


def initialize_workers():
    """初始化 Worker 信息"""
    manager = get_worker_manager()
    
    # 注册已知 Worker 和模型
    manager.register_worker("gemini", "gemini-2.5-flash")
    manager.register_worker("claude", "claude-sonnet-4")
    manager.register_worker("codex", "codex-1")
    manager.register_worker("qwen", "qwen3.5-plus")
    
    logger.info("Worker manager initialized")


def get_worker_status() -> str:
    """获取 Worker 状态（用于工具调用）"""
    manager = get_worker_manager()
    summary = manager.get_status_summary()
    summary["available_models"] = manager.get_available_models()
    return json.dumps(summary, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    manager = WorkerManager()
    
    # 模拟请求
    manager.mark_success("gemini", 15.5, "gemini-2.5-flash")
    manager.mark_success("gemini", 12.3)
    manager.mark_error("qwen", "Rate limit exceeded", is_rate_limit=True)
    
    print("\nWorker Status:")
    print(json.dumps(manager.get_status_summary(), indent=2))
