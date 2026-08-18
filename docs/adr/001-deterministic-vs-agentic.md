# ADR-001: Deterministic Code for Money Math, AI Agents for Reasoning

## Status

Accepted

## Date

2026-08-19

## Context

RevenueGuard AI must be trustworthy enough that finance teams rely on its numbers. The platform performs monetary calculations (expected vs. actual billing, outstanding balances, recovery amounts), date-based comparisons (overdue detection, contract expiration), threshold checks (underbilling percentages, aging buckets), and database queries (joining contracts to invoices to payments). It also needs to interpret ambiguous contract language, investigate discrepancies across multiple records, narrate evidence, and recommend recovery actions — tasks that require language understanding and reasoning.

The risk is that an LLM performing arithmetic will occasionally hallucinate a number, and a financial product cannot survive a single instance of "the AI said we underbilled by $14,200 but it was actually $12,400." Conversely, requiring hard-coded deterministic logic for contract interpretation or evidence narration would be brittle and unscalable.

## Decision

All money math, date math, threshold comparisons, and database queries are performed exclusively by deterministic Python code. AI agents (orchestrated via Microsoft Agent Framework, powered by Google Gemini) are used exclusively for: contract interpretation, evidence gathering and narration, investigation reasoning, and recovery recommendation.

The boundary is enforced by architectural convention: agents produce structured outputs (Pydantic models) that flow into deterministic pipelines. Agents never execute arithmetic directly. Deterministic code never attempts natural-language interpretation.

## Alternatives Considered

### 1. LLM for everything (including math)

Used by some demo-stage products. Rejected because LLMs are stochastic — they can produce plausible but incorrect dollar figures. In a product whose value proposition is "trust our numbers," a single hallucinated calculation destroys credibility. Additionally, LLMs cannot guarantee consistent results across runs for identical inputs, making audit and reproducibility impossible.

### 2. Deterministic code for everything (no LLM)

Rejected because contract interpretation, cross-record investigation, and evidence narration require language understanding that rule-based systems handle poorly. A contract might state "billing shall occur within 30 days of project completion, exclusive of holidays" — parsing that requires NLU, not regex. Eliminating LLMs entirely would make the product brittle against the real-world messiness of contracts and business communications.

### 3. Hybrid with fuzzy boundaries

Allowing agents to "sometimes" do arithmetic if the logic is "simple enough." Rejected because fuzzy boundaries are unenforceable — every phase (built by separate coding agents with only the repo as context) would interpret "simple enough" differently, and eventually an agent would compute a dollar figure. A hard boundary (agents produce structured facts, deterministic code computes) is the only convention that survives 17+ phases of parallel development.

## Concrete Domain Examples

| Operation | Owner | Rationale |
|---|---|---|
| Sum of InvoiceLine amounts for a contract | Deterministic code | Exact arithmetic — no tolerance for approximation |
| Comparing `sum(contract_line.qty × unit_price)` vs `sum(invoice_line.qty × unit_price)` for underbilling detection | Deterministic code | Monetary comparison with configurable threshold |
| Determining whether `invoice.due_date < today()` with `outstanding_balance > 0` | Deterministic code | Date math and comparison |
| Interpreting a contract clause about billing frequency and renewal terms | AI agent (Contract Analysis) | Natural language understanding required |
| Investigating whether a detected underbilling case is a real discrepancy or a legitimate contract amendment | AI agent (Investigation) | Requires cross-referencing multiple records and reasoning about intent |
| Narrating the evidence trail for a confirmed leakage case | AI agent (Investigation) | Language generation from structured facts |
| Recommending whether to create a corrective invoice or send a payment reminder | AI agent (Recovery Recommendation) | Contextual reasoning, but the dollar amount is always computed deterministically first |
| Computing confidence score from detection strength + entity resolution quality + evidence completeness | Deterministic code | Weighted formula — must be reproducible and decomposable |

## Consequences

- Every monetary value in the system is traceable to deterministic code, enabling full auditability.
- Agents produce structured outputs (enums, typed fields) that deterministic pipelines consume — no agent output is trusted as a raw dollar figure.
- This boundary must be documented in every ADR and enforced in code review: if an agent call returns a dollar amount, it is a bug.
- Future phases must not introduce LLM calls inside rule evaluation, scoring, or financial impact calculation functions.
