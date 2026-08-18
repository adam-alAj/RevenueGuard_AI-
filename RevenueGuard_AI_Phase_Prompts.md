# RevenueGuard AI — Phase Prompts (6-Component Anatomy)

Each prompt below is fully self-contained — copy one block into a coding-agent session on its own. Every prompt uses the same six components, in the same order, so the coding agent always knows: who to be, what to build, what it needs to know, why it matters, when it's done, and exactly how to report back.

**Before using any prompt**: the agent must inspect the existing repository (`git log`, `ls -R`, read `README.md` and `docs/adr/*`) before writing code, and must not blindly trust this prompt if the repo already diverges from an assumption in it — adapt to what actually exists and report the divergence. Implement **only** the phase in the prompt. Leave the repo in a working, test-passing state. Do not implement future phases. At the end, report files changed, tests executed with real pass/fail counts, and known limitations.

---

## PHASE 0 — Architecture Foundation & Repo Scaffolding

```
🔵 ROLE
Act as a senior SaaS architect setting up a repository for a multi-phase, multi-agent
financial product build. You default to documenting decisions before writing code, and
you never let an assumption go unrecorded when a future engineer (human or AI) will need
to rely on it.

🟠 TASK
Establish the repository skeleton, three architecture decision records (ADRs), and a
domain glossary for RevenueGuard AI — with zero business logic, zero database schema,
and zero installed dependencies. This phase produces documentation and folder structure
only.

🟢 CONTEXT
- Product: RevenueGuard AI, a multi-tenant SaaS that detects and helps recover revenue
  leakage (missing invoices, underbilling, overdue receivables, contract-expiration
  leakage, etc.) for B2B services companies.
- Two non-negotiable architectural rules govern the entire build:
  1. Deterministic code (never an LLM) performs all money math, date math, thresholds,
     and database queries.
  2. AI agents (Microsoft Agent Framework orchestrating Google Gemini) are used only for
     contract interpretation, investigation, evidence narration, and recommendation —
     never for arithmetic.
- Orchestration is Microsoft Agent Framework (`agent_framework` package) — do not
  substitute LangChain, LangGraph, CrewAI, AutoGen, or Semantic Kernel anywhere in this
  project, ever.
- The LLM provider is Google Gemini, accessed via `GEMINI_API_KEY`, which must never be
  hard-coded, logged, committed, or exposed to the frontend.
- Multi-tenancy is required from day one: every tenant-owned entity will carry an
  `organization_id`.
- This is the first phase — no prior code exists.

🟣 REASONING
Every later phase (2 through 17) will be built by a separate coding-agent session that
only has the repository itself as context — it will not have this conversation. If the
core architectural decisions (deterministic-vs-agentic split, MAF+Gemini as the sole
stack, multi-tenancy strategy) aren't written down now as ADRs, every later phase risks
silently re-deciding them differently. Getting this phase right is cheap; getting it
wrong is expensive because it compounds across 17 more phases.

🔴 STOP CONDITIONS
Only stop when:
- Three ADRs exist, each stating a decision, the alternatives considered, and the
  rationale (not just a decision with no "why").
- ADR-001 covers the deterministic-vs-agentic split with concrete examples pulled from
  the product's leakage-detection domain.
- ADR-002 covers Microsoft Agent Framework + Gemini as the sole orchestration/provider
  stack, explicitly ruling out the disallowed frameworks by name.
- ADR-003 covers the multi-tenancy strategy (organization_id + repository-layer
  enforcement) and states the row-level-security tradeoff explicitly.
- A domain glossary defines all 11 core entities (Customer, Contract, Invoice,
  RevenueLeakageCase, Evidence, Investigation, RecoveryAction, RecoveryResult, Approval,
  AuditLog, AgentExecution) in one sentence each.
- No Python/TypeScript code, database schema, or dependency has been added.

🟣 OUTPUT
Produce:
- /README.md — 3 paragraphs describing the product, the phase list, and a placeholder
  "Phase 1 will add the dev environment" run instruction.
- /docs/adr/001-deterministic-vs-agentic.md
- /docs/adr/002-maf-gemini.md
- /docs/adr/003-multitenancy.md
- /docs/DOMAIN_GLOSSARY.md
- /backend/.gitkeep, /frontend/.gitkeep (empty placeholders)
- .gitignore covering Python, Node, .env, IDE files

Then:
- Git branch: phase-0-architecture-foundation
- Commit message: docs(architecture): establish ADRs, glossary, and repo skeleton
- Report: files created, and confirm no code/schema/dependency was introduced.
```

---

## PHASE 1 — Development Environment & Tooling

```
🔵 ROLE
Act as a senior backend platform engineer setting up a reproducible Python service
environment for a production-oriented (not toy) SaaS backend.

🟠 TASK
Make the repository runnable: dependency management, containerized Postgres, a minimal
FastAPI app with a health check, linting, testing, and CI — with zero business logic.
Every subsequent phase must be able to `docker compose up` and `pytest` from day one.

🟢 CONTEXT
- Repository already contains Phase 0's ADRs and skeleton (docs/adr/001–003,
  DOMAIN_GLOSSARY.md) — read them before starting; they define the deterministic-vs-
  agentic split, the MAF+Gemini stack, and the multi-tenancy strategy you must respect
  in the config you set up here (e.g., config must be able to hold GEMINI_API_KEY and a
  future JWT secret, even though nothing uses them yet).
- Target stack: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, the
  `agent-framework` package (installed now, unused until Phase 7), pytest, ruff, Docker
  Compose.
- Secrets (GEMINI_API_KEY, JWT_SECRET, DATABASE_URL) must be loaded from environment
  variables via pydantic-settings, with no default values for secrets outside test mode
  — the app should fail fast, not silently run insecure, if a secret is missing.

🟣 REASONING
Phases 2 through 17 all assume a working `pytest`/`docker compose up`/CI loop exists.
Skipping rigor here (e.g., allowing a default secret value, or skipping the CI workflow)
creates a foundation that quietly tolerates insecure config for the rest of the build —
by the time Phase 16's security hardening pass would catch it, dozens of features may
already depend on the lax default.

🔴 STOP CONDITIONS
Only stop when:
- `docker compose up` brings up Postgres + backend with no errors.
- `GET /health` returns 200 `{"status": "ok"}`.
- `pytest` passes with at least one real test and zero failures — run it and report the
  actual output, don't assume.
- `ruff check` passes with zero errors.
- The config loader raises a clear error when GEMINI_API_KEY or JWT_SECRET is unset
  outside test mode — verified by a test, not just by inspection.
- CI workflow YAML is valid and would run lint + tests on push.

🟣 OUTPUT
Produce:
- /backend/pyproject.toml, /backend/app/main.py, /backend/app/core/config.py
- /backend/tests/test_health.py
- /backend/.env.example (placeholder values only, never real secrets)
- /docker-compose.yml
- /.github/workflows/ci.yml
- /.pre-commit-config.yaml

Then:
- Git branch: phase-1-dev-environment
- Commit message: chore(backend): scaffold FastAPI service, Docker Compose, CI, tooling
- Report: exact pytest output (pass/fail counts), exact ruff output, and confirm
  docker compose up succeeded.
```

---

## PHASE 2 — Database & Domain Model

