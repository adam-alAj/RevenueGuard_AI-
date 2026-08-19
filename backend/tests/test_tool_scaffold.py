"""Tests for the tool scaffold — tenant-scope injection, authorization, and audit logging.

These tests verify:
1. organization_id is injected from context, not from LLM arguments
2. Forged organization_id from LLM is rejected
3. Unauthorized tool calls are rejected
4. ToolExecution audit rows are written on every call
"""

from __future__ import annotations

import pytest

from app.agents.tools.base import (
    ToolAuthorizationError,
    ToolContext,
    ToolExecutionRecord,
    authorize_tool_call,
    clear_tool_execution_log,
    create_tenant_scoped_tool,
    get_tool_execution_log,
    sanitize_arguments,
)


@pytest.fixture(autouse=True)
def _clear_audit_log() -> None:
    """Clear the audit log before each test."""
    clear_tool_execution_log()
    yield
    clear_tool_execution_log()


class TestToolContext:
    """Tests for the ToolContext dataclass."""

    def test_context_has_organization_id(self) -> None:
        """Context carries organization_id."""
        ctx = ToolContext(
            organization_id="org-123",
            user_id="user-456",
            agent_name="test-agent",
        )
        assert ctx.organization_id == "org-123"

    def test_context_has_permitted_tools(self) -> None:
        """Context carries permitted_tools list."""
        ctx = ToolContext(
            organization_id="org-123",
            user_id="user-456",
            agent_name="test-agent",
            permitted_tools=["tool_a", "tool_b"],
        )
        assert ctx.permitted_tools == ["tool_a", "tool_b"]

    def test_context_generates_execution_id(self) -> None:
        """Context auto-generates a unique execution_id."""
        ctx1 = ToolContext(
            organization_id="org-123",
            user_id="user-456",
            agent_name="test-agent",
        )
        ctx2 = ToolContext(
            organization_id="org-123",
            user_id="user-456",
            agent_name="test-agent",
        )
        assert ctx1.execution_id != ctx2.execution_id


class TestSanitizeArguments:
    """Tests for argument sanitization — organization_id injection."""

    def test_injects_organization_id_from_context(self) -> None:
        """organization_id from context is injected into arguments."""
        ctx = ToolContext(
            organization_id="real-org-id",
            user_id="user-1",
            agent_name="test-agent",
        )
        sanitized = sanitize_arguments({"name": "test"}, ctx)
        assert sanitized["organization_id"] == "real-org-id"

    def test_removes_forged_organization_id(self) -> None:
        """organization_id from LLM arguments is removed and replaced."""
        ctx = ToolContext(
            organization_id="real-org-id",
            user_id="user-1",
            agent_name="test-agent",
        )
        sanitized = sanitize_arguments(
            {"name": "test", "organization_id": "evil-org-id"},
            ctx,
        )
        assert sanitized["organization_id"] == "real-org-id"
        assert "evil-org-id" not in sanitized.values()

    def test_preserves_other_arguments(self) -> None:
        """Non-organization_id arguments are preserved."""
        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="test-agent",
        )
        sanitized = sanitize_arguments(
            {"name": "test", "amount": 100.0, "currency": "USD"},
            ctx,
        )
        assert sanitized["name"] == "test"
        assert sanitized["amount"] == 100.0
        assert sanitized["currency"] == "USD"

    def test_empty_arguments_get_organization_id(self) -> None:
        """Empty arguments dict gets organization_id injected."""
        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="test-agent",
        )
        sanitized = sanitize_arguments({}, ctx)
        assert sanitized == {"organization_id": "org-1"}


class TestAuthorizeToolCall:
    """Tests for tool authorization."""

    def test_authorized_tool_call_succeeds(self) -> None:
        """Tool call succeeds when tool is in permitted list."""
        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="test-agent",
            permitted_tools=["read_data", "write_data"],
        )
        # Should not raise
        authorize_tool_call("read_data", ctx)

    def test_unauthorized_tool_call_raises(self) -> None:
        """Tool call raises when tool is not in permitted list."""
        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="test-agent",
            permitted_tools=["read_data"],
        )
        with pytest.raises(ToolAuthorizationError, match="not authorized"):
            authorize_tool_call("write_data", ctx)

    def test_empty_permitted_tools_allows_all(self) -> None:
        """Empty permitted_tools list means no restriction."""
        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="test-agent",
            permitted_tools=[],
        )
        # Should not raise
        authorize_tool_call("any_tool", ctx)

    def test_error_message_includes_agent_name(self) -> None:
        """Authorization error includes agent name for debugging."""
        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="leaky-agent",
            permitted_tools=["safe_tool"],
        )
        with pytest.raises(ToolAuthorizationError, match="leaky-agent"):
            authorize_tool_call("dangerous_tool", ctx)


