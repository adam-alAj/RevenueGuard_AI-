"""Tool scaffold with tenant-scope injection, authorization, and audit logging.

Every RevenueGuard AI tool inherits from TenantScopedTool which:
1. Injects organization_id from the calling context (never from LLM args)
2. Checks the calling agent's permitted-tool list before dispatch
3. Writes a ToolExecution audit row on every call
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agent_framework import tool

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    """Context injected into every tool call by the scaffold.

    The organization_id is always derived server-side from the authenticated
    JWT session — it is NEVER accepted from LLM-provided arguments.
    """

    organization_id: str
    user_id: str
    agent_name: str
    permitted_tools: list[str] = field(default_factory=list)
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ToolAuthorizationError(Exception):
    """Raised when an agent attempts to call a tool it is not authorized for."""


class ToolExecutionRecord:
    """Record of a tool execution for audit logging."""

    def __init__(
        self,
        execution_id: str,
        tool_name: str,
        agent_name: str,
        organization_id: str,
        arguments: dict[str, Any],
        result: Any = None,
        error: str | None = None,
        duration_ms: float = 0.0,
    ) -> None:
        self.execution_id = execution_id
        self.tool_name = tool_name
        self.agent_name = agent_name
        self.organization_id = organization_id
        self.arguments = arguments
        self.result = result
        self.error = error
        self.duration_ms = duration_ms
        self.created_at = time.time()


# Global audit log for tool executions (in-memory for now; DB-backed in Phase 8)
_tool_execution_log: list[ToolExecutionRecord] = []


def get_tool_execution_log() -> list[ToolExecutionRecord]:
    """Return the in-memory tool execution log."""
    return _tool_execution_log


def clear_tool_execution_log() -> None:
    """Clear the in-memory tool execution log (for testing)."""
    _tool_execution_log.clear()


def authorize_tool_call(tool_name: str, ctx: ToolContext) -> None:
    """Check if the agent is authorized to call the given tool.

    Args:
        tool_name: The name of the tool being called.
        ctx: The tool context with permitted_tools list.

    Raises:
        ToolAuthorizationError: If the tool is not in the permitted list.
    """
    if ctx.permitted_tools and tool_name not in ctx.permitted_tools:
        raise ToolAuthorizationError(
            f"Agent '{ctx.agent_name}' is not authorized to call tool '{tool_name}'. "
            f"Permitted tools: {ctx.permitted_tools}"
        )


def sanitize_arguments(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    """Remove organization_id from LLM-provided arguments and inject from context.

    This prevents the LLM from forging or overriding the tenant scope.

    Args:
        arguments: Raw arguments from the LLM.
        ctx: The tool context with the real organization_id.

    Returns:
        Sanitized arguments with organization_id from context.
    """
    sanitized = {k: v for k, v in arguments.items() if k != "organization_id"}
    sanitized["organization_id"] = ctx.organization_id
    return sanitized


def create_tenant_scoped_tool(
    name: str,
    description: str,
    func: Callable[..., Any],
) -> Any:
    """Wrap a function as a tenant-scoped tool with authorization and audit logging.

    The wrapped function receives sanitized arguments with organization_id
    injected from the context, and a ToolExecution audit row is written
    on every call.

    Args:
        name: Tool name (must match the function name for LLM clarity).
        description: Tool description visible to the LLM.
        func: The actual tool function. Its first argument should be
              'organization_id' which will be injected automatically.

    Returns:
        A FunctionTool decorated with @tool.
    """
    import functools

    @functools.wraps(func)
    async def wrapped_func(**kwargs: Any) -> Any:
        # Extract context (injected by the scaffold, not by the LLM)
        ctx: ToolContext = kwargs.pop("_tool_context")
        args_for_func = sanitize_arguments(kwargs, ctx)

        # Authorize and execute with audit logging
        start_time = time.time()
        result = None
        error_msg = None
        try:
            authorize_tool_call(name, ctx)
            result = await func(**args_for_func)
        except Exception as e:
            error_msg = str(e)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            record = ToolExecutionRecord(
                execution_id=ctx.execution_id,
                tool_name=name,
                agent_name=ctx.agent_name,
                organization_id=ctx.organization_id,
                arguments=args_for_func,
                result=result,
                error=error_msg,
                duration_ms=duration_ms,
            )
            _tool_execution_log.append(record)
            logger.info(
                "Tool execution: %s by agent %s in org %s (%.1fms) %s",
                name,
                ctx.agent_name,
                ctx.organization_id,
                duration_ms,
                "ERROR: " + error_msg if error_msg else "OK",
            )

        return result

    @tool(name=name, description=description)
    async def tool_func(**kwargs: Any) -> Any:
        return await wrapped_func(**kwargs)

    return tool_func