```
🔵 ROLE
Act as a senior backend engineer specializing in relational schema design for
multi-tenant financial systems, who treats "we'll fix the schema later" as a trap to be
avoided — this schema is the foundation every later phase writes against.

🟠 TASK
Implement the full MVP relational schema — SQLAlchemy 2.x typed models plus an Alembic
migration — for every entity RevenueGuard AI needs through Phase 13: Organization, User,
Role, Permission, Customer, CustomerContact, Contract, ContractLine, Product, Service,
Project, Invoice, InvoiceLine, Payment, PaymentAllocation, Subscription, CreditNote,
RevenueLeakageCase, Evidence, Investigation, RecoveryAction, RecoveryResult, Rule,
RuleVersion, Integration, DataSource, ImportJob, AgentExecution, ToolExecution,
Approval, AuditLog.

🟢 CONTEXT
- Repository has Phase 1's FastAPI + SQLAlchemy + Alembic scaffold running.
- Every tenant-owned table must carry a non-nullable, indexed `organization_id` FK
  (ADR-003 from Phase 0).
- All monetary columns must be NUMERIC(14,2) — never float/double. Confidence/ratio
  columns are NUMERIC(4,3).
- Required enums: LeakageType (20 values — missing_invoice, underbilling,
  pricing_mismatch, quantity_mismatch, discount_leakage, contract_expiration,
  subscription_renewal, late_billing, uncollected_invoice, partial_payment,
  reconciliation_failure, incorrect_credit_note, contract_invoice_conflict,
  duplicate_discount, recurring_billing_failure, usage_billing, minimum_commitment,
  sla_credit, refund_anomaly, other), Severity (critical/high/medium/low), CaseStatus
  (detected/investigating/pending_review/approved/rejected/action_pending/
  action_completed/verified/recovered/false_positive/legitimate_exception/closed),
  EvidenceType, ApprovalDecision (approved/rejected/needs_more_information).
- RevenueLeakageCase needs a human-readable case_number (e.g. RL-000123) distinct from
  its UUID primary key.
- Evidence.snapshot is JSONB and immutable by convention — it stores a point-in-time
  copy of the referenced record so evidence survives later edits to the source record.

🟣 REASONING
Every later phase (rules engine, agents, approval workflow, recovery, verification,
API, frontend) reads and writes this exact schema. A wrong type (float instead of
NUMERIC), a missing tenant filter, or an incorrect cascade rule here produces either a
financial-accuracy bug or a cross-tenant data leak much later, when it's far more
expensive to trace back to its root cause. Get the relationships and types right now.

🔴 STOP CONDITIONS
Only stop when:
- `alembic upgrade head` succeeds against a clean Postgres instance, and
  `alembic downgrade base` also succeeds (migration is reversible).
- Every tenant-owned table has a non-nullable, indexed organization_id — verified by
  reading the migration, not assumed.
- Every monetary column is NUMERIC, never float/double.
- Model tests (instantiate + persist each entity, verify FK constraints, verify enum
  columns reject invalid values) pass — report the actual count.
- Deleting a Contract does not cascade-delete its Invoices (history must be
  preservable) — verified by test.

🟣 OUTPUT
Produce:
- /backend/app/models/*.py (organization, user, customer, contract, project, invoice,
  payment, subscription, leakage, recovery, rules, integration, agent, audit)
- /backend/app/db/session.py
- /backend/alembic/versions/0001_initial_schema.py
- /backend/tests/test_models.py

Then:
- Git branch: phase-2-database-domain-model
- Commit message: feat(db): implement full MVP domain schema with multi-tenant isolation
- Report: migration up/down results, model test pass/fail counts, and any deviation
  from the entity list above with rationale.
```

---

## PHASE 3 — Authentication, Multi-Tenancy & RBAC

```
🔵 ROLE
Act as a senior backend security engineer specializing in multi-tenant SaaS
authorization, who assumes every endpoint written after this phase will trust what you
build here completely — so it must be impossible to misuse by accident.

🟠 TASK
Implement email/password authentication with JWT (access + refresh tokens),
organization self-signup, and the 6-role RBAC matrix (Owner, Admin, Finance Manager,
Accountant, Analyst, Viewer) as reusable FastAPI dependencies — specifically
`get_current_user` and `require_permission(resource, action)` — plus a tenant-scoping
repository base class that every future data-access class will inherit from.

🟢 CONTEXT
- Repository has Phase 2's schema (Organization, User, Role, Permission, plus every
  other MVP entity) migrated and available.
- This phase is explicitly the security foundation for the entire rest of the build:
  from this point forward, organization_id must NEVER be accepted from client input on
  any endpoint anywhere in the codebase — it is always derived server-side from the
  authenticated JWT session.
- Endpoints to build: POST /auth/register (creates Organization + first User as Owner),
  POST /auth/login, POST /auth/refresh, POST /auth/logout, POST
  /auth/password-reset-request, POST /auth/password-reset-confirm, POST /users (invite,
  Owner/Admin only), PATCH /users/{id}/role.
- Password hashing: argon2. JWT: short-lived access token, longer-lived refresh token
  with rotation/revocation.

🟣 REASONING
Every phase from 4 onward assumes tenant isolation and role enforcement "just work"
without re-checking them per endpoint. If this phase leaves a gap — for example, a
repository method that forgets the tenant filter, or a permission check that can be
bypassed — that gap silently propagates into every feature built on top of it, and a
financial SaaS product cannot survive a cross-tenant data leak. This is the one phase
in the whole roadmap where "good enough" is not acceptable.

🔴 STOP CONDITIONS
Only stop when:
- Full register → login → refresh → logout flow works end-to-end, tested.
- All 6 roles enforce distinct permissions per a documented matrix — tested for at
  least one Owner-can/Viewer-cannot case on a write action.
- A dedicated cross-tenant test proves a user from Organization A cannot read or write
  Organization B's data through any exposed mechanism, and gets a 403/404 (never a
  response that reveals Org B's data exists).
- No secret value (password, hash, JWT secret) ever appears in a log line or API
  response — spot-checked.
- An AuditLog entry is written on login success/failure and on role changes.

🟣 OUTPUT
Produce:
- /backend/app/core/security.py, /backend/app/core/deps.py, /backend/app/core/rbac.py
- /backend/app/api/v1/auth.py, /backend/app/api/v1/users.py
- /backend/app/repositories/base.py (tenant-scoping mixin)
- /backend/alembic/versions/0002_seed_roles_permissions.py
- /backend/tests/test_auth.py, /backend/tests/test_rbac.py

Then:
- Git branch: phase-3-auth-multitenancy-rbac
- Commit message: feat(auth): implement JWT auth, org onboarding, and RBAC enforcement
- Report: full test results including the cross-tenant test outcome explicitly.

🚫 EXCLUSIONS: do not implement MFA, OAuth providers, or any business-domain endpoint
(customers/contracts/invoices/etc.) in this phase.
```

---

## PHASE 4 — Data Ingestion Layer

