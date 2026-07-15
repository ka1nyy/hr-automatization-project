# HR Full-stack Implementation Plan

## Existing foundation

The repository is a two-workspace monorepo. `frontend` is React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form and Zod. It already provides the approved shell, themes, shared panels, tables, dialogs, repository mocks, permissions and HR employee/leave screens. `backend` is NestJS, Prisma and PostgreSQL with request context, permission guard, audit/outbox records, employee and leave modules, and mock/HTTP ports for shared Document and Workflow services.

The implementation must extend these foundations. It must not introduce a second application shell, UI framework, authentication model, task system, document store or workflow engine.

## Target increments

1. Establish `departmentCode = HR`, canonical `/hr/*` routes and `HR / current page` header context.
2. Remove ATS language and surfaces. Keep staffing positions only as organization data.
3. Deliver Add Employee as a browser-only form: Zod validation, local draft, preview and DOCX generation.
4. Connect dashboard and employee directory through typed DTO/domain/mapping repositories.
5. Add Incoming Messages with per-user receipts and optimistic read state.
6. Add absence capabilities: leave, sick leave privacy mapping, business trips and the combined calendar.
7. Add lifecycle capabilities for existing employees: onboarding, probation, changes, termination and offboarding.
8. Reuse shared Tasks, Processes, Documents, Notifications, Audit and Camunda adapters.
9. Add migrations, deterministic seed data, unit/integration/e2e coverage and browser-visible verification.

## Service and data ownership

- HR Core owns employee employment records, HR profile metadata, assignments and employment history.
- HR Absence owns leave, balances, sick leave, business trips and absence projections.
- HR Lifecycle owns onboarding and changes after an employee already exists.
- Dashboard is an aggregated read contract, not an empty microservice.
- Organization, Documents, Files, Tasks, Workflow, Notifications, Audit, Identity and Signature remain shared service boundaries.
- Binary documents are never stored in HR tables.

## API and events

REST contracts live under `/api/v1/hr`. Mutations require authenticated request context, permission checks, correlation IDs and optimistic locking/idempotency where applicable. Durable changes write audit and outbox records transactionally. Consumers must be idempotent. No Hiring/Add Employee endpoint, table, process, worker, upload, draft or event is permitted in this scope.

## Security

RBAC selects capabilities; ABAC narrows records by self, reporting line, department, ownership and process participation. Compensation, personal and medical projections are explicit and audited. Medical values are excluded from manager DTOs and logs. Development identity headers are never a production authentication mechanism.

## Development behavior

Frontend pages consume repositories rather than fixture imports. Mock adapters are deterministic and may be selected for local work. Backend-supported functionality must fail honestly when unavailable. Add Employee is the sole intentional browser-local workflow; its files are held only in memory.

## Risks and assumptions

- Shared external services are represented by ports; their production contracts require coordination.
- Current seed/migrations cover employee and leave only; later increments require additive migrations.
- Legacy `/departments/hr/*` links remain compatible while `/hr/*` becomes canonical.
- Existing visual primitives constrain page composition and must be reused.

## Current implementation status

Completed in the first increment: branch isolation, repository inspection, canonical HR context/routes, Add Employee local form/validation/draft/preview/DOCX, Hiring integration boundary, dashboard API alias, ATS-free dashboard metrics and baseline verification. Remaining capabilities are implemented incrementally in the order above; this document does not claim unfinished modules are complete.
