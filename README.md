# RevenueGuard AI

RevenueGuard AI is a multi-tenant SaaS platform that detects and helps recover revenue leakage for B2B services companies. It continuously compares what a business should have earned against what it actually billed and collected — surfacing missing invoices, underbilling, overdue receivables, contract-expiration leakage, and more. Every finding is backed by deterministic evidence (not LLM guessing), and AI agents are used only for contract interpretation, investigation narration, and recovery recommendation — never for arithmetic or database queries.

The platform is built in 17 phases, each producing a self-contained, testable increment. Phases 0–3 establish architecture foundations, the development environment, the database schema, and authentication/RBAC. Phases 4–6 cover data ingestion, normalization/entity resolution, and the deterministic rules engine. Phases 7–8 wire up Microsoft Agent Framework with Google Gemini to build the agentic investigation and recommendation layer. Phases 9–12 implement confidence scoring, human approval workflows, recovery action drafting, and closed-loop verification. Phases 13–17 complete the backend API, build the SaaS frontend, add real-world integrations, and perform security hardening and production readiness. Each phase prompt is fully self-contained — a coding agent only needs the repository and the prompt for the phase it is building.

## Run

Phase 0 is documentation-only — no code to run. Phase 1 will add the development environment, Docker Compose configuration, and the ability to `docker compose up` and `pytest`.