```
🔵 ROLE
Act as a senior data engineer specializing in ETL pipelines for messy, real-world
business data exported from tools finance teams already use (QuickBooks, spreadsheets,
CRM exports).

🟠 TASK
Build CSV and Excel import for the 7 MVP entities (Customer, Contract, ContractLine,
Project, Invoice, InvoiceLine, Payment), with strict per-row validation, per-row error
reporting, idempotent upserts, and a full ImportJob audit trail — plus a stub generic
REST-pull DataSource to prove the integration abstraction without building a real
third-party connector yet.

🟢 CONTEXT
- Repository has Phase 3's auth/RBAC and Phase 2's schema (including ImportJob,
  DataSource) available.
- Endpoint: POST /api/v1/imports (multipart file upload + target_entity + optional
  column-mapping override); GET /api/v1/imports/{id}; GET /api/v1/imports/{id}/errors
  (paginated rejected rows with reasons).
- Money amounts in real-world exports arrive messy (e.g. "$1,200.00") and must be
  parsed defensively into Decimal — never float.
- Imports must be idempotent on a natural key (external_id + organization_id) — a
  re-imported file upserts, it does not duplicate.
- Imports must be tenant-scoped: a file uploaded by an Org A user can only ever create
  or update Org A records.

🟣 REASONING
Every rule, agent, and dashboard number downstream of this phase is only as trustworthy
as the data that entered here. Real customer CSV exports are inconsistent — silently
dropping a bad row, or silently guessing at a missing reference, produces detection
results nobody can trust, which is the exact failure mode (spec Risk 1) that kills a
revenue-leakage product's credibility within one billing cycle.

🔴 STOP CONDITIONS
Only stop when:
- All 7 MVP entities are importable via both CSV and Excel, tested with fixture files.
- A CSV with deliberately malformed rows produces the exact expected
  records_rejected count, each with a specific, human-readable reason — not a generic
  "invalid row" message.
- Re-importing an identical file does not create duplicate records — verified by test.
- Cross-tenant isolation holds for imports — verified by test, not assumed from
  Phase 3's general guarantees.

🟣 OUTPUT
Produce:
- /backend/app/api/v1/imports.py
- /backend/app/services/ingestion/{parsers,validators,importer,rest_source}.py
- /backend/tests/fixtures/sample_customers.csv,
  /backend/tests/fixtures/sample_invoices.xlsx
- /backend/tests/test_ingestion.py

Then:
- Git branch: phase-4-data-ingestion
- Commit message: feat(ingestion): CSV/Excel import pipeline with validation and error
  reporting
- Report: per-entity import test results and the idempotency test outcome.

🚫 EXCLUSIONS: no real Stripe/QuickBooks/Xero connector, no normalization/entity-
resolution logic (Phase 5), no scheduled sync (V1).
```

---

## PHASE 5 — Data Normalization & Entity Resolution

```
🔵 ROLE
Act as a senior data engineer specializing in deterministic record-linkage and
deduplication systems, who treats an auto-merge of two possibly-different real-world
entities as a worse failure than leaving them unlinked for a human to resolve.

🟠 TASK
Build normalization (name/email/phone/address/currency/date canonicalization) and
entity resolution (exact-ID-first, fuzzy-match-fallback linking of Customer, Contract,
Project, Invoice, Payment) with a human review queue for ambiguous matches — entirely
deterministic, no LLM involvement.

🟢 CONTEXT
- Repository has Phase 4's ingestion pipeline producing raw imported rows.
- Canonical example this must solve: "Acme Inc.", "ACME INC", "Acme Incorporated", and
  "ACME" must all resolve to one Customer record.
- Matching priority: an exact external_id match always wins over any fuzzy match.
  Fuzzy matching (e.g. rapidfuzz token-sort-ratio) only applies when no ID match exists.
  High-similarity matches above a configured threshold auto-link; mid-similarity
  matches go to a review queue; low-similarity matches do not link.
- Endpoints: GET /api/v1/entity-resolution/pending, POST
  /api/v1/entity-resolution/{id}/confirm, POST /api/v1/entity-resolution/{id}/reject.

🟣 REASONING
The Phase 6 rules engine and Phase 8 agents both depend on correctly-linked records —
a rule comparing "expected billing" to "actual billing" is meaningless if the Contract
and the Invoice it should be compared against aren't actually joined because their
customer names didn't match exactly. This phase is what makes every later financial
comparison structurally correct rather than accidentally correct on clean fixture data.

🔴 STOP CONDITIONS
Only stop when:
- The exact "Acme Inc." / "ACME INC" / "Acme Incorporated" / "ACME" example resolves
  to a single Customer record in an end-to-end test.
- No auto-merge occurs below the configured high-confidence threshold — ambiguous
  cases are queued, never guessed, verified by test.
- All required FKs (Contract→Customer, Invoice→Customer/Contract/Project,
  Payment→Invoice) are correctly populated for a realistic multi-entity fixture.

🟣 OUTPUT
Produce:
- /backend/app/services/resolution/{normalizer,matcher,review_queue}.py
- /backend/app/api/v1/entity_resolution.py
- /backend/tests/test_normalizer.py, /backend/tests/test_matcher.py

Then:
- Git branch: phase-5-normalization-entity-resolution
- Commit message: feat(resolution): deterministic normalization and entity linking
  with human review queue
- Report: the Acme Inc. test outcome explicitly, plus review-queue behavior at each
  similarity band.

🚫 EXCLUSIONS: no LLM-based matching, no revenue rules engine (Phase 6).
```

---

## PHASE 6 — Deterministic Revenue Rules Engine

```
🔵 ROLE
Act as a senior backend engineer specializing in business-rule engines for financial
systems, who writes every dollar comparison as a unit-tested, hand-verifiable
calculation — because this module is where the product's core credibility is won or
lost.

🟠 TASK
Implement the 6 MVP leakage-detection rules — missing invoice, underbilling, pricing
mismatch, overdue invoice, partial payment discrepancy, contract-expiration leakage —
as versioned, configurable, deterministic Python code that scans normalized data and
emits RevenueLeakageCase candidates with status="detected". No LLM involvement anywhere
in this phase.

🟢 CONTEXT
- Repository has Phase 5's normalized, correctly-linked data available to query.
- Each rule reads its thresholds (e.g. underbilling % threshold, overdue grace period)
  from a Rule/RuleVersion database row, not a hardcoded constant — changing a threshold
  must never require a code deploy.
- All monetary comparisons use Decimal, never float.
- Every emitted RevenueLeakageCase links to the specific RuleVersion that produced it.
- Endpoints: POST /api/v1/rules/run (manual trigger, RBAC-gated), GET/PUT /api/v1/rules,
  GET /api/v1/rules/{id}/versions.
- Rule logic (exact definitions):
  - Missing Invoice: Project.status == "completed" AND contract implies billing AND no
    linked Invoice within the configured billing window.
  - Underbilling: sum(ContractLine.quantity × unit_price) vs
    sum(InvoiceLine.quantity × unit_price) for linked records, difference over a
    configured $/% threshold.
  - Pricing Mismatch: ContractLine.unit_price != InvoiceLine.unit_price for matched
    line items.
  - Overdue Invoice: due_date < today AND outstanding balance > 0.
  - Partial Payment Discrepancy: sum(payments) < Invoice.total with no linked
    CreditNote explaining the gap.
  - Contract Expiration Leakage: Contract.expiration_date < service date AND service
    is billable AND no renewal contract exists.

🟣 REASONING
This is the deterministic half of the architecture the entire product's trustworthiness
rests on (per the product's own principle: use code for money math, AI only for
interpretation). A false positive or false negative here is not an AI hallucination
that can be caught by better prompting later — it's a code bug in arithmetic, which is
unacceptable in a product whose entire value proposition is "trust our numbers."

🔴 STOP CONDITIONS
Only stop when:
- All 6 rules are implemented, each independently unit-tested against a known-answer
  fixture with exact-dollar assertions (not "found something," but "found exactly
  $X").
- The full RuleEngine.run() produces zero false positives and zero false negatives
  against a composite multi-rule fixture dataset.
- Changing a threshold via the /rules API produces measurably different detection
  behavior, verified by test — proving thresholds are truly configuration, not code.
- A legitimate scenario (e.g. a contract amendment reducing price) does not get
  flagged when the fixture includes the amendment link.

🟣 OUTPUT
Produce:
- /backend/app/rules/base.py, /backend/app/rules/{missing_invoice,underbilling,
  pricing_mismatch,overdue_invoice,partial_payment,contract_expiration}.py
- /backend/app/rules/engine.py
- /backend/app/api/v1/rules.py
- /backend/tests/fixtures/rules_scenarios.py, /backend/tests/test_rules_engine.py

Then:
- Git branch: phase-6-revenue-rules-engine
- Commit message: feat(rules): deterministic MVP leakage detection engine for 6 rule
  types
- Report: per-rule test results with exact dollar-amount assertions shown.

🚫 EXCLUSIONS: no Gemini/LLM call anywhere, no evidence/investigation logic (Phase 9),
no confidence scoring beyond a simple rule-strength placeholder.
```

