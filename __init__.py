# __init__.py
from .tools import acp_dispatch, acp_progress, acp_result
from .schemas import ACP_DISPATCH_SCHEMA, ACP_PROGRESS_SCHEMA, ACP_RESULT_SCHEMA

def register(ctx):
    """Register ACP client tools with Hermes."""
    ctx.register_tool(
        name="acp_dispatch",
        handler=acp_dispatch,
        schema=ACP_DISPATCH_SCHEMA
    )
    ctx.register_tool(
        name="acp_progress",
        handler=acp_progress,
        schema=ACP_PROGRESS_SCHEMA
    )
    ctx.register_tool(
        name="acp_result",
        handler=acp_result,
        schema=ACP_RESULT_SCHEMA
    )
