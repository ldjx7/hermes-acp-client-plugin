"""
OpenACP Daemon Manager
Manages the lifecycle of OpenACP daemon process.
"""

import subprocess
import time
import os
import logging
import shutil
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class DaemonManager:
    """
    Manages OpenACP daemon lifecycle.
    
    Automatically starts daemon if not running, supports external daemon URL.
    """
    
    DEFAULT_BASE_URL = "http://localhost:3000"
    HEALTH_ENDPOINT = "/api/health"
    STARTUP_TIMEOUT = 60  # 增加到 60 秒，给 daemon 更长的启动时间
    HEALTH_CHECK_INTERVAL = 2  # 增加到 2 秒，减少轮询频率
    HEALTH_CHECK_TIMEOUT = 5  # 增加到 5 秒，避免网络波动导致误判
    
    def __init__(self, base_url: str = None, startup_timeout: int = None):
        """
        Initialize DaemonManager.
        
        Args:
            base_url: OpenACP daemon URL. Defaults to OPENACP_DAEMON_URL env var
                     or http://localhost:3000
            startup_timeout: Seconds to wait for daemon to start (default: 30)
        """
        # 修复：正确处理传入 0 或空字符串等 falsy 值的情况
        self.base_url = base_url if base_url is not None else os.environ.get(
            "OPENACP_DAEMON_URL", 
            self.DEFAULT_BASE_URL
        )
        self.startup_timeout = startup_timeout if startup_timeout is not None else self.STARTUP_TIMEOUT
        
        self._process: Optional[subprocess.Popen] = None
        # 使用 Session，提升连接性能（Keep-Alive），也方便测试 mock
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Hermes-ACP-Plugin"})
    
    def ensure_running(self) -> bool:
        """
        Ensure OpenACP daemon is running.
        
        Starts daemon automatically if not running.
        
        Returns:
            True if daemon is running and healthy, False otherwise
        """
        if self.health_check():
            logger.info("OpenACP daemon is already running")
            return True
            
        logger.info("OpenACP daemon not running, attempting to start...")
        if self.start_daemon():
            start_time = time.time()
            
            # 修复：使用真实的时钟时间计算超时，而不是循环次数
            while time.time() - start_time < self.startup_timeout:
                if self.health_check():
                    logger.info("OpenACP daemon started successfully")
                    return True
                
                # 修复：检查子进程是否已经崩溃退出，避免无意义的等待
                if self._process and self._process.poll() is not None:
                    logger.error(f"OpenACP daemon process exited prematurely with return code {self._process.returncode}")
                    return False
                    
                time.sleep(self.HEALTH_CHECK_INTERVAL)
                
            logger.error("Timeout waiting for OpenACP daemon to start")
        return False
    
    def health_check(self) -> bool:
        """
        Check if OpenACP daemon is healthy.
        
        Returns:
            True if daemon responds to health check, False otherwise
        """
        try:
            # 修复：缩短检查的超时时间，以免阻塞整个检查循环
            response = self.session.get(
                f"{self.base_url}{self.HEALTH_ENDPOINT}", 
                timeout=self.HEALTH_CHECK_TIMEOUT
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            # 修复：精确捕获 requests 异常，并在 debug 级别记录日志
            logger.debug(f"Health check failed: {e}")
            return False
        except Exception as e:
            logger.debug(f"Health check error: {e}")
            return False
    
    def start_daemon(self) -> bool:
        """
        Start OpenACP daemon in background.
        
        Returns:
            True if daemon process started, False if failed
        """
        try:
            executable = shutil.which("openacp")
            if not executable:
                logger.error("openacp executable not found in PATH. Please install: npm install -g @openacp/cli")
                return False
            
            # 修复：将输入输出重定向到 DEVNULL，防止污染父进程终端
            self._process = subprocess.Popen(
                [executable, "start", "--daemon"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            logger.info(f"Started OpenACP daemon (PID: {self._process.pid})")
            return True
            
        except Exception as e:
            # 修复：捕获明确的 Exception 而不是裸 except，并打印堆栈追踪
            logger.exception(f"Failed to start OpenACP daemon process: {e}")
            return False
    
    def is_running(self) -> bool:
        """
        Check if OpenACP daemon is running.
        
        Returns:
            True if daemon is running, False otherwise
        """
        return self.health_check()
    
    def stop_daemon(self) -> None:
        """
        Stop OpenACP daemon if started by this manager.
        """
        if self._process and self._process.poll() is None:
            logger.info("Terminating OpenACP daemon process...")
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
                logger.info("OpenACP daemon terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("OpenACP daemon did not terminate gracefully, killing...")
                self._process.kill()
                self._process.wait()
            self._process = None
    
    def __del__(self):
        """Cleanup when object is garbage collected."""
        try:
            if self._process:
                self.stop_daemon()
        except Exception:
            pass


# Singleton instance for convenience
_default_manager: Optional[DaemonManager] = None


def get_daemon_manager() -> DaemonManager:
    """Get default DaemonManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = DaemonManager()
    return _default_manager


def ensure_daemon_running() -> bool:
    """Ensure OpenACP daemon is running using default manager."""
    return get_daemon_manager().ensure_running()