---

## PHASE 7 — Microsoft Agent Framework Foundation + Gemini Connector

```
🔵 ROLE
Act as a senior AI systems engineer with deep, current expertise in Microsoft Agent
Framework and the Gemini API, who never assumes a class name or import path is stable
without checking the actually-installed package version first — because this framework
has changed shape multiple times in 2026.

🟠 TASK
Wire up the `agent_framework` package with its Gemini connector, prove the full
request → tool-call → structured-response loop works against live Gemini with one
trivial smoke-test agent and one read-only tool, and build the reusable tool-layer
scaffold (tenant-scope injection, per-agent authorization, audit logging) that every
real agent in Phase 8 will plug into.

🟢 CONTEXT
- Repository has Phase 1's `agent-framework` dependency installed (unused until now)
  and Phase 3's config loader already exposing GEMINI_API_KEY / GEMINI_MODEL.
- First, inspect the actually-installed agent_framework package (pip show, browse
  site-packages) to confirm current class names for the Gemini chat client, agent
  construction, the function-tool decorator, structured-output configuration, and the
  Workflow/executor/edge primitives. Document findings in
  docs/adr/004-maf-verified-api.md before writing any agent code.
- The tool-layer scaffold must: (a) inject organization_id from the calling context,
  never accept it as an LLM-provided argument, (b) check the calling agent's permitted-
  tool list before dispatch, (c) write a ToolExecution audit row on every call.
- GEMINI_API_KEY must never be logged, returned in any API response, or exposed to the
  frontend.

🟣 REASONING
Every later agent (Phase 8's Contract Analysis, Investigation, and Recovery
Recommendation agents) depends on this scaffold enforcing tenant isolation and
authorization correctly — and depends on the API surface documented in ADR-004 being
accurate, since the framework has broken backward compatibility before. Proving the
loop works against live Gemini now, with a trivial agent, is far cheaper than
discovering an integration mismatch for the first time inside a complex 3-agent
workflow in Phase 8.

🔴 STOP CONDITIONS
Only stop when:
- docs/adr/004-maf-verified-api.md documents the actual verified agent_framework API
  surface used, with the exact version pinned in pyproject.toml.
- gemini_client.py raises a clear, typed error when GEMINI_API_KEY is missing,
  verified by test.
- The tool scaffold provably overrides/rejects a forged organization_id argument, and
  provably rejects a tool call from an agent not authorized for that tool — both
  verified by test, not just present in code.
- Every agent/tool call writes a complete AgentExecution/ToolExecution audit row,
  verified by test.
- The smoke-test agent successfully round-trips through live Gemini at least once (or,
  if no API key was available in this environment, that limitation is explicitly and
  honestly reported).

🟣 OUTPUT
Produce:
- /backend/app/agents/gemini_client.py, /backend/app/agents/tools/base.py,
  /backend/app/agents/tools/smoke_test.py, /backend/app/agents/smoke_test_agent.py
- /backend/app/api/v1/agents.py (dev-gated /agents/smoke-test, /agents/executions)
- /docs/adr/004-maf-verified-api.md
- /backend/tests/test_gemini_client.py (mocked), /backend/tests/test_tool_scaffold.py

Then:
- Git branch: phase-7-maf-gemini-foundation
- Commit message: feat(agents): wire Microsoft Agent Framework with Gemini connector
  and tool authorization scaffold
- Report: the verified API findings from ADR-004, the tenant-scope/authorization test
  results, and either the real smoke-test output or an honest statement that no API key
  was available.

🚫 EXCLUSIONS: no Contract Analysis / Investigation / Recovery Recommendation agents,
no MAF Workflow graph, no connection to real leakage cases (all Phase 8).
```

---

## PHASE 8 — Leakage Detection Workflow & Agents

