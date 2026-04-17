from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WorkerCapabilities:
    supports_cancel: bool = False
    supports_stream_updates: bool = False


@dataclass(frozen=True)
class WorkerAdapter:
    name: str
    command: List[str]
    capabilities: WorkerCapabilities = field(default_factory=WorkerCapabilities)

    def build_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        prompt = task
        if context:
            prompt += f"\n\nContext:\n{json.dumps(context, indent=2, default=str)}"
        return prompt

    def normalize_prompt_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return response

    def get_cancel_handler(self, transport):
        if not self.capabilities.supports_cancel:
            return None

        for attr_name in ("cancel_session", "cancel"):
            handler = getattr(transport, attr_name, None)
            if callable(handler):
                return handler
        return None