class TestCreateTenantScopedTool:
    """Tests for the tool creation scaffold."""

    def test_tool_creation(self) -> None:
        """create_tenant_scoped_tool returns a callable tool."""
        async def my_func(**kwargs: object) -> str:
            return "result"

        tool = create_tenant_scoped_tool(
            name="test_tool",
            description="A test tool",
            func=my_func,
        )
        assert tool is not None

    @pytest.mark.asyncio
    async def test_tool_execution_writes_audit_row(self) -> None:
        """Tool execution writes a ToolExecution audit record."""
        async def my_func(organization_id: str, **kwargs: object) -> str:
            return f"data for {organization_id}"

        tool = create_tenant_scoped_tool(
            name="audit_test_tool",
            description="Tests audit logging",
            func=my_func,
        )

        ctx = ToolContext(
            organization_id="org-audit-1",
            user_id="user-1",
            agent_name="audit-agent",
        )

        result = await tool(
            organization_id="org-audit-1",
            _tool_context=ctx,
        )

        assert result == "data for org-audit-1"

        # Check audit log
        log = get_tool_execution_log()
        assert len(log) == 1
        record = log[0]
        assert record.tool_name == "audit_test_tool"
        assert record.agent_name == "audit-agent"
        assert record.organization_id == "org-audit-1"
        assert record.error is None
        assert record.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_tool_execution_logs_error(self) -> None:
        """Tool execution logs errors in the audit record."""
        async def failing_func(**kwargs: object) -> str:
            raise ValueError("Something went wrong")

        tool = create_tenant_scoped_tool(
            name="failing_tool",
            description="A tool that fails",
            func=failing_func,
        )

        ctx = ToolContext(
            organization_id="org-err",
            user_id="user-1",
            agent_name="error-agent",
        )

        with pytest.raises(ValueError, match="Something went wrong"):
            await tool(
                organization_id="org-err",
                _tool_context=ctx,
            )

        log = get_tool_execution_log()
        assert len(log) == 1
        record = log[0]
        assert record.error == "Something went wrong"
        assert record.tool_name == "failing_tool"

    @pytest.mark.asyncio
    async def test_tool_rejects_forged_organization_id(self) -> None:
        """Tool rejects organization_id from LLM and uses context value."""
        received_ids = []

        async def capture_org(organization_id: str, **kwargs: object) -> str:
            received_ids.append(organization_id)
            return "ok"

        tool = create_tenant_scoped_tool(
            name="org_capture_tool",
            description="Captures org_id",
            func=capture_org,
        )

        ctx = ToolContext(
            organization_id="real-org",
            user_id="user-1",
            agent_name="test-agent",
        )

        # LLM tries to forge organization_id
        result = await tool(
            organization_id="evil-org",
            _tool_context=ctx,
        )

        assert result == "ok"
        assert received_ids == ["real-org"]

    @pytest.mark.asyncio
    async def test_tool_rejects_unauthorized_agent(self) -> None:
        """Tool rejects call from agent not in permitted list."""
        async def safe_func(**kwargs: object) -> str:
            return "should not reach here"

        tool = create_tenant_scoped_tool(
            name="safe_tool",
            description="A safe tool",
            func=safe_func,
        )

        ctx = ToolContext(
            organization_id="org-1",
            user_id="user-1",
            agent_name="unauthorized-agent",
            permitted_tools=["other_tool"],  # safe_tool not included
        )

        with pytest.raises(ToolAuthorizationError, match="not authorized"):
            await tool(
                organization_id="org-1",
                _tool_context=ctx,
            )

        # Audit row should still be written for the failed attempt
        log = get_tool_execution_log()
        assert len(log) == 1
        assert log[0].error is not None


class TestToolExecutionRecord:
    """Tests for the ToolExecutionRecord dataclass."""

    def test_record_creation(self) -> None:
        """Record stores all audit fields."""
        record = ToolExecutionRecord(
            execution_id="exec-123",
            tool_name="test_tool",
            agent_name="test-agent",
            organization_id="org-1",
            arguments={"key": "value"},
            result="success",
            duration_ms=42.5,
        )
        assert record.execution_id == "exec-123"
        assert record.tool_name == "test_tool"
        assert record.result == "success"
        assert record.duration_ms == 42.5
        assert record.error is None
        assert record.created_at > 0

    def test_record_with_error(self) -> None:
        """Record stores error information."""
        record = ToolExecutionRecord(
            execution_id="exec-err",
            tool_name="failing_tool",
            agent_name="test-agent",
            organization_id="org-1",
            arguments={},
            error="Division by zero",
        )
        assert record.error == "Division by zero"
        assert record.result is None


class TestGetToolExecutionLog:
    """Tests for the global audit log functions."""

    def test_log_starts_empty(self) -> None:
        """Audit log starts empty."""
        clear_tool_execution_log()
        assert get_tool_execution_log() == []

    def test_log_grows(self) -> None:
        """Audit log grows as records are added."""
        clear_tool_execution_log()
        _tool_execution_log = get_tool_execution_log()
        _tool_execution_log.append(
            ToolExecutionRecord(
                execution_id="e1",
                tool_name="t1",
                agent_name="a1",
                organization_id="o1",
                arguments={},
            )
        )
        assert len(get_tool_execution_log()) == 1

    def test_clear_resets_log(self) -> None:
        """clear_tool_execution_log empties the log."""
        get_tool_execution_log().append(
            ToolExecutionRecord(
                execution_id="e1",
                tool_name="t1",
                agent_name="a1",
                organization_id="o1",
                arguments={},
            )
        )
        clear_tool_execution_log()
        assert get_tool_execution_log() == []