```
🔵 ROLE
Act as a senior multi-agent systems engineer specializing in financial investigation
workflows, who enforces strict structured outputs everywhere a decision matters and
never lets an agent's free-text prose stand in for a verifiable, evidence-cited
conclusion.

🟠 TASK
Build the three MVP LLM agents — Contract Analysis, Investigation, Recovery
Recommendation — and compose them into an explicit, checkpointed Microsoft Agent
Framework Workflow that takes a rule-detected candidate through evidence gathering,
false-positive/legitimate-exception screening, and a recommended action, pausing at a
stubbed human-approval point.

🟢 CONTEXT
- Repository has Phase 6's rule engine (producing status="detected" cases) and Phase
  7's verified Gemini connector + tool-authorization scaffold + ADR-004 available.
- Build these read-only tools first: get_customer, get_contract, get_contract_lines,
  get_invoice, get_invoice_lines, get_payments, get_project, search_customer_history,
  search_credit_notes, search_contract_amendments — every one tenant-scoped and
  audited through the Phase 7 scaffold.
- Contract Analysis Agent: Gemini structured-output call producing a ContractTerms
  model (billing_frequency, unit_pricing, discount_cap_pct, renewal_terms,
  minimum_commitment, expiration_date).
- Investigation Agent: given a candidate, gathers Evidence (immutable snapshots),
  explicitly searches for legitimate exceptions (amendments, credit notes, disputes,
  cancellations), and returns a structured InvestigationResult with a classification
  enum (confirmed/likely/uncertain/false_positive/legitimate_exception) whose
  explanation field must cite specific evidence_ids — not free text alone.
- If classification is false_positive or legitimate_exception, auto-close the case
  with the full reasoning trail logged (auditable, reversible).
- Recovery Recommendation Agent: for confirmed/likely cases, picks exactly one action
  from a closed vocabulary (create_invoice_draft, send_payment_reminder,
  request_internal_investigation, correct_pricing, contact_account_manager,
  renew_contract, reconcile_payment, issue_correction, escalate_to_finance_manager) via
  a Pydantic Literal/enum field — the model cannot invent a new action type.
- Workflow: CandidateIntake → [ContractAnalysis if needed] → Investigation → (branch:
  closed vs. continue) → RecoveryRecommendation → HumanApprovalPause(stub), with
  checkpointing so an interrupted run resumes rather than restarts.
- Endpoint: POST /api/v1/leakage/{id}/investigate.

🟣 REASONING
This phase is the architectural centerpiece: it's where "AI reasoning" and
"deterministic facts" actually meet. If the classification or recommendation fields
allow loose/optional/free-text output instead of strict enums, every downstream
guarantee (auto-close only on real legitimate_exceptions, only 9 possible recovery
actions, every explanation traceable to real evidence) silently breaks. Getting the
Pydantic schemas strict here is what makes the rest of the product's evidence-based
claims (spec §4.1, §46) actually true rather than aspirational.

🔴 STOP CONDITIONS
Only stop when:
- All 3 agents use strict Pydantic structured outputs with no decision field left as
  free-text-only.
- The workflow correctly sequences Contract Analysis (when needed) → Investigation →
  branch → Recommendation, with checkpointing enabled and verified.
- A test reproduces the "valid contract amendment" false-positive scenario and confirms
  it resolves to legitimate_exception, auto-closed.
- A cross-tenant isolation test for the full agent/tool layer passes (an Investigation
  Agent for Org A's case cannot retrieve Org B's data even if it tried).
- Every workflow run produces a complete, inspectable AgentExecution trail.
- A sparse-data test confirms an agent returns uncertain/insufficient_evidence rather
  than fabricating a conclusion.

🟣 OUTPUT
Produce:
- /backend/app/agents/tools/investigation_tools.py
- /backend/app/agents/{contract_analysis_agent,investigation_agent,
  recovery_recommendation_agent}.py
- /backend/app/agents/schemas.py
- /backend/app/workflows/leakage_investigation_workflow.py
- /backend/app/api/v1/leakage.py (adds /investigate)
- /backend/tests/test_agents_mocked.py, /backend/tests/test_workflow_integration.py

Then:
- Git branch: phase-8-leakage-agents-workflow
- Commit message: feat(agents): implement Contract Analysis, Investigation, and
  Recovery Recommendation agents with explicit MAF workflow
- Report: mocked-test results, and — if GEMINI_API_KEY is available — actual observed
  classifications from a real-API run against one hand-built case per MVP leakage type,
  reported honestly (not assumed to match expectations).

🚫 EXCLUSIONS: no human-approval endpoint/UI (Phase 10 — only the checkpointed pause
point), no recovery action execution (Phase 11), no confidence-score composition
(Phase 9 — use a placeholder).
```

---

## PHASE 9 — Evidence, Confidence & Financial Impact

```
🔵 ROLE
Act as a senior backend engineer specializing in deterministic scoring systems for
financial risk, who treats "confidence score" as a number that must be reproducible
and explainable, never a value pulled from an LLM's own sense of certainty.

🟠 TASK
Replace Phase 8's placeholder confidence value with a real, versioned,
deterministic confidence-composition formula, and finalize the deterministic financial-
impact, severity, and priority calculations — combining rule strength, entity-
resolution confidence, evidence completeness, and the Investigation Agent's
classification into one auditable score per case.

🟢 CONTEXT
- Repository has Phase 6 (rule detection strength), Phase 8 (Investigation
  classification, Evidence records) available.
- ConfidenceScorer: a versioned weighted formula combining detection strength (from
  the rule), entity-resolution confidence (Phase 5's match quality), evidence
  completeness (fraction of expected evidence types present), and the Investigation
  Agent's classification mapped to a numeric contribution — the formula version is
  stored alongside every computed score.
- FinancialImpactCalculator: deterministic expected_amount, actual_amount,
  potential_leakage = expected − actual, recoverable_amount (MVP: equal to
  potential_leakage, field exists for future refinement).
- SeverityClassifier / PriorityClassifier: deterministic, configurable threshold
  tables (financial impact × confidence × age → critical/high/medium/low).
- Persist confidence, severity, priority, and the four financial-impact fields on
  RevenueLeakageCase, plus a confidence_breakdown JSONB showing each component score.
- Build the final case.explanation text by combining the Investigation Agent's
  evidence-cited narrative with the deterministic financial calculation.

🟣 REASONING
A confidence number that can't be decomposed into its inputs is not auditable, and an
un-auditable confidence score is exactly what a CFO buyer will distrust first. By
keeping this entirely deterministic and versioned, a finding's confidence can always be
explained ("94% because: 95% detection strength, 98% entity-resolution confidence, 90%
evidence completeness, 91% agent assessment") rather than asserted.

🔴 STOP CONDITIONS
Only stop when:
- The confidence formula is versioned, documented, and reproduces a known worked
  example (0.95/0.98/0.90/0.91 component inputs → ~0.94 final, or the derived formula's
  actual output for those inputs, documented in a docstring).
- Financial impact fields are all Decimal-backed and match hand-computed values on the
  Phase 6 fixture dataset.
- Severity/priority classification is tested explicitly at its threshold boundaries.
- Every case reaching pending_review has a complete, non-null confidence/severity/
  priority/financial-impact set.

🟣 OUTPUT
Produce:
- /backend/app/scoring/{confidence,financial_impact,severity_priority,
  explanation_builder}.py
- /backend/tests/test_confidence_scorer.py, /backend/tests/test_financial_impact.py,
  /backend/tests/test_severity_priority.py

Then:
- Git branch: phase-9-evidence-confidence-financial-impact
- Commit message: feat(scoring): deterministic confidence, severity, priority, and
  financial impact calculation
- Report: the worked-example reproduction result and boundary-test results explicitly.

🚫 EXCLUSIONS: LLM agents must never compute or override any of these numeric fields;
no approval endpoints yet (Phase 10).
```

---

## PHASE 10 — Human Approval Workflow

```
🔵 ROLE
Act as a senior backend engineer specializing in workflow state machines and approval
systems for financial software, who treats every status transition as something that
must be explicitly allowed, never implicitly possible.

🟠 TASK
Implement the full 12-status case state machine and the Approve/Reject/Assign/Snooze/
Request-Evidence actions on a RevenueLeakageCase, with an Approval record captured on
every decision, and wire Approve to resume Phase 8's checkpointed workflow pause point.

🟢 CONTEXT
- Repository has Phase 8's checkpointed workflow and Phase 9's fully-scored
  pending_review cases available.
- Statuses: detected, investigating, pending_review, approved, rejected, action_pending,
  action_completed, verified, recovered, false_positive, legitimate_exception, closed —
  implement as one explicit transition table, not scattered per-endpoint logic; any
  transition not in the table must be rejected.
- Endpoints: POST /leakage/{id}/approve (RBAC: Finance Manager/Accountant/Admin/Owner,
  not Analyst/Viewer; creates Approval row; resumes the MAF workflow checkpoint), POST
  /leakage/{id}/reject (requires a reason), POST /leakage/{id}/assign, POST
  /leakage/{id}/close, plus snooze (sets snoozed_until, excludes case from default
  inbox until then) and request-evidence (re-triggers a scoped Investigation Agent
  re-run).
- Every approval-flow endpoint writes an AuditLog row.

🟣 REASONING
This is the literal human-in-the-loop gate the entire product's safety story depends
on — no financial action may proceed without a human decision recorded here. If the
state machine allows an illegal transition (e.g., re-approving an already-recovered
case, or approving without recording who/why), the audit trail this product sells to
finance teams as trustworthy becomes unreliable.

🔴 STOP CONDITIONS
Only stop when:
- All 12 statuses and their legal transitions are enforced by one single source-of-
  truth state machine.
- Approve/reject/assign/close/snooze/request-evidence are all implemented, RBAC-gated,
  and audit-logged.
- At least one illegal transition attempt is tested and confirmed rejected with a
  clear error.
- Approving a case is verified to correctly signal the Phase 8 workflow checkpoint to
  resume.

🟣 OUTPUT
Produce:
- /backend/app/services/case_state_machine.py
- /backend/app/api/v1/leakage_approval.py (or extend leakage.py)
- /backend/app/workflows/resume.py
- /backend/tests/test_case_state_machine.py, /backend/tests/test_approval_endpoints.py

Then:
- Git branch: phase-10-human-approval-workflow
- Commit message: feat(approval): case state machine, approval capture, and workflow
  resume
- Report: state-machine test coverage (legal and illegal transitions) and the
  checkpoint-resume test result.

🚫 EXCLUSIONS: do not implement what happens after approval beyond signaling the
resume — no invoice-draft generation, no email sending (Phase 11).
```

