#!/usr/bin/env python3
"""
Tests for OpenACP integration.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add acp directory to path
acp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "acp")
sys.path.insert(0, acp_dir)

from openacp_bridge import (
    OpenACPBridge, 
    DaemonManager, 
    SessionRegistry, 
    ExceptionMapper,
    TaskResult,
    AgentError,
    AgentTimeoutError,
    AgentRateLimitError,
    AgentNotFoundError,
    AgentExecutionError,
    AgentServerError
)


class TestDaemonManager(unittest.TestCase):
    """Test DaemonManager class."""
    
    def test_init_default(self):
        """Test default initialization."""
        dm = DaemonManager()
        self.assertEqual(dm.base_url, "http://localhost:3000")
        self.assertEqual(dm.startup_timeout, 60)  # Updated: 30→60 for daemon startup
    
    def test_init_custom(self):
        """Test custom initialization."""
        dm = DaemonManager(base_url="http://custom:8080", startup_timeout=60)
        self.assertEqual(dm.base_url, "http://custom:8080")
        self.assertEqual(dm.startup_timeout, 60)
    
    @patch("openacp_bridge.requests.Session.get")
    def test_health_check_success(self, mock_get):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        dm = DaemonManager()
        self.assertTrue(dm.health_check())
    
    @patch("openacp_bridge.requests.get")
    def test_health_check_failure(self, mock_get):
        """Test failed health check."""
        mock_get.side_effect = Exception("Connection refused")
        dm = DaemonManager()
        self.assertFalse(dm.health_check())


class TestSessionRegistry(unittest.TestCase):
    """Test SessionRegistry class."""
    
    def test_register_and_get(self):
        """Test registering and retrieving session."""
        registry = SessionRegistry()
        registry.register("task1", "session1")
        self.assertEqual(registry.get_session("task1"), "session1")
    
    def test_unregister(self):
        """Test unregistering session."""
        registry = SessionRegistry()
        registry.register("task1", "session1")
        registry.unregister("task1")
        self.assertIsNone(registry.get_session("task1"))
    
    def test_get_nonexistent(self):
        """Test getting nonexistent session."""
        registry = SessionRegistry()
        self.assertIsNone(registry.get_session("nonexistent"))


class TestExceptionMapper(unittest.TestCase):
    """Test ExceptionMapper class."""
    
    def test_timeout_error(self):
        """Test timeout error mapping."""
        exc = ExceptionMapper.map_error("Request timeout", 408)
        self.assertIsInstance(exc, AgentTimeoutError)
    
    def test_rate_limit_error(self):
        """Test rate limit error mapping."""
        exc = ExceptionMapper.map_error("Rate limit exceeded", 429)
        self.assertIsInstance(exc, AgentRateLimitError)
    
    def test_not_found_error(self):
        """Test not found error mapping."""
        exc = ExceptionMapper.map_error("Session not found", 404)
        self.assertIsInstance(exc, AgentNotFoundError)
    
    def test_server_error(self):
        """Test server error mapping."""
        exc = ExceptionMapper.map_error("Internal error", 500)
        self.assertIsInstance(exc, AgentServerError)
    
    def test_default_error(self):
        """Test default error mapping."""
        exc = ExceptionMapper.map_error("Unknown error")
        self.assertIsInstance(exc, AgentExecutionError)


class TestTaskResult(unittest.TestCase):
    """Test TaskResult dataclass."""
    
    def test_success_result(self):
        """Test successful task result."""
        result = TaskResult(
            task_id="task1",
            session_id="session1",
            status="success",
            output="Hello World"
        )
        self.assertEqual(result.status, "success")
        self.assertEqual(result.output, "Hello World")
        self.assertIsNone(result.error)
    
    def test_error_result(self):
        """Test error task result."""
        result = TaskResult(
            task_id="task1",
            session_id="",
            status="error",
            error="Something went wrong"
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error, "Something went wrong")
        self.assertIsNone(result.output)


class TestOpenACPBridge(unittest.TestCase):
    """Test OpenACPBridge class."""
    
    @patch("openacp_bridge.DaemonManager")
    def test_init(self, mock_dm):
        """Test bridge initialization."""
        bridge = OpenACPBridge(base_url="http://test:3000")
        self.assertEqual(bridge.base_url, "http://test:3000")
        self.assertIsInstance(bridge.session_registry, SessionRegistry)
    
    @patch("openacp_bridge.requests.Session.post")
    @patch("openacp_bridge.DaemonManager.ensure_running")
    def test_dispatch_success(self, mock_ensure, mock_post):
        """Test successful dispatch."""
        mock_ensure.return_value = True
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {
            "sessionId": "session1",
            "output": "Result"
        }
        
        bridge = OpenACPBridge()
        result = bridge.dispatch("gemini", "Hello")
        
        self.assertEqual(result.status, "success")
        self.assertEqual(result.session_id, "session1")
        self.assertEqual(result.output, "Result")


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDaemonManager))
    suite.addTests(loader.loadTestsFromTestCase(TestSessionRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestExceptionMapper))
    suite.addTests(loader.loadTestsFromTestCase(TestTaskResult))
    suite.addTests(loader.loadTestsFromTestCase(TestOpenACPBridge))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
