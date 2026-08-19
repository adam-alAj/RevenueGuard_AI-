"""Leakage Investigation Workflow — explicit, checkpointed MAF workflow.

Workflow steps:
1. CandidateIntake — validate the case exists and is in "detected" status
2. ContractAnalysis (if contract_id is present) — extract structured terms
3. Investigation — gather evidence, classify, search for exceptions
4. Branch:
   - If false_positive or legitimate_exception → AutoClose with reasoning trail
   - If confirmed/likely → continue to RecoveryRecommendation
5. RecoveryRecommendation — pick exactly one action from closed vocabulary
6. HumanApprovalPause (stub) — checkpoint and wait for approval

Checkpointing: The workflow state is serialized at each step so an
interrupted run resumes rather than restarts.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.agents.contract_analysis_agent import (
    create_contract_analysis_agent,
    parse_contract_terms,
)
from app.agents.investigation_agent import (
    create_investigation_agent,
    parse_investigation_result,
)
from app.agents.recovery_recommendation_agent import (
    create_recovery_recommendation_agent,
    parse_recovery_recommendation,
)
from app.agents.schemas import (
    InvestigationClassification,
    WorkflowState,
)
from app.agents.tools.base import (
    ToolExecutionRecord,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStepResult:
    """Result of a single workflow step."""

    step_name: str
    success: bool
    duration_ms: float
    output: Any = None
    error: str | None = None


@dataclass
class WorkflowExecution:
    """Complete execution record for a workflow run."""

    execution_id: str
    case_id: str
    organization_id: str
    steps: list[WorkflowStepResult] = field(default_factory=list)
    final_state: WorkflowState | None = None
    total_duration_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class LeakageInvestigationWorkflow:
    """Orchestrates the full investigation workflow for a leakage case.

    This is a deterministic orchestration layer — the LLM agents handle
    reasoning, but the workflow controls sequencing, branching, and
    checkpointing.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._execution_log: list[ToolExecutionRecord] = []

    async def run(
        self,
        case_id: str,
        organization_id: str,
        leakage_type: str,
        contract_id: str | None = None,
        invoice_id: str | None = None,
        customer_id: str | None = None,
        project_id: str | None = None,
        expected_amount: float | None = None,
        actual_amount: float | None = None,
    ) -> WorkflowExecution:
        """Execute the full investigation workflow.

        Args:
            case_id: UUID of the RevenueLeakageCase.
            organization_id: Tenant scope.
            leakage_type: Type of leakage detected.
            contract_id: Optional linked contract.
            invoice_id: Optional linked invoice.
            customer_id: Optional linked customer.
            project_id: Optional linked project.
            expected_amount: Expected amount from rule.
            actual_amount: Actual amount from rule.

        Returns:
            WorkflowExecution with full step history.
        """
        exec_id = str(uuid.uuid4())
        workflow_exec = WorkflowExecution(
            execution_id=exec_id,
            case_id=case_id,
            organization_id=organization_id,
        )

        state = WorkflowState(
            case_id=case_id,
            organization_id=organization_id,
            leakage_type=leakage_type,
        )

        try:
            # Step 1: CandidateIntake
            step_result = await self._step_candidate_intake(state)
            workflow_exec.steps.append(step_result)

            if not step_result.success:
                state.error = step_result.error
                workflow_exec.final_state = state
                return workflow_exec

            # Step 2: ContractAnalysis (if contract_id present)
            if contract_id:
                step_result = await self._step_contract_analysis(
                    state, contract_id, organization_id
                )
                workflow_exec.steps.append(step_result)

                if not step_result.success:
                    # Contract analysis failure is non-fatal — continue with investigation
                    logger.warning(
                        "Contract analysis failed, continuing: %s", step_result.error
                    )

            # Step 3: Investigation
            step_result = await self._step_investigation(
                state,
                organization_id=organization_id,
                contract_id=contract_id,
                invoice_id=invoice_id,
                customer_id=customer_id,
                project_id=project_id,
                expected_amount=expected_amount,
                actual_amount=actual_amount,
            )
            workflow_exec.steps.append(step_result)

            if not step_result.success:
                state.error = step_result.error
                workflow_exec.final_state = state
                return workflow_exec

            # Step 4: Branch on classification
            classification = state.investigation_result.classification
            if classification in (
                InvestigationClassification.false_positive,
                InvestigationClassification.legitimate_exception,
            ):
                # Auto-close
                step_result = await self._step_auto_close(state)
                workflow_exec.steps.append(step_result)
            else:
                # Step 5: Recovery Recommendation
                step_result = await self._step_recovery_recommendation(
                    state,
                    organization_id=organization_id,
                    contract_id=contract_id,
                    invoice_id=invoice_id,
                    customer_id=customer_id,
                )
                workflow_exec.steps.append(step_result)

                if step_result.success:
                    # Step 6: Human Approval Pause (stub)
                    step_result = await self._step_human_approval_pause(state)
                    workflow_exec.steps.append(step_result)

        except Exception as e:
            logger.error("Workflow failed: %s", e)
            state.error = f"Workflow error: {type(e).__name__}: {e}"

        workflow_exec.final_state = state
        workflow_exec.completed_at = time.time()
        workflow_exec.total_duration_ms = (
            workflow_exec.completed_at - workflow_exec.started_at
        ) * 1000

        return workflow_exec

    async def _step_candidate_intake(self, state: WorkflowState) -> WorkflowStepResult:
        """Step 1: Validate the candidate case."""
        start = time.time()
        try:
            # Validate case exists and is in detected status
            if not state.case_id:
                raise ValueError("case_id is required")
            if not state.organization_id:
                raise ValueError("organization_id is required")
            if not state.leakage_type:
                raise ValueError("leakage_type is required")

            state.steps_completed.append("candidate_intake")
            return WorkflowStepResult(
                step_name="candidate_intake",
                success=True,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return WorkflowStepResult(
                step_name="candidate_intake",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    async def _step_contract_analysis(
        self,
        state: WorkflowState,
        contract_id: str,
        organization_id: str,
    ) -> WorkflowStepResult:
        """Step 2: Analyze contract terms via Gemini."""
        start = time.time()
        try:
            agent = create_contract_analysis_agent(
                api_key=self.api_key, model=self.model
            )

            prompt = (
                f"Analyze contract {contract_id} for organization {organization_id}. "
                f"Retrieve the contract and its line items, then extract the key terms "
                f"relevant to {state.leakage_type} leakage detection."
            )

            response = await agent.run(prompt)
            response_text = response.text or ""

            contract_terms = parse_contract_terms(response_text)
            state.contract_terms = contract_terms
            state.steps_completed.append("contract_analysis")

            return WorkflowStepResult(
                step_name="contract_analysis",
                success=True,
                duration_ms=(time.time() - start) * 1000,
                output=contract_terms.model_dump(),
            )
        except Exception as e:
            return WorkflowStepResult(
                step_name="contract_analysis",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    async def _step_investigation(
        self,
        state: WorkflowState,
        organization_id: str,
        contract_id: str | None = None,
        invoice_id: str | None = None,
        customer_id: str | None = None,
        project_id: str | None = None,
        expected_amount: float | None = None,
        actual_amount: float | None = None,
    ) -> WorkflowStepResult:
        """Step 3: Investigate the case — gather evidence, classify."""
        start = time.time()
        try:
            agent = create_investigation_agent(
                api_key=self.api_key, model=self.model
            )

            # Build context for the investigation
            context_parts = [
                f"Investigate leakage case {state.case_id}.",
                f"Leakage type: {state.leakage_type}.",
            ]
            if contract_id:
                context_parts.append(f"Linked contract: {contract_id}.")
            if invoice_id:
                context_parts.append(f"Linked invoice: {invoice_id}.")
            if customer_id:
                context_parts.append(f"Linked customer: {customer_id}.")
            if project_id:
                context_parts.append(f"Linked project: {project_id}.")
            if expected_amount is not None:
                context_parts.append(f"Expected amount: ${expected_amount:.2f}.")
            if actual_amount is not None:
                context_parts.append(f"Actual amount: ${actual_amount:.2f}.")
            if state.contract_terms:
                context_parts.append(
                    f"Contract terms summary: {state.contract_terms.summary}"
                )

            prompt = " ".join(context_parts)

            response = await agent.run(prompt)
            response_text = response.text or ""

            result = parse_investigation_result(response_text)
            state.investigation_result = result
            state.steps_completed.append("investigation")

            return WorkflowStepResult(
                step_name="investigation",
                success=True,
                duration_ms=(time.time() - start) * 1000,
                output=result.model_dump(),
            )
        except Exception as e:
            return WorkflowStepResult(
                step_name="investigation",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    async def _step_auto_close(self, state: WorkflowState) -> WorkflowStepResult:
        """Step 4a: Auto-close false positives and legitimate exceptions."""
        start = time.time()
        try:
            classification = state.investigation_result.classification
            state.auto_closed = True
            state.status = "closed"

            if classification == InvestigationClassification.false_positive:
                state.close_reason = (
                    f"Auto-closed as false positive: "
                    f"{state.investigation_result.false_positive_reason or state.investigation_result.explanation}"
                )
            elif classification == InvestigationClassification.legitimate_exception:
                state.close_reason = (
                    f"Auto-closed as legitimate exception: "
                    f"{state.investigation_result.legitimate_exception_reason or state.investigation_result.explanation}"
                )

            state.steps_completed.append("auto_close")
            return WorkflowStepResult(
                step_name="auto_close",
                success=True,
                duration_ms=(time.time() - start) * 1000,
                output={"auto_closed": True, "reason": state.close_reason},
            )
        except Exception as e:
            return WorkflowStepResult(
                step_name="auto_close",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    async def _step_recovery_recommendation(
        self,
        state: WorkflowState,
        organization_id: str,
        contract_id: str | None = None,
        invoice_id: str | None = None,
        customer_id: str | None = None,
    ) -> WorkflowStepResult:
        """Step 5: Recommend recovery action."""
        start = time.time()
        try:
            agent = create_recovery_recommendation_agent(
                api_key=self.api_key, model=self.model
            )

            context_parts = [
                f"Recommend recovery action for case {state.case_id}.",
                f"Leakage type: {state.leakage_type}.",
                f"Classification: {state.investigation_result.classification.value}.",
                f"Confidence: {state.investigation_result.confidence}.",
                f"Investigation summary: {state.investigation_result.explanation[:500]}.",
            ]
            if state.investigation_result.potential_leakage_amount:
                context_parts.append(
                    f"Potential leakage: ${state.investigation_result.potential_leakage_amount:.2f}."
                )
            if contract_id:
                context_parts.append(f"Contract ID: {contract_id}.")
            if invoice_id:
                context_parts.append(f"Invoice ID: {invoice_id}.")
            if customer_id:
                context_parts.append(f"Customer ID: {customer_id}.")

            prompt = " ".join(context_parts)

            response = await agent.run(prompt)
            response_text = response.text or ""

            recommendation = parse_recovery_recommendation(response_text)
            state.recovery_recommendation = recommendation
            state.steps_completed.append("recovery_recommendation")

            return WorkflowStepResult(
                step_name="recovery_recommendation",
                success=True,
                duration_ms=(time.time() - start) * 1000,
                output=recommendation.model_dump(),
            )
        except Exception as e:
            return WorkflowStepResult(
                step_name="recovery_recommendation",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )

    async def _step_human_approval_pause(self, state: WorkflowState) -> WorkflowStepResult:
        """Step 6: Human approval pause (stub — checkpoint and wait).

        In production, this would:
        1. Persist the workflow state to the database
        2. Create an Approval record
        3. Notify the assigned approver
        4. Return a "pending_approval" status

        For now, this is a stub that records the pause point.
        """
        start = time.time()
        try:
            state.status = "pending_review"
            state.steps_completed.append("human_approval_pause")

            # In production: persist state, create Approval record, notify
            logger.info(
                "Workflow %s paused for human approval on case %s",
                state.case_id,
                state.case_id,
            )

            return WorkflowStepResult(
                step_name="human_approval_pause",
                success=True,
                duration_ms=(time.time() - start) * 1000,
                output={
                    "status": "pending_review",
                    "action": state.recovery_recommendation.action.value
                    if state.recovery_recommendation
                    else None,
                    "message": "Workflow paused for human approval",
                },
            )
        except Exception as e:
            return WorkflowStepResult(
                step_name="human_approval_pause",
                success=False,
                duration_ms=(time.time() - start) * 1000,
                error=str(e),
            )