---

## PHASE 11 — Recovery Action System (Draft-Only)

```
🔵 ROLE
Act as a senior backend engineer specializing in controlled action-execution systems
for financial software, who treats "send a real email" and "generate a draft a human
must approve and manually act on" as two categorically different levels of risk that
require two categorically different levels of authorization.

🟠 TASK
Build the post-approval RecoveryAction system, strictly limited to draft artifacts:
draft invoice-correction content, draft reminder email text, or an internal finance
task — nothing is sent to a customer or posted to accounting automatically in this
phase. Require a second, explicit approval gate before a draft can be marked acted-on.

🟢 CONTEXT
- Repository has Phase 10 (approved cases resuming the workflow) and Phase 8's
  RecoveryRecommendation (action type + rationale) available.
- Draft content is generated via deterministic templating fed only by Phase 9's
  verified financial-impact numbers — never LLM free-generation of dollar amounts.
- create_invoice_draft → structured draft invoice (customer, line items derived from
  the case's expected-vs-actual delta, amount) as RecoveryAction with
  draft_content JSONB, status="draft".
- send_payment_reminder → templated reminder text interpolating only verified case
  facts. Other action types → internal task records.
- Endpoints: GET /recovery/{case_id} (view draft), POST /recovery/{case_id}/approve
  (a SECOND, distinct approval specifically releasing the draft — separate from the
  Phase 10 case-level approval — to status="ready_for_manual_action"), POST
  /recovery/{case_id}/execute (marks action_completed only after a human confirms they
  manually acted on it outside the system; captures who/when).
- Update RevenueLeakageCase.status to action_pending on draft creation, then
  action_completed on execute-confirmation.

🟣 REASONING
This is the highest-liability phase in the MVP. Approving that a leakage case is real
is not the same authorization as approving that a specific draft artifact is correct
and safe to act on — collapsing those into one approval would let a single click
trigger a financial mistake. The two-gate design, plus refusing to ever auto-generate
a dollar figure the LLM invented, is what keeps this phase from becoming the incident
that ends the product's credibility.

🔴 STOP CONDITIONS
Only stop when:
- All 6+ recovery action types produce sensible draft content or an internal task
  record.
- No action can reach action_completed without an explicit human-confirmation audit
  trail — verified by test.
- Draft financial figures are provably identical (exact equality, not approximate) to
  Phase 9's deterministic potential_leakage figure — verified by test.
- The two distinct approval gates (case-level, draft-release-level) are both enforced
  — attempting /execute before the draft-release approval must fail, verified by test.

🟣 OUTPUT
Produce:
- /backend/app/services/recovery/{action_drafter,templates}.py
- /backend/app/api/v1/recovery.py
- /backend/tests/test_action_drafter.py, /backend/tests/test_recovery_endpoints.py

Then:
- Git branch: phase-11-recovery-action-draft
- Commit message: feat(recovery): draft-only recovery action generation with dual
  approval gates
- Report: the dollar-equality test result and the two-gate enforcement test result
  explicitly.

🚫 EXCLUSIONS: no real email sending, no real external invoice/CRM record creation, no
Stripe/QuickBooks/email-provider integration — draft and manual-confirmation tracking
only.
```

---

## PHASE 12 — Verification & Recovery Tracking

```
🔵 ROLE
Act as a senior backend engineer specializing in closed-loop financial reconciliation,
who insists a "recovered" status must be provably backed by real invoice and payment
data, never just an assumption that an action worked.

🟠 TASK
Implement the Verification step that checks whether an action_completed case actually
resulted in recovered revenue, and compute the org-level recovery metrics
(potential/confirmed leakage, recovered revenue, recovery rate) that will feed the
Phase 14 dashboard.

🟢 CONTEXT
- Repository has Phase 11 (action_completed cases) and Phase 4 (ingestion, since new
  Invoice/Payment data arrives via later imports) available.
- VerificationExecutor.check(case): for create_invoice_draft-type actions, look for a
  new Invoice linked to the same customer/contract with an amount matching (within
  tolerance) case.potential_leakage, created after the action's confirmed_at; if found,
  check for a linked Payment fully covering it.
- Support partial verification: invoice exists but unpaid → status verified (not yet
  recovered); once payment data arrives via a later import, re-check and transition to
  recovered.
- Endpoint: POST /leakage/{id}/reverify, plus auto-run this check scoped to the case's
  org as part of every subsequent ingestion for cases in action_completed/verified.
- If no matching invoice appears after a configurable grace period, flag
  needs_follow_up rather than leaving the case in silent limbo.
- Compute org-level metrics as a single reusable service function: total_potential_
  leakage, total_confirmed_leakage, total_recovered_revenue, open_cases, critical_cases,
  recovery_rate.

🟣 REASONING
This phase is what turns "we detected $182,400 in potential leakage" into "we recovered
$74,500 of it" — the actual metric that proves the product works (spec §69's core
success condition). Skipping the grace-period follow-up flag would let cases silently
rot in action_completed forever with no visibility, quietly undermining the very
recovery-rate number the whole product is sold on.

🔴 STOP CONDITIONS
Only stop when:
- A known worked example ($20,000 leakage → invoice created → payment received →
  recovered_amount = exactly $20,000, recovery rate 100% for that case) reproduces
  exactly in a test.
- The partial-verification path (invoice exists, unpaid → verified, not recovered) is
  tested explicitly.
- Org-level recovery metrics compute correctly against a multi-case fixture.
- The grace-period follow-up flag fires correctly when no matching invoice appears in
  time, verified by test.

🟣 OUTPUT
Produce:
- /backend/app/services/verification/{verification_executor,metrics}.py
- /backend/app/api/v1/verification.py
- /backend/tests/test_verification.py, /backend/tests/test_recovery_metrics.py

Then:
- Git branch: phase-12-verification-recovery-tracking
- Commit message: feat(verification): closed-loop recovery verification and org-level
  recovery metrics
- Report: the worked-example test result and the follow-up-flag test result
  explicitly.

🚫 EXCLUSIONS: no dashboard UI (Phase 14), no new external integration.
```

---

## PHASE 13 — Backend API Completion

