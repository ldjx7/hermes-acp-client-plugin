# __init__.py
from .tools import (
    acp_dispatch,
    acp_progress,
    acp_result,
    acp_cancel,
    acp_list,
    acp_cleanup,
    acp_shutdown,
)
from .schemas import (
    ACP_DISPATCH_SCHEMA,
    ACP_PROGRESS_SCHEMA,
    ACP_RESULT_SCHEMA,
    ACP_CANCEL_SCHEMA,
    ACP_LIST_SCHEMA,
    ACP_CLEANUP_SCHEMA,
    ACP_SHUTDOWN_SCHEMA,
)


REGISTERED_TOOLS = (
    ("acp_dispatch", acp_dispatch, ACP_DISPATCH_SCHEMA),
    ("acp_progress", acp_progress, ACP_PROGRESS_SCHEMA),
    ("acp_result", acp_result, ACP_RESULT_SCHEMA),
    ("acp_cancel", acp_cancel, ACP_CANCEL_SCHEMA),
    ("acp_list", acp_list, ACP_LIST_SCHEMA),
    ("acp_cleanup", acp_cleanup, ACP_CLEANUP_SCHEMA),
    ("acp_shutdown", acp_shutdown, ACP_SHUTDOWN_SCHEMA),
)

def register(ctx):
    """Register ACP client tools with Hermes."""
    for name, handler, schema in REGISTERED_TOOLS:
        ctx.register_tool(name=name, handler=handler, schema=schema)
