# RevenueGuard AI — Security Runbook

## Overview

This document provides incident response procedures specific to RevenueGuard AI.
It is NOT generic boilerplate — every section references actual system components.

## 1. Suspected API Key Leak (GEMINI_API_KEY)

**Immediate actions:**
1. Rotate the key in Google AI Studio immediately
2. Update the GEMINI_API_KEY environment variable in all environments
3. Check git history: `git log --all -p -S "GEMINI_API_KEY"` to confirm no key was committed
4. Check `.env` files: `git ls-files '*.env*'` — only `.env.example` should be tracked
5. If a key was committed, it is compromised — rotate and ensure the old key is deleted

**Verification:**
- GEMINI_API_KEY is loaded from environment variables via pydantic-settings (app/core/config.py)
- It is NEVER hard-coded, logged, returned in API responses, or exposed to the frontend
- The gemini_client.py raises GeminiClientError if the key is missing

**Prevention:**
- Pre-commit hooks scan for API key patterns
- CI workflow includes a secrets scanning step
- No default values for GEMINI_API_KEY outside test mode

## 2. Suspected Cross-Tenant Data Exposure

**Immediate actions:**
1. Identify the affected resource types (customers, contracts, invoices, cases)
2. Check AuditLog entries for the suspected unauthorized access
3. Verify the tenant-scoping filter is applied on all queries

**How tenant isolation works:**
- Every tenant-owned entity has a non-nullable `organization_id` FK (ADR-003)
- The `get_current_user` dependency (app/core/deps.py) extracts org_id from JWT
- The `require_permission` dependency (app/core/rbac.py) checks role permissions
-organization_id is NEVER accepted from client input — always derived server-side

**Verification:**
- Run adversarial tenant-isolation tests: `pytest tests/test_tenant_isolation_adversarial.py`
- Check that every list endpoint filters by organization_id
- Verify the tool scaffold overrides forged organization_id arguments

**If confirmed:**
1. Immediately revoke all active sessions for the affected tenant
2. Review all API logs for the affected time period
3. Notify affected customers per your data breach notification policy
4. File incident report with root cause analysis

## 3. Failed Audit Log Write

**Immediate actions:**
1. Check if the AuditLog table is accessible
2. Verify the database connection is healthy
3. Check for any SQLAlchemy errors in application logs

**How audit logging works:**
- AuditLog entries are written on: login success/failure, role changes,
  case approvals/rejections, agent executions, tool executions
- The AuditLog model (app/models/audit.py) stores: user_id, org_id, action,
  resource_type, resource_id, details (JSONB), ip_address, timestamp

**Verification:**
- Query AuditLog for recent entries: check that entries exist for all
  approval actions, login attempts, and agent executions
- Run: `pytest tests/test_auth.py` to verify audit logging on login

**If audit logging fails:**
1. The system should continue operating (audit logging is non-blocking)
2. Investigate the root cause (database issue, model mismatch)
3. Repair the logging pipeline
4. Consider any actions during the gap as "unaudited" and flag for review

## 4. Agent Behavior Anomaly

**Immediate actions:**
1. Check AgentExecution records for the suspicious case
2. Review the tool execution log for unauthorized tool calls
3. Verify the correlation_id threading works (case → agent → tool)

**How agent behavior is controlled:**
- Agents use Microsoft Agent Framework with Google Gemini
- The tool scaffold (app/agents/tools/base.py) enforces:
  - Server-side organization_id override (prevents cross-tenant tool calls)
  - Per-agent authorized tool list (prevents unauthorized tool calls)
  - Audit logging on every tool execution
- Structured outputs (Pydantic schemas) prevent free-text decision fields

**Verification:**
- Run adversarial prompt-injection tests: `pytest tests/test_agent_prompt_injection.py`
- Check that all agent executions have complete audit trails
- Verify correlation_id links rule → agent → tool execution

**If agent behaves unexpectedly:**
1. The tool scaffold should have blocked unauthorized actions
2. Check if the authorization check was bypassed (this would be a critical bug)
3. Review the AgentExecution and ToolExecution audit records
4. If the scaffold failed, treat as a P0 security incident

## 5. JWT Token Compromise

**Immediate actions:**
1. All tokens use HS256 with JWT_SECRET — if JWT_SECRET is compromised, ALL tokens are invalid
2. Rotate JWT_SECRET immediately
3. All users will need to re-authenticate (tokens signed with old secret will fail verification)

**How JWT works:**
- Access tokens: 15-minute expiry, contain user_id, org_id, role
- Refresh tokens: 7-day expiry, single-use with rotation
- JWT_SECRET is loaded from environment, never logged or committed

**Verification:**
- `decode_token()` in app/core/security.py verifies signature and expiry
- Refresh token rotation invalidates old tokens on each use

## 6. Password Security

**How passwords are handled:**
- Hashed with argon2 (OWASP recommendation) — never bcrypt
- Hashes are NEVER returned in API responses or logs
- Password reset uses time-limited tokens (stub in MVP)

**Verification:**
- Run: `pytest tests/test_auth.py::TestPasswordHashing`
- Verify no plaintext passwords appear in any log or response

## 7. Dependency Vulnerabilities

**Procedure:**
1. Run `pip-audit` monthly: `pip-audit --desc`
2. Check for known CVEs in: FastAPI, SQLAlchemy, PyJWT, passlib, Pydantic
3. Update dependencies promptly for critical/high CVEs
4. Document any risk-accepted vulnerabilities in this file

**Current dependency status:**
- FastAPI: 0.138.0 (check for updates)
- PyJWT: 2.13.0 (current)
- SQLAlchemy: 2.0.52 (current)
- Pydantic: 2.13.4 (current)

## 8. Rate Limiting

**Current limits:**
- Login: 10 attempts per 5 minutes per IP
- Register: 5 attempts per 10 minutes per IP
- Password reset: 3 attempts per 15 minutes per IP

**If rate limiting is triggered:**
- The client receives HTTP 429 with retry-after information
- This is expected behavior — no action needed unless it's a false positive

## 9. Security Testing

**Run all security tests:**
```bash
# Tenant isolation (adversarial)
pytest tests/test_tenant_isolation_adversarial.py -v

# Prompt injection resistance
pytest tests/test_agent_prompt_injection.py -v

# Auth security
pytest tests/test_auth.py -v

# RBAC enforcement
pytest tests/test_rbac.py -v
```

**CI security gate:**
- `.github/workflows/security-scan.yml` runs on every push
- Checks for dependency vulnerabilities, secrets in code, and security test failures