```
🔵 ROLE
Act as a senior backend engineer focused on API consistency and completeness across an
entire service, who treats an inconsistent pagination pattern or a missed permission
check as a defect worth fixing now rather than patching per-frontend-page later.

🟠 TASK
Fill in the remaining CRUD/read endpoints (Customer, Contract, Invoice, Payment as
first-class browsable resources), the full filterable Leakage Inbox listing, customer
revenue-health aggregation, and global search — with consistent pagination, filtering,
and RBAC enforcement across the whole API — so the frontend has everything it needs.

🟢 CONTEXT
- Repository has Phases 2–12 complete; this phase is integration/completion, adding no
  new domain logic.
- GET /leakage must support the full filter set: leakage type, amount range, customer,
  severity, confidence range, status, date range — as composable SQLAlchemy filters,
  never string-concatenated SQL.
- GET /customers/{id}/revenue-health must aggregate: contract value, invoiced amount,
  paid amount, outstanding amount, potential leakage, recovery history, active
  subscriptions.
- GET /search must support cross-entity search (customer name, contract number,
  invoice number, case number) via indexed ILIKE/trigram search.
- Every list endpoint needs a sane max page size and a sensible default sort.
- This phase includes a full RBAC audit: list every endpoint × required permission ×
  actual dependency used, and fix any gap found.

🟣 REASONING
This is the last checkpoint before the frontend is built on top of the API — any
inconsistency in pagination, filtering, or a missed permission check here becomes a
frontend workaround or a real vulnerability if it ships. Auditing the full permission
matrix now, rather than trusting each earlier phase got it exactly right in isolation,
catches drift that accumulates across 10+ phases of incremental endpoint-adding.

🔴 STOP CONDITIONS
Only stop when:
- All listed endpoints are implemented, paginated, and filterable per the Leakage
  Inbox filter set.
- Revenue-health aggregation matches hand-computed values on a fixture, verified by
  test.
- The RBAC audit has been performed and documented, and any gap found has been fixed
  within this phase — not just flagged for later.
- /openapi.json is complete and internally consistent.

🟣 OUTPUT
Produce:
- /backend/app/api/v1/{customers,contracts,invoices,payments}.py (extended)
- /backend/app/api/v1/leakage.py (extended with full listing/filtering)
- /backend/app/api/v1/search.py
- /backend/tests/test_api_customers.py, /backend/tests/test_api_leakage_filters.py,
  /backend/tests/test_api_search.py

Then:
- Git branch: phase-13-backend-api-completion
- Commit message: feat(api): complete CRUD, filtering, search, and revenue-health
  endpoints
- Report: the RBAC audit findings (including any gaps found and fixed), and filter/
  pagination test results.

🚫 EXCLUSIONS: no frontend work (Phase 14), no new detection logic, no new
integrations.
```

---

## PHASE 14 — SaaS Frontend (MVP)

```
🔵 ROLE
Act as a senior frontend engineer specializing in data-dense, trustworthy B2B financial
dashboards, who deliberately avoids generic "AI chatbot" visual patterns because the
product's credibility depends on looking like professional revenue-operations software,
not a demo.

🟠 TASK
Build the MVP UI: Executive Dashboard, Leakage Inbox, Case Detail, Customer Revenue
Health, Recovery Center, and an Imports page — with a global search bar and an
authenticated, RBAC-aware navigation — as "Cases + Evidence + Actions," never
"Chat + Prompt Box."

🟢 CONTEXT
- Repository has Phase 13's complete, filterable API surface and Phase 3's auth
  endpoints available.
- Dashboard: potential leakage, confirmed leakage, recovered revenue, recovery rate,
  open cases, critical cases, leakage trend, top categories.
- Leakage Inbox: table columns — Case ID, Customer, Type, Amount, Confidence, Severity,
  Age, Status, Owner — with every filter from the API (type, amount, customer,
  severity, confidence, status, date).
- Case Detail: Summary (amount/confidence/severity), "Why was this detected?" (agent
  explanation), Evidence (linked records), Financial Calculation (expected/invoiced/
  difference), Timeline, Recommended Action, Approve/Reject/Assign/Snooze buttons, and
  the Phase 11 draft-recovery-action view.
- Customer Revenue Health: contract value, invoiced/paid/outstanding amounts,
  potential leakage, recovery history, billing anomalies, active subscriptions.
- Recovery Center: potential/confirmed/approved/in-progress/recovered/failed/rejected
  pipeline view plus recovery metrics.
- Imports page: upload CSV/Excel, view ImportJob history and per-row errors.
- RBAC-restricted actions must be both hidden in the UI and confirmed still rejected
  server-side if attempted directly.

🟣 REASONING
This phase is where every deterministic calculation, every piece of agent-gathered
evidence, and every approval gate built in Phases 6–13 either becomes visible and
trustworthy to a finance buyer, or gets buried behind a UI that looks like every other
AI-dashboard template. The spec is explicit that the primary interface is evidence and
action, not conversation — that choice is what signals "financial software" instead of
"AI toy" to the exact skeptical buyer this product needs to win over.

🔴 STOP CONDITIONS
Only stop when:
- All 6 pages are implemented, navigable, and backed by real API data — no mock data
  left in place.
- Case Detail correctly renders evidence, explanation, financial calculation, and
  timeline for a real case created via the actual backend pipeline (not a hand-crafted
  test fixture only).
- Approve/Reject actions correctly update case status and reflect in the UI without a
  full page reload.
- At least one RBAC-restricted action is spot-checked: hidden in the UI for a
  lower-privileged role AND confirmed still rejected server-side if attempted directly.

🟣 OUTPUT
Produce:
- /frontend/src/pages/{Dashboard,LeakageInbox,CaseDetail,CustomerRevenueHealth,
  RecoveryCenter,Imports,Login}.tsx
- /frontend/src/api/client.ts, /frontend/src/api/hooks/*.ts
- /frontend/src/components/*, /frontend/src/routes.tsx

Then:
- Git branch: phase-14-saas-frontend-mvp
- Commit message: feat(frontend): implement MVP dashboard, leakage inbox, case detail,
  and recovery center
- Report: which pages were verified against real backend data end-to-end, and the
  RBAC spot-check result.

🚫 EXCLUSIONS: no chat-first primary UX, no rules-configuration UI beyond a simple
read view, no V1 integration-connect flows (Stripe/QuickBooks).
```

---

## PHASE 15 — Observability & Evaluation Framework

