import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Union
from enum import Enum

class MessageType(Enum):
    INITIALIZE = "initialize"
    SESSION_NEW = "session/new"
    SESSION_PROMPT = "session/prompt"
    SESSION_STATE = "session/state"

@dataclass
class ACPMessage:
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            d["id"] = self.id
        if self.method is not None:
            d["method"] = self.method
        if self.params is not None:
            d["params"] = self.params
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

@dataclass
class InitializeRequest(ACPMessage):
    method: str = "initialize"
    params: Dict[str, Any] = field(default_factory=lambda: {
        "protocolVersion": 1,  # Qwen expects a number, not string
        "capabilities": {},
        "clientInfo": {"name": "hermes-acp-client-plugin", "version": "0.2.1"}
    })

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())

@dataclass
class NewSessionRequest(ACPMessage):
    method: str = "session/new"
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, name: str = "default", cwd: str = None, mcp_servers: list = None) -> 'NewSessionRequest':
        import os
        params = {
            "name": name,
            "cwd": cwd or os.getcwd(),
            "mcpServers": mcp_servers or []
        }
        return cls(params=params, id=str(uuid.uuid4()))

@dataclass
class PromptRequest(ACPMessage):
    method: str = "session/prompt"
    params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, session_id: str, prompt: str, system_prompt: str = None) -> 'PromptRequest':
        # Qwen expects prompt as an array with specific structure
        # Each message needs type field and content fields
        messages = [{
            "type": "text",
            "text": prompt
        }]
        
        params = {
            "sessionId": session_id,
            "prompt": messages
        }
        
        if system_prompt:
            params["systemPrompt"] = system_prompt
        
        return cls(params=params, id=str(uuid.uuid4()))
