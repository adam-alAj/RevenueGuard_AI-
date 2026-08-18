# ADR-003: Multi-Tenancy via organization_id Column with Repository-Layer Enforcement

## Status

Accepted

## Date

2026-08-19

## Context

RevenueGuard AI is a multi-tenant SaaS: multiple organizations (customers of the platform) share a single database and application instance. Every tenant-owned entity — customers, contracts, invoices, payments, leakage cases, evidence, audit logs, agent executions — must be isolated so that Organization A can never read, write, or infer the existence of Organization B's data. This isolation must be enforced from day one (Phase 2 schema), not bolted on later.

## Decision

- Every tenant-owned table carries a non-nullable, indexed `organization_id` foreign key referencing the `Organization` table.
- Tenant isolation is enforced at the **repository layer**: every data-access class inherits from a `TenantScopedRepository` base class that automatically applies `WHERE organization_id = :current_org_id` to all queries and injects `organization_id` into all inserts.
- `organization_id` is **never accepted from client input** on any endpoint — it is always derived server-side from the authenticated JWT session.
- The JWT token contains the `organization_id` claim, set during authentication. API requests carry only the access token; the organization context is resolved by middleware/deps.

## Alternatives Considered

### 1. Row-Level Security (RLS) at the database level

PostgreSQL RLS policies can enforce tenant isolation at the database layer by filtering rows based on a session variable (e.g., `SET app.current_org_id = '...'`). This is a strong isolation boundary because even a bug in application code cannot leak data if the RLS policy is correct.

**Tradeoff explicitly stated:** RLS was considered but deferred in favor of repository-layer enforcement for the following reasons:

- **Complexity:** RLS policies must be defined for every table, must handle joins correctly (a query joining `invoices` to `customers` must filter both by `organization_id`), and must be maintained as the schema evolves across 17 phases. A mistake in an RLS policy (e.g., forgetting to apply it to a new table or a complex join) silently leaks data with no application-level error.
- **Testing:** RLS behavior is only verifiable against a real PostgreSQL instance — unit tests and mocked database layers cannot validate RLS policies. This makes the test suite dependent on a running database for every tenant-isolation test.
- **Portability:** RLS is PostgreSQL-specific. If the project ever needs to support a different database (e.g., for development tooling or testing), RLS policies do not transfer.
- **Observability:** When RLS silently filters rows, there is no application-level log or metric showing that isolation was enforced. Repository-layer enforcement can emit audit logs on every query, providing traceability.

**Why repository-layer enforcement was chosen instead:** It is testable in unit tests (mock the repository, verify the filter), database-agnostic, observable (can log every tenant-scoped query), and consistent with the Phase 3 RBAC dependency injection pattern (`get_current_user` provides `organization_id`, which flows into every repository call). The repository base class is a single point of enforcement — a new developer (or coding agent) cannot accidentally write an unscoped query without bypassing the base class.

**Future consideration:** RLS may be added as a defense-in-depth layer in a later phase (e.g., Phase 16 security hardening) once the schema is stable and the repository-layer pattern is proven. At that point, RLS would be a safety net, not the primary enforcement mechanism.

### 2. Application-level filtering without a base class

Each repository method manually adds `WHERE organization_id = ?` to its queries. Rejected because this is error-prone — a single missed filter in any of the dozens of repository methods across 17 phases creates a cross-tenant data leak. The base-class pattern makes the default safe: unscoped queries require explicitly opting out (which should never happen for tenant-owned data).

### 3. Separate database per tenant

Each organization gets its own PostgreSQL database. Provides the strongest isolation but is operationally complex (migrations must run across all databases, connection pool management scales poorly, and cost increases linearly with tenants). Rejected for an MVP SaaS product targeting 10–500 employee B2B companies — the tenant volume does not justify the operational overhead.

### 4. Schema-per-tenant

Each organization gets its own schema within a shared database. Better than database-per-tenant but still adds migration complexity and connection management overhead. Rejected for the same reasons as database-per-tenant, with the additional risk that schema names could leak in error messages or logs.

## Implementation Pattern

```
# Repository base class (Phase 3)
class TenantScopedRepository:
    def __init__(self, session: AsyncSession, organization_id: UUID):
        self.session = session
        self.organization_id = organization_id

    async def get_by_id(self, model, entity_id: UUID):
        return await self.session.execute(
            select(model).where(
                model.id == entity_id,
                model.organization_id == self.organization_id  # always filtered
            )
        )
```

Every downstream repository (CustomerRepository, ContractRepository, InvoiceRepository, etc.) inherits from `TenantScopedRepository` and receives `organization_id` from the authenticated user context — never from a request parameter.

## Consequences

- Tenant isolation is enforced by a single base class — a coding agent cannot accidentally write an unscoped query.
- `organization_id` is never present in API request bodies or query parameters — only in the JWT and server-side context.
- Cross-tenant testing is possible in unit tests by instantiating repositories with different `organization_id` values.
- The pattern is database-agnostic and testable without a running PostgreSQL instance.
- If a future phase adds RLS, it will serve as defense-in-depth on top of this application-layer guarantee, not as a replacement.
