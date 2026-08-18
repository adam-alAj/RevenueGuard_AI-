# RevenueGuard AI — Domain Glossary

This glossary defines the 11 core domain entities that appear throughout the platform. Every entity carries an `organization_id` for multi-tenant isolation (ADR-003). Deterministic code (never an LLM) handles all monetary calculations and queries involving these entities (ADR-001).

---

**Customer** — A B2B client organization whose revenue data is ingested, monitored, and analyzed for leakage by RevenueGuard AI.

**Contract** — A commercial agreement between the customer and the services company that defines pricing, billing terms, renewal conditions, minimum commitments, and expiration dates, serving as the ground truth for what should have been billed.

**Invoice** — A billing document issued to a customer for specific services or deliverables, representing the actual amount billed, and compared against contract terms to detect underbilling, pricing mismatches, or missing invoices.

**RevenueLeakageCase** — A detected instance of revenue that should have been billed or collected but was missed, carrying a severity, confidence score, financial impact estimate, and a lifecycle status from detection through recovery.

**Evidence** — An immutable, point-in-time snapshot of a referenced record (contract, invoice, payment, or operational data) that supports or refutes a leakage case, ensuring the investigation trail survives later edits to the source data.

**Investigation** — A structured inquiry into a detected leakage case, performed by an AI agent that gathers evidence, checks for legitimate exceptions (amendments, credit notes, cancellations), and produces a classification (confirmed, likely, uncertain, false positive, or legitimate exception).

**RecoveryAction** — A draft-only remediation step (such as a corrective invoice draft, payment reminder, or internal task) generated after a case is approved, requiring a second human approval before any external action is taken.

**RecoveryResult** — The outcome of an executed recovery action, recording whether the potential leakage was actually recovered, partially recovered, or not recovered, along with the verified recovered amount.

**Approval** — A recorded human decision (approve, reject, or request more information) on a leakage case or recovery draft, capturing who decided, when, and why, forming the audit trail that makes every financial action traceable.

**AuditLog** — A chronological, append-only record of every significant system event (data ingestion, rule execution, agent invocation, approval decision, status change) that provides full traceability for compliance and debugging.

**AgentExecution** — A record of a single AI agent invocation, capturing which agent ran, which tools it called, what structured output it produced, the tenant context it operated under, and the full execution trace for audit and debugging purposes.