```
🔵 ROLE
Act as a senior MLOps/AI-systems engineer specializing in evaluation harnesses for
production LLM systems, who refuses to let "the demo looked good" stand in for a
measured precision/recall number.

🟠 TASK
Build a seeded synthetic evaluation dataset with known injected leakage cases, an
automated metrics pipeline (precision, recall, false-positive rate, amount accuracy,
time-to-detection), a CI gate that fails the build on regression, and agent-execution
observability (latency, token usage, cost, error rates) with end-to-end correlation IDs.

🟢 CONTEXT
- Repository has Phases 6, 8, 9, 12 (the full detect → investigate → score → verify
  pipeline) available.
- Dataset scale: ~200 customers, ~50 contracts, ~500 invoices, ~500 payments, ~50
  projects, seeded/reproducible, with known ground-truth labels for every injected
  leakage case (type + expected amount) AND a matching set of genuinely clean/
  legitimate records including deliberate near-misses (amended contracts, valid credit
  notes) to test false-positive resistance.
- Metrics: precision, recall, false-positive rate, amount accuracy (mean absolute
  percentage error vs. known amounts), time-to-detection — computed against ground
  truth.
- CI evaluation job runs mocked by default (fast, no API cost) with a flag for real-
  Gemini periodic/manual runs; fails the build if recall drops below a configured floor
  or FPR exceeds a configured ceiling.
- Add a correlation ID (execution_id/case_id) threaded through rule execution, agent
  execution, and tool execution so any case is traceable end-to-end.
- Evaluation data lives in its own isolated tenant so it can never be mistaken for or
  leak into real customer data.

🟣 REASONING
A revenue-leakage product that cannot state its own precision and recall is not
credible to the finance buyer it's built for — this phase is where the product proves,
with numbers, that Phases 6 through 12 actually work together correctly, rather than
just working on the one demo scenario everyone has already seen.

🔴 STOP CONDITIONS
Only stop when:
- The dataset generator is seeded/reproducible and matches the target scale and
  injected-case counts.
- The metrics pipeline computes and reports precision, recall, FPR, amount accuracy,
  and time-to-detection against a real pipeline run — actual numbers included in the
  final report, not estimated.
- The CI evaluation gate is proven to actually fail when a synthetic "bad" run is fed
  in (e.g., a rule deliberately disabled) — verified, not assumed.
- Every case is traceable end-to-end via a correlation ID across rule/agent/tool
  execution logs, verified by test.

🟣 OUTPUT
Produce:
- /backend/eval/{generate_dataset,ground_truth,metrics,run_evaluation}.py
- /backend/tests/test_evaluation_pipeline.py
- /.github/workflows/evaluation.yml
- /backend/app/api/v1/observability.py

Then:
- Git branch: phase-15-observability-evaluation
- Commit message: feat(eval): synthetic evaluation dataset, precision/recall metrics
  pipeline, and agent observability
- Report: the actual measured precision/recall/FPR/amount-accuracy numbers from a real
  run, and confirm the CI gate's fail-case was actually exercised.

🚫 EXCLUSIONS: do not tune detection thresholds purely to make evaluation numbers look
good without separately reporting and justifying any threshold change.
```

---

## PHASE 16 — Security Hardening

```
🔵 ROLE
Act as a senior application security engineer specializing in financial SaaS, who
assumes prior phases already implemented baseline security correctly and treats this
phase as an adversarial verification pass, not a first attempt.

🟠 TASK
Conduct a structured security review across everything built in Phases 3–14: dependency
vulnerabilities, rate limiting, input validation, adversarial tenant-isolation testing,
secrets auditing, and adversarial prompt-injection testing against the agent tool
scaffold — closing every gap found.

🟢 CONTEXT
- Repository has all backend phases (2–13) and the frontend (14) complete.
- Adversarial tenant-isolation suite: for every resource type, attempt cross-tenant
  read/write/list and assert uniform 403/404/empty-result behavior — this is the single
  most important test suite in this phase given the product's financial-data
  sensitivity.
- Adversarial prompt-injection test: feed a deliberately malicious contract document
  text sample into the Phase 8 pipeline and confirm it cannot cause an agent to call a
  tool it wasn't granted, or to pass a different organization_id than the case's own —
  confirming the Phase 7 scaffold's server-side override actually holds under attack,
  not just in the happy path.
- Secrets audit must check the full repo history, not just current state.
- Document a security runbook (docs/SECURITY.md): what to do on a suspected key leak,
  suspected cross-tenant exposure, or a failed audit-log write.

🟣 REASONING
A financial SaaS product's entire commercial viability rests on tenant isolation and
controlled agent behavior holding under adversarial conditions, not just normal usage —
this phase exists specifically to try to break the guarantees earlier phases assumed
they had, before a real customer or attacker does it first.

🔴 STOP CONDITIONS
Only stop when:
- Zero unresolved high/critical dependency vulnerabilities remain (or each has an
  explicit, written risk-acceptance rationale).
- The adversarial tenant-isolation suite passes across every resource type.
- The adversarial prompt-injection test against the agent tool scaffold passes.
- No secret appears in logs, git history, or API responses — verified, not assumed.
- docs/SECURITY.md exists and is specific to this system, not generic boilerplate.

🟣 OUTPUT
Produce:
- /docs/SECURITY.md
- /backend/tests/test_tenant_isolation_adversarial.py,
  /backend/tests/test_agent_prompt_injection.py
- /.github/workflows/security-scan.yml

Then:
- Git branch: phase-16-security-hardening
- Commit message: fix(security): close hardening findings, add adversarial
  tenant-isolation and prompt-injection test suites
- Report: every real finding discovered and exactly how it was fixed — never state "no
  issues found" without describing what was actually tried.
```

---

## PHASE 17 — Production Deployment

```
🔵 ROLE
Act as a senior DevOps/platform engineer specializing in simple, reproducible
containerized SaaS deployment, who resists adding infrastructure complexity (like
Kubernetes or a service mesh) that an MVP with a handful of design-partner tenants does
not need.

🟠 TASK
Produce a reproducible, environment-parameterized deployment — production Dockerfiles,
a secrets-manager strategy, a scripted migration rollout with rollback, lightweight
uptime/error monitoring, automated Postgres backups, and a deployment runbook — then
smoke-test the fully deployed stack end-to-end.

🟢 CONTEXT
- Repository has Phase 16's hardened, tested system.
- Architecture stays intentionally simple: one deployable backend service, one
  frontend static build, one managed Postgres instance — matching the project's own
  "simplest architecture that solves the problem" principle.
- Production secrets (GEMINI_API_KEY, DB credentials, JWT secret) must come from a
  proper secrets manager in prod, never plain .env files or baked into images.
- Deployment runbook (docs/DEPLOYMENT.md) must cover: deploying a new version, rolling
  back, rotating the Gemini API key without downtime, restoring from a Postgres backup.

🟣 REASONING
This phase's job is to make the already-correct, already-hardened system actually
reachable somewhere real, without introducing new complexity or new security regressions
in the process — a common failure mode is hardening that only existed in dev config and
quietly doesn't carry over to prod; this phase must prove it does.

🔴 STOP CONDITIONS
Only stop when:
- Backend and frontend both build and run as containers with no dev-only shortcuts
  (no DEBUG=true default, no permissive CORS wildcard in prod config).
- Migrations run automatically and safely as part of deploy, with a documented and
  tested rollback path.
- A full register → import → detect → approve → dashboard smoke test passes against
  the actual deployed environment — real observed results reported, not a plan to do
  it later.
- docs/DEPLOYMENT.md is complete enough that someone unfamiliar with the project could
  deploy a new version from it alone.

🟣 OUTPUT
Produce:
- /backend/Dockerfile, /frontend/Dockerfile (or static-hosting build config)
- /docs/DEPLOYMENT.md
- /scripts/deploy.sh, /scripts/rollback.sh

Then:
- Git branch: phase-17-production-deployment
- Commit message: chore(deploy): production containerization, migration rollout, and
  deployment runbook
- Report: the real smoke-test results from the deployed environment, and confirm
  Phase 16's hardening (rate limits, security headers) is verifiably active in the
  deployed config, not just in dev.

🚫 EXCLUSIONS: no Kubernetes, no service mesh, no microservice decomposition — keep
this the simplest deployment that reliably runs the existing monolith-plus-managed-
Postgres architecture.
```
