import unittest
import json
from acp.protocol import InitializeRequest, NewSessionRequest, PromptRequest, ACPMessage
from acp.session_manager import get_session_manager, SessionStatus
from tools import acp_dispatch, acp_progress, acp_result

class TestACPComponents(unittest.TestCase):
    def test_protocol_messages(self):
        init_req = InitializeRequest()
        self.assertEqual(init_req.method, "initialize")
        self.assertIn("capabilities", init_req.params)
        
        session_req = NewSessionRequest.create("test-session")
        self.assertEqual(session_req.method, "session/new")
        self.assertEqual(session_req.params["name"], "test-session")
        
        prompt_req = PromptRequest.create("sess-123", "hello")
        self.assertEqual(prompt_req.method, "session/prompt")
        self.assertEqual(prompt_req.params["sessionId"], "sess-123")
        self.assertEqual(prompt_req.params["prompt"], "hello")

    def test_session_manager(self):
        sm = get_session_manager()
        session = sm.create_session(prompt="test", session_id="sess-1")
        self.assertEqual(session.status, SessionStatus.PENDING)
        
        sm.update_session("sess-1", status=SessionStatus.RUNNING)
        self.assertEqual(sm.get_session("sess-1").status, SessionStatus.RUNNING)
        
        sm.update_session("sess-1", status=SessionStatus.COMPLETED, result="done")
        self.assertEqual(sm.get_session("sess-1").result, "done")
        
        sm.delete_session("sess-1")
        self.assertIsNone(sm.get_session("sess-1"))

if __name__ == "__main__":
    unittest.main()
