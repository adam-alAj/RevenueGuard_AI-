"""Observability API — execution trace logs with correlation IDs.

Endpoints:
- GET /api/v1/observability/traces — list execution traces
- GET /api/v1/observability/traces/{correlation_id} — get full trace
- GET /api/v1/observability/metrics — aggregated observability metrics
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.core.rbac import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observability", tags=["observability"])


# ─── In-memory trace store (MVP — replace with OpenTelemetry in production) ───

_trace_store: list[dict[str, Any]] = []


def record_trace(trace: dict[str, Any]) -> None:
    """Record an execution trace (called by rule engine, agents, tools)."""
    _trace_store.append(trace)


def get_traces(correlation_id: str | None = None) -> list[dict[str, Any]]:
    """Get traces, optionally filtered by correlation_id."""
    if correlation_id:
        return [t for t in _trace_store if t.get("correlation_id") == correlation_id]
    return list(_trace_store)


def clear_traces() -> None:
    """Clear all traces (for testing)."""
    _trace_store.clear()


# ─── Schemas ─────────────────────────────────────────────────────────────────


class TraceResponse(BaseModel):
    """A single execution trace entry."""

    correlation_id: str
    execution_type: str  # rule, agent, tool, workflow
    execution_id: str
    started_at: str
    completed_at: str | None = None
    duration_ms: float | None = None
    status: str = "success"
    error_message: str | None = None
    token_count: int | None = None
    cost_usd: float | None = None
    metadata: dict[str, Any] = {}


class TraceListResponse(BaseModel):
    """List of traces with summary metrics."""

    traces: list[TraceResponse]
    total: int
    summary: dict[str, Any]


class ObservabilityMetricsResponse(BaseModel):
    """Aggregated observability metrics."""

    total_executions: int
    by_type: dict[str, int]
    avg_duration_ms: float
    error_rate: float
    total_tokens: int
    total_cost_usd: float
    p95_duration_ms: float


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    correlation_id: str | None = Query(None, description="Filter by correlation ID"),
    execution_type: str | None = Query(None, description="Filter by type (rule/agent/tool)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _user: Any = Depends(require_permission("observability", "read")),
) -> TraceListResponse:
    """List execution traces with optional filtering."""
    traces = get_traces(correlation_id)

    if execution_type:
        traces = [t for t in traces if t.get("execution_type") == execution_type]

    total = len(traces)
    start = (page - 1) * page_size
    page_traces = traces[start : start + page_size]

    # Compute summary
    total_tokens = sum(t.get("token_count", 0) or 0 for t in traces)
    total_cost = sum(t.get("cost_usd", 0) or 0 for t in traces)
    durations = [t["duration_ms"] for t in traces if t.get("duration_ms") is not None]
    avg_dur = sum(durations) / len(durations) if durations else 0
    errors = sum(1 for t in traces if t.get("status") == "error")

    return TraceListResponse(
        traces=[TraceResponse(**t) for t in page_traces],
        total=total,
        summary={
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_duration_ms": round(avg_dur, 2),
            "error_count": errors,
        },
    )


@router.get("/traces/{correlation_id}", response_model=list[TraceResponse])
async def get_trace_by_correlation_id(
    correlation_id: str,
    _user: Any = Depends(require_permission("observability", "read")),
) -> list[TraceResponse]:
    """Get all trace entries for a correlation ID (end-to-end trace)."""
    traces = get_traces(correlation_id)
    return [TraceResponse(**t) for t in traces]


@router.get("/metrics", response_model=ObservabilityMetricsResponse)
async def get_observability_metrics(
    _user: Any = Depends(require_permission("observability", "read")),
) -> ObservabilityMetricsResponse:
    """Aggregated observability metrics across all executions."""
    traces = get_traces()

    total = len(traces)
    by_type: dict[str, int] = {}
    for t in traces:
        et = t.get("execution_type", "unknown")
        by_type[et] = by_type.get(et, 0) + 1

    durations = [t["duration_ms"] for t in traces if t.get("duration_ms") is not None]
    avg_dur = sum(durations) / len(durations) if durations else 0
    sorted_durs = sorted(durations) if durations else [0]
    p95_idx = int(len(sorted_durs) * 0.95)
    p95_dur = sorted_durs[min(p95_idx, len(sorted_durs) - 1)]

    errors = sum(1 for t in traces if t.get("status") == "error")
    error_rate = errors / total if total > 0 else 0

    total_tokens = sum(t.get("token_count", 0) or 0 for t in traces)
    total_cost = sum(t.get("cost_usd", 0) or 0 for t in traces)

    return ObservabilityMetricsResponse(
        total_executions=total,
        by_type=by_type,
        avg_duration_ms=round(avg_dur, 2),
        error_rate=round(error_rate, 4),
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 6),
        p95_duration_ms=round(p95_dur, 2),
    )
