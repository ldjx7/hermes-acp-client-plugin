# schemas.py - ACP Client Plugin Tool Schemas

ACP_DISPATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "Task description to be dispatched to ACP worker"
        },
        "context": {
            "type": "object",
            "description": "Additional context for the task (files, constraints, etc.)",
            "properties": {
                "files": {"type": "array", "items": {"type": "string"}},
                "constraints": {"type": "string"},
                "examples": {"type": "array", "items": {"type": "string"}}
            }
        },
        "worker": {
            "type": "string",
            "enum": ["gemini", "claude", "codex", "qwen"],
            "description": "The platform worker to use for this task",
            "default": "gemini"
        },
        "timeout": {
            "type": "number",
            "description": "Request timeout in seconds",
            "default": 120
        },
        "max_retries": {
            "type": "integer",
            "description": "Maximum retry attempts on failure",
            "default": 3,
            "minimum": 0,
            "maximum": 10
        }
    },
    "required": ["task"]
}

ACP_PROGRESS_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "ID of the session/task to check progress"
        }
    },
    "required": ["task_id"]
}

ACP_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "ID of the session/task to get result"
        },
        "wait": {
            "type": "boolean",
            "description": "Whether to wait for completion",
            "default": True
        },
        "timeout": {
            "type": "number",
            "description": "Timeout in seconds when waiting",
            "default": 120
        }
    },
    "required": ["task_id"]
}

ACP_CANCEL_SCHEMA = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "string",
            "description": "ID of the session/task to cancel"
        }
    },
    "required": ["task_id"]
}

ACP_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "active_only": {
            "type": "boolean",
            "description": "Show only active (running/pending) sessions",
            "default": True
        }
    }
}

ACP_CLEANUP_SCHEMA = {
    "type": "object",
    "properties": {
        "max_age_hours": {
            "type": "number",
            "description": "Maximum age of sessions to keep (hours)",
            "default": 24,
            "minimum": 1
        }
    }
}

ACP_SHUTDOWN_SCHEMA = {
    "type": "object",
    "properties": {
        "worker": {
            "type": "string",
            "enum": ["gemini", "claude", "codex", "qwen"],
            "description": "Specific worker to shutdown (omit to shutdown all)"
        }
    }
}

ACP_WORKER_STATUS_SCHEMA = {
    "type": "object",
    "properties": {}
}
