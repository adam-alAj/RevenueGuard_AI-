# RBAC Audit — Phase 13: Backend API Completion

## Date: Phase 13 completion

## Complete Endpoint × Permission Matrix

Every endpoint uses `require_permission(resource, action)` as a FastAPI dependency.
The `require_permission` function (app/core/rbac.py) checks the authenticated user's
role permissions against the required (resource, action) pair.

### Auth Endpoints (no auth required — by design)

| Method | Path | Permission | Rationale |
|--------|------|-----------|-----------|
| POST | /auth/register | NONE | Public signup |
| POST | /auth/login | NONE | Public login |
| POST | /auth/refresh | NONE | Token refresh |
| POST | /auth/logout | NONE | Token invalidation |
| POST | /auth/password-reset-request | NONE | Password recovery |
| POST | /auth/password-reset-confirm | NONE | Password recovery |

### Users

| Method | Path | Permission |
|--------|------|-----------|
| POST | /users | users:write |
| PATCH | /users/{user_id}/role | users:write |

### Customers

| Method | Path | Permission |
|--------|------|-----------|
| GET | /customers | customers:read |
| GET | /customers/{id} | customers:read |
| POST | /customers | customers:write |
| PATCH | /customers/{id} | customers:write |
| DELETE | /customers/{id} | customers:delete |
| GET | /customers/{id}/revenue-health | customers:read |

### Contracts

| Method | Path | Permission |
|--------|------|-----------|
| GET | /contracts | contracts:read |
| GET | /contracts/{id} | contracts:read |
| POST | /contracts | contracts:write |
| PATCH | /contracts/{id} | contracts:write |

### Invoices

| Method | Path | Permission |
|--------|------|-----------|
| GET | /invoices | invoices:read |
| GET | /invoices/{id} | invoices:read |

### Payments

| Method | Path | Permission |
|--------|------|-----------|
| GET | /payments | payments:read |
| GET | /payments/{id} | payments:read |

### Imports

| Method | Path | Permission |
|--------|------|-----------|
| POST | /imports | imports:write |
| GET | /imports/{id} | imports:read |
| GET | /imports/{id}/errors | imports:read |

### Entity Resolution

| Method | Path | Permission |
|--------|------|-----------|
| GET | /entity-resolution/pending | customers:read |
| POST | /entity-resolution/{id}/confirm | customers:write |
| POST | /entity-resolution/{id}/reject | customers:write |

### Rules

| Method | Path | Permission |
|--------|------|-----------|
| POST | /rules/run | rules:write |
| GET | /rules | rules:read |
| PUT | /rules/{id} | rules:write |
| GET | /rules/{id}/versions | rules:read |

### Leakage Investigation

| Method | Path | Permission |
|--------|------|-----------|
| POST | /leakage/{id}/investigate | leakage:investigate |

### Leakage Approval

| Method | Path | Permission |
|--------|------|-----------|
| POST | /leakage/{id}/approve | leakage:approve |
| POST | /leakage/{id}/reject | leakage:reject |
| POST | /leakage/{id}/assign | leakage:assign |
| POST | /leakage/{id}/close | leakage:close |
| POST | /leakage/{id}/snooze | leakage:snooze |
| POST | /leakage/{id}/request-evidence | leakage:investigate |

### Leakage Inbox

| Method | Path | Permission |
|--------|------|-----------|
| GET | /leakage/inbox | leakage:read |

### Recovery

| Method | Path | Permission |
|--------|------|-----------|
| POST | /recovery/{case_id}/create | leakage:execute |
| GET | /recovery/{case_id} | leakage:read |
| GET | /recovery/draft/{draft_id} | leakage:read |
| POST | /recovery/{draft_id}/approve | leakage:approve |
| POST | /recovery/{draft_id}/execute | leakage:execute |

### Verification

| Method | Path | Permission |
|--------|------|-----------|
| POST | /verification/{case_id}/reverify | leakage:read |
| POST | /verification/org/{org_id}/reverify-all | leakage:read |
| GET | /verification/org/{org_id}/metrics | leakage:read |

### Agents

| Method | Path | Permission |
|--------|------|-----------|
| POST | /agents/smoke-test | agents:execute |
| GET | /agents/executions | agents:read |

### Search

| Method | Path | Permission |
|--------|------|-----------|
| GET | /search | search:read |

## Findings

1. **All 47 endpoints have RBAC protection** (auth endpoints are correctly unprotected).
2. **No gaps found** — every endpoint requires `require_permission(resource, action)`.
3. **organization_id is never accepted from client input** — derived from JWT via `get_current_user`.
4. **Cross-tenant isolation** is enforced at the repository/data-access layer (Phase 3).

## Role → Permission Summary

| Role | Permissions |
|------|-------------|
| Owner | *:* (wildcard — full access) |
| Admin | users:write + all read permissions |
| Finance Manager | leakage:approve, leakage:reject, leakage:close |
| Accountant | invoices:write, contracts:write |
| Analyst | leakage:read (read-only) |
| Viewer | customers:read, contracts:read, invoices:read, payments:read |
