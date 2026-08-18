# ADR-002: Microsoft Agent Framework + Google Gemini as the Sole Orchestration and LLM Stack

## Status

Accepted

## Date

2026-08-19

## Context

RevenueGuard AI requires an agent orchestration layer (to sequence multi-step investigations, manage tool calls, and checkpoint long-running workflows) and an LLM provider (to power contract interpretation, evidence narration, and recommendation generation). The choices made here will be used across all agent-related phases (7–8 and beyond) and must be consistent across every coding agent session that builds on this repository.

## Decision

- **Orchestration:** Microsoft Agent Framework (`agent-framework` package) is the sole orchestration framework for all agent workflows in this project.
- **LLM Provider:** Google Gemini, accessed via `GEMINI_API_KEY`, is the sole LLM provider for all agent-powered features.
- **No substitutions:** LangChain, LangGraph, CrewAI, AutoGen, and Semantic Kernel must never be installed, imported, or used anywhere in this codebase.

## Alternatives Considered

### 1. LangChain / LangGraph

LangChain is the most widely adopted agent framework. However, it introduces significant abstraction overhead, its API surface changes frequently across versions, and its tool-calling patterns do not align well with the strict structured-output requirements of a financial investigation workflow. LangGraph adds graph-based orchestration but does not match the Microsoft Agent Framework's checkpointing and workflow primitives. **Rejected** — do not use in this project.

### 2. CrewAI

CrewAI provides role-based multi-agent orchestration with a simple API. However, it lacks the fine-grained tool authorization, per-agent permission control, and audit logging capabilities required for a financial SaaS product where every agent action must be traceable and tenant-scoped. **Rejected** — do not use in this project.

### 3. AutoGen (Microsoft)

AutoGen is Microsoft's multi-agent conversation framework. While it shares the Microsoft ecosystem, it is a different product from Microsoft Agent Framework with a different API, different tool-calling patterns, and different workflow primitives. Using it would create confusion between "Microsoft Agent Framework" (the chosen tool) and "AutoGen" (a separate Microsoft product). **Rejected** — do not use in this project.

### 4. Semantic Kernel (Microsoft)

Semantic Kernel is Microsoft's SDK for integrating LLMs into .NET and Python applications. It provides plugin-based tool calling and planning but does not match the workflow orchestration capabilities (checkpointing, sequential/concurrent/handoff patterns) that Microsoft Agent Framework provides for long-running financial investigation workflows. **Rejected** — do not use in this project.

### 5. OpenAI API directly (without orchestration framework)

Using the OpenAI API without an orchestration layer would require building workflow management, tool dispatch, and checkpointing from scratch. This duplicates effort and lacks the agent lifecycle management that Microsoft Agent Framework provides out of the box. **Rejected** — do not use in this project.

### 6. Anthropic Claude as LLM provider

Claude is a capable model but is not the chosen provider. The decision to use Google Gemini is driven by the project's existing integration requirements and the `GEMINI_API_KEY`-based access pattern. **Rejected** — do not use in this project.

## Key Constraints

- `GEMINI_API_KEY` must never be hard-coded, logged, committed to version control, or exposed to the frontend.
- The `agent-framework` package version will be pinned in `pyproject.toml` and verified in Phase 7 (ADR-004).
- All agent tool calls must go through the tool authorization scaffold (Phase 7), which enforces tenant scoping and permission checks.
- Agent structured outputs must use Pydantic models, not raw JSON parsing.

## Consequences

- All agent code uses a single, consistent API surface — no framework migration risk across phases.
- The tool authorization scaffold built in Phase 7 applies uniformly to all agents in Phases 8+.
- If the `agent-framework` package changes its API, the breakage is localized to one integration point (documented in ADR-004).
- Any coding agent session that introduces a LangChain/LangGraph/CrewAI/AutoGen/Semantic Kernel import will fail code review and must be reverted.
