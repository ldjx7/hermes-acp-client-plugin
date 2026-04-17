from __future__ import annotations

from typing import Dict

from .base import WorkerAdapter, WorkerCapabilities


DEFAULT_WORKER = "gemini"

_WORKER_ADAPTERS: Dict[str, WorkerAdapter] = {
    "gemini": WorkerAdapter(
        name="gemini",
        command=["gemini", "--acp"],
        capabilities=WorkerCapabilities(supports_cancel=False, supports_stream_updates=False),
    ),
    "claude": WorkerAdapter(
        name="claude",
        command=["claude", "--acp"],
        capabilities=WorkerCapabilities(supports_cancel=False, supports_stream_updates=False),
    ),
    "codex": WorkerAdapter(
        name="codex",
        command=["codex", "--acp"],
        capabilities=WorkerCapabilities(supports_cancel=False, supports_stream_updates=False),
    ),
    "qwen": WorkerAdapter(
        name="qwen",
        command=["qwen", "--acp"],
        capabilities=WorkerCapabilities(supports_cancel=False, supports_stream_updates=True),
    ),
}


def get_worker_adapter(worker_name: str) -> WorkerAdapter:
    worker_key = (worker_name or DEFAULT_WORKER).lower()
    return _WORKER_ADAPTERS.get(worker_key, _WORKER_ADAPTERS[DEFAULT_WORKER])


def get_worker_adapters() -> Dict[str, WorkerAdapter]:
    return dict(_WORKER_ADAPTERS)
