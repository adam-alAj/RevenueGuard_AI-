"""Agent API endpoints — dev-gated smoke test and execution audit.

Endpoints:
- POST /api/v1/agents/smoke-test — Run the smoke test agent against live Gemini
- GET /api/v1/agents/executions — List tool execution audit records
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.gemini_client import GeminiClientError
from app.agents.smoke_test_agent import create_smoke_test_agent
from app.agents.tools.base import get_tool_execution_log
from app.core.config import Settings, get_settings
from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


class SmokeTestRequest(BaseModel):
    """Request body for the smoke test endpoint."""

    message: str = "Please greet RevenueGuard AI"


class SmokeTestResponse(BaseModel):
    """Response from the smoke test agent."""

    response_text: str
    agent_name: str
    model: str
    tool_called: bool
    tool_execution_id: str | None = None


class ToolExecutionResponse(BaseModel):
    """A single tool execution audit record."""

    execution_id: str
    tool_name: str
    agent_name: str
    organization_id: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    created_at: float


@router.post("/smoke-test", response_model=SmokeTestResponse)
async def run_smoke_test(
    request: SmokeTestRequest,
    settings: Settings = Depends(get_settings),
    _user: Any = Depends(require_permission("agents", "execute")),
) -> SmokeTestResponse:
    """Run the smoke test agent against live Gemini.

    This endpoint is intended for development and verification only.
    It creates a trivial agent, sends the provided message, and returns
    the response along with tool execution details.
    """
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=403,
            detail="Smoke test endpoint is not available in production.",
        )

    try:
        agent = create_smoke_test_agent(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
        )
    except GeminiClientError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    try:
        response = await agent.run(request.message)
        response_text = response.text or ""
    except Exception as e:
        logger.error("Smoke test agent failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Agent execution failed: {type(e).__name__}: {e}",
        ) from e

    # Check if a tool was called
    executions = get_tool_execution_log()
    last_execution = executions[-1] if executions else None
    tool_called = last_execution is not None and last_execution.tool_name == "smoke_test_greet"

    return SmokeTestResponse(
        response_text=response_text,
        agent_name="smoke-test-agent",
        model=settings.GEMINI_MODEL,
        tool_called=tool_called,
        tool_execution_id=last_execution.execution_id if last_execution else None,
    )


@router.get("/executions", response_model=list[ToolExecutionResponse])
async def list_executions(
    limit: int = 50,
    _user: Any = Depends(require_permission("agents", "read")),
) -> list[ToolExecutionResponse]:
    """List tool execution audit records.

    Returns the most recent tool executions, newest first.
    """
    executions = get_tool_execution_log()
    # Return newest first, limited
    recent = list(reversed(executions[-limit:]))
    return [
        ToolExecutionResponse(
            execution_id=e.execution_id,
            tool_name=e.tool_name,
            agent_name=e.agent_name,
            organization_id=e.organization_id,
            arguments=e.arguments,
            result=e.result,
            error=e.error,
            duration_ms=e.duration_ms,
            created_at=e.created_at,
        )
        for e in recent
    ]
