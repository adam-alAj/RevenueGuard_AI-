"""Workflow integration tests — sequencing, cross-tenant, audit trail.

Tests verify:
- Workflow steps execute in correct order
- Cross-tenant isolation holds for the full agent/tool layer
- Every workflow run produces a complete AgentExecution trail
- Auto-close works for false_positive and legitimate_exception
- Workflow state is properly checkpointed
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.schemas import (
    InvestigationClassification,
    InvestigationResult,
    RecoveryActionType,
    RecoveryRecommendation,
    UrgencyLevel,
    WorkflowState,
)
from app.agents.tools.base import (
    ToolContext,
    clear_tool_execution_log,
)
from app.agents.tools.investigation_tools import (
    clear_data_store,
    set_data_store,
)
from app.workflows.leakage_investigation_workflow import (
    LeakageInvestigationWorkflow,
)


@pytest.fixture(autouse=True)
def _clear_state() -> None:
    """Clear global state before each test."""
    clear_tool_execution_log()
    clear_data_store()
    yield
    clear_tool_execution_log()
    clear_data_store()


class TestWorkflowState:
    """Tests for WorkflowState schema."""

    def test_initial_state(self) -> None:
        """Initial state has correct defaults."""
        state = WorkflowState(
            case_id="case-001",
            organization_id="org-001",
            leakage_type="missing_invoice",
        )
        assert state.status == "detected"
        assert state.auto_closed is False
        assert state.steps_completed == []
        assert state.contract_terms is None
        assert state.investigation_result is None
        assert state.recovery_recommendation is None

    def test_state_with_investigation(self) -> None:
        """State carries investigation result."""
        state = WorkflowState(
            case_id="case-001",
            organization_id="org-001",
            leakage_type="underbilling",
        )
        state.investigation_result = InvestigationResult(
            classification=InvestigationClassification.confirmed,
            confidence=0.9,
            explanation="Confirmed underbilling.",
            evidence_refs=[
                {"evidence_id": "ev-001", "evidence_type": "invoice", "relevance": "test"}
            ],
        )
        assert state.investigation_result.classification == InvestigationClassification.confirmed


class TestWorkflowStepOrdering:
    """Tests that workflow steps execute in the correct order."""

    @pytest.mark.asyncio
    async def test_workflow_steps_order(self) -> None:
        """Workflow records steps in execution order."""
        workflow = LeakageInvestigationWorkflow(
            api_key="test-key",
            model="gemini-2.0-flash",
        )

        # Mock all agent calls
        mock_contract_response = MagicMock()
        mock_contract_response.text = json.dumps(
            {
                "billing_frequency": "monthly",
                "unit_pricing_model": "fixed",
                "base_rate": 1000.0,
                "renewal_terms": "auto_renew",
                "summary": "Test contract",
            }
        )

        mock_investigation_response = MagicMock()
        mock_investigation_response.text = json.dumps(
            {
                "classification": "confirmed",
                "confidence": 0.9,
                "explanation": "Confirmed leakage.",
                "evidence_refs": [
                    {"evidence_id": "ev-001", "evidence_type": "invoice", "relevance": "test"}
                ],
            }
        )

        mock_recovery_response = MagicMock()
        mock_recovery_response.text = json.dumps(
            {
                "action": "create_invoice_draft",
                "urgency": "within_week",
                "rationale": "Invoice needed.",
                "requires_approval": True,
            }
        )

        with (
            patch(
                "app.workflows.leakage_investigation_workflow.create_contract_analysis_agent"
            ) as mock_ca,
            patch(
                "app.workflows.leakage_investigation_workflow.create_investigation_agent"
            ) as mock_inv,
            patch(
                "app.workflows.leakage_investigation_workflow.create_recovery_recommendation_agent"
            ) as mock_rec,
        ):
            # Setup mocks
            mock_ca_agent = MagicMock()
            mock_ca_agent.run = AsyncMock(return_value=mock_contract_response)
            mock_ca.return_value = mock_ca_agent

            mock_inv_agent = MagicMock()
            mock_inv_agent.run = AsyncMock(return_value=mock_investigation_response)
            mock_inv.return_value = mock_inv_agent

            mock_rec_agent = MagicMock()
            mock_rec_agent.run = AsyncMock(return_value=mock_recovery_response)
            mock_rec.return_value = mock_rec_agent

            execution = await workflow.run(
                case_id="case-001",
                organization_id="org-001",
                leakage_type="underbilling",
                contract_id="contract-001",
                invoice_id="invoice-001",
                customer_id="customer-001",
            )

        # Verify step ordering
        step_names = [s.step_name for s in execution.steps]
        assert step_names == [
            "candidate_intake",
            "contract_analysis",
            "investigation",
            "recovery_recommendation",
            "human_approval_pause",
        ]

        # Verify all steps succeeded
        for step in execution.steps:
            assert step.success, f"Step {step.step_name} failed: {step.error}"

        # Verify final state
        state = execution.final_state
        assert state.status == "pending_review"
        assert state.investigation_result is not None
        assert state.recovery_recommendation is not None
        assert state.auto_closed is False


class TestWorkflowAutoClose:
    """Tests for auto-close on false_positive and legitimate_exception."""

    @pytest.mark.asyncio
    async def test_false_positive_auto_closes(self) -> None:
        """False positive classification triggers auto-close."""
        workflow = LeakageInvestigationWorkflow(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "classification": "false_positive",
                "confidence": 0.85,
                "explanation": "Not actual leakage — pricing was amended.",
                "evidence_refs": [
                    {
                        "evidence_id": "ev-001",
                        "evidence_type": "contract_amendment",
                        "relevance": "test",
                    }
                ],
                "false_positive_reason": "Contract amended to reflect new pricing.",
            }
        )

        with patch(
            "app.workflows.leakage_investigation_workflow.create_investigation_agent"
        ) as mock_inv:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_response)
            mock_inv.return_value = mock_agent

            execution = await workflow.run(
                case_id="case-002",
                organization_id="org-001",
                leakage_type="pricing_mismatch",
            )

        state = execution.final_state
        assert state.auto_closed is True
        assert state.status == "closed"
        assert "false positive" in state.close_reason.lower()

        # Should NOT have recovery recommendation step
        step_names = [s.step_name for s in execution.steps]
        assert "recovery_recommendation" not in step_names
        assert "auto_close" in step_names

    @pytest.mark.asyncio
    async def test_legitimate_exception_auto_closes(self) -> None:
        """Legitimate exception classification triggers auto-close."""
        workflow = LeakageInvestigationWorkflow(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "classification": "legitimate_exception",
                "confidence": 0.95,
                "explanation": "Credit note explains the discrepancy.",
                "evidence_refs": [
                    {"evidence_id": "ev-002", "evidence_type": "credit_note", "relevance": "test"}
                ],
                "legitimate_exception_reason": "Credit note CN-001 covers the gap.",
            }
        )

        with patch(
            "app.workflows.leakage_investigation_workflow.create_investigation_agent"
        ) as mock_inv:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_response)
            mock_inv.return_value = mock_agent

            execution = await workflow.run(
                case_id="case-003",
                organization_id="org-001",
                leakage_type="partial_payment",
            )

        state = execution.final_state
        assert state.auto_closed is True
        assert state.status == "closed"
        assert "legitimate exception" in state.close_reason.lower()


class TestCrossTenantIsolation:
    """Cross-tenant isolation tests for the full agent/tool layer."""

    @pytest.mark.asyncio
    async def test_org_a_cannot_see_org_b_data(self) -> None:
        """Tools for Org A return no data from Org B."""
        from app.agents.tools.investigation_tools import (
            get_contract,
            get_customer,
            get_payments,
            search_customer_history,
        )

        # Set up data for two different organizations
        store = {
            "org-A": {
                "customers": [{"id": "cust-A1", "organization_id": "org-A", "name": "Acme A"}],
                "contracts": [
                    {"id": "cont-A1", "organization_id": "org-A", "customer_id": "cust-A1"}
                ],
                "payments": [{"id": "pay-A1", "organization_id": "org-A", "invoice_id": "inv-A1"}],
            },
            "org-B": {
                "customers": [{"id": "cust-B1", "organization_id": "org-B", "name": "Globex B"}],
                "contracts": [
                    {"id": "cont-B1", "organization_id": "org-B", "customer_id": "cust-B1"}
                ],
                "payments": [{"id": "pay-B1", "organization_id": "org-B", "invoice_id": "inv-B1"}],
            },
        }
        set_data_store(store)

        try:
            # Org A tries to get Org B's customer — should return None
            result = await get_customer(organization_id="org-A", customer_id="cust-B1")
            assert result is None

            # Org A tries to get Org B's contract — should return None
            result = await get_contract(organization_id="org-A", contract_id="cont-B1")
            assert result is None

            # Org A tries to get Org B's payments — should return empty
            result = await get_payments(organization_id="org-A", invoice_id="inv-B1")
            assert result == []

            # Org A searches customer history — should only see Org A data
            result = await search_customer_history(organization_id="org-A", customer_id="cust-A1")
            assert len(result) > 0
            for item in result:
                assert str(item["data"].get("organization_id")) == "org-A"

            # Org A searches for Org B's customer history — should return empty
            result = await search_customer_history(organization_id="org-A", customer_id="cust-B1")
            assert result == []
        finally:
            clear_data_store()

    @pytest.mark.asyncio
    async def test_tool_context_enforces_tenant_scope(self) -> None:
        """ToolContext organization_id overrides any LLM-provided value."""
        from app.agents.tools.base import sanitize_arguments

        ctx = ToolContext(
            organization_id="real-org",
            user_id="user-1",
            agent_name="investigation-agent",
        )

        # LLM tries to forge organization_id
        sanitized = sanitize_arguments(
            {"customer_id": "cust-001", "organization_id": "evil-org"},
            ctx,
        )

        assert sanitized["organization_id"] == "real-org"
        assert "evil-org" not in sanitized.values()


class TestAgentExecutionTrail:
    """Tests that every workflow run produces a complete audit trail."""

    @pytest.mark.asyncio
    async def test_workflow_produces_execution_record(self) -> None:
        """Workflow execution has complete step history."""
        workflow = LeakageInvestigationWorkflow(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "classification": "confirmed",
                "confidence": 0.9,
                "explanation": "Confirmed.",
                "evidence_refs": [
                    {"evidence_id": "ev-001", "evidence_type": "invoice", "relevance": "test"}
                ],
            }
        )

        mock_recovery = MagicMock()
        mock_recovery.text = json.dumps(
            {
                "action": "send_payment_reminder",
                "urgency": "within_week",
                "rationale": "Payment reminder needed.",
                "requires_approval": False,
            }
        )

        with (
            patch(
                "app.workflows.leakage_investigation_workflow.create_investigation_agent"
            ) as mock_inv,
            patch(
                "app.workflows.leakage_investigation_workflow.create_recovery_recommendation_agent"
            ) as mock_rec,
        ):
            mock_inv_agent = MagicMock()
            mock_inv_agent.run = AsyncMock(return_value=mock_response)
            mock_inv.return_value = mock_inv_agent

            mock_rec_agent = MagicMock()
            mock_rec_agent.run = AsyncMock(return_value=mock_recovery)
            mock_rec.return_value = mock_rec_agent

            execution = await workflow.run(
                case_id="case-audit",
                organization_id="org-001",
                leakage_type="missing_invoice",
            )

        # Verify execution record
        assert execution.execution_id is not None
        assert execution.case_id == "case-audit"
        assert execution.organization_id == "org-001"
        assert len(execution.steps) > 0
        assert execution.total_duration_ms >= 0
        assert execution.completed_at is not None

        # Verify each step has timing
        for step in execution.steps:
            assert step.duration_ms >= 0
            assert step.step_name is not None

    @pytest.mark.asyncio
    async def test_workflow_step_failure_recorded(self) -> None:
        """Failed steps are recorded in the execution trail."""
        workflow = LeakageInvestigationWorkflow(api_key="test-key")

        # Make investigation agent fail
        with patch(
            "app.workflows.leakage_investigation_workflow.create_investigation_agent"
        ) as mock_inv:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(side_effect=Exception("Gemini API error"))
            mock_inv.return_value = mock_agent

            execution = await workflow.run(
                case_id="case-fail",
                organization_id="org-001",
                leakage_type="underbilling",
            )

        # Investigation step should have failed
        inv_step = next((s for s in execution.steps if s.step_name == "investigation"), None)
        assert inv_step is not None
        assert inv_step.success is False
        assert "Gemini API error" in inv_step.error

        # Final state should have error
        assert execution.final_state.error is not None


class TestWorkflowCheckpointing:
    """Tests for workflow state checkpointing."""

    def test_state_serialization(self) -> None:
        """WorkflowState can be serialized and deserialized."""
        state = WorkflowState(
            case_id="case-001",
            organization_id="org-001",
            leakage_type="missing_invoice",
        )
        state.steps_completed = ["candidate_intake", "contract_analysis"]

        # Serialize
        data = state.model_dump()

        # Deserialize
        restored = WorkflowState(**data)

        assert restored.case_id == state.case_id
        assert restored.organization_id == state.organization_id
        assert restored.steps_completed == state.steps_completed

    def test_state_with_full_results(self) -> None:
        """State with all results serializes correctly."""
        state = WorkflowState(
            case_id="case-001",
            organization_id="org-001",
            leakage_type="underbilling",
        )
        state.investigation_result = InvestigationResult(
            classification=InvestigationClassification.confirmed,
            confidence=0.9,
            explanation="Confirmed.",
            evidence_refs=[
                {"evidence_id": "ev-001", "evidence_type": "invoice", "relevance": "test"}
            ],
        )
        state.recovery_recommendation = RecoveryRecommendation(
            action=RecoveryActionType.create_invoice_draft,
            urgency=UrgencyLevel.within_week,
            rationale="Need invoice.",
        )

        data = state.model_dump()
        json_str = json.dumps(data, default=str)
        restored = WorkflowState(**json.loads(json_str))

        assert (
            restored.investigation_result.classification == InvestigationClassification.confirmed
        )
        assert restored.recovery_recommendation.action == RecoveryActionType.create_invoice_draft


class TestWorkflowWithoutContract:
    """Tests workflow behavior when no contract is linked."""

    @pytest.mark.asyncio
    async def test_skips_contract_analysis(self) -> None:
        """Workflow skips contract analysis when contract_id is None."""
        workflow = LeakageInvestigationWorkflow(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "classification": "confirmed",
                "confidence": 0.8,
                "explanation": "Confirmed without contract analysis.",
                "evidence_refs": [
                    {"evidence_id": "ev-001", "evidence_type": "invoice", "relevance": "test"}
                ],
            }
        )

        with patch(
            "app.workflows.leakage_investigation_workflow.create_investigation_agent"
        ) as mock_inv:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_response)
            mock_inv.return_value = mock_agent

            execution = await workflow.run(
                case_id="case-no-contract",
                organization_id="org-001",
                leakage_type="overdue_invoice",
                # No contract_id
            )

        step_names = [s.step_name for s in execution.steps]
        assert "candidate_intake" in step_names
        assert "contract_analysis" not in step_names
        assert "investigation" in step_names
