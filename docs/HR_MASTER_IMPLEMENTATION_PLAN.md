# HR Master Implementation Plan

## Reusable foundation

The monorepo has a React/Vite frontend and a NestJS/Prisma backend. The shared application shell provides sidebar, contextual header, theme, permission-aware personas, queries, common panels/forms/dialogs, tasks, processes and organization pages. Backend foundation provides request context, RBAC guard, correlation IDs, audit/outbox records and Document/Workflow ports.

Existing HR implementation covers authenticated-persona department context, a role-aware main dashboard, employee directory/profile, leave foundation and frontend-only Add Employee. For an HR user, `/` is the HR Home and the shared sidebar exposes Incoming Messages, Employees, Add Employee, Leave, Tasks, Processes and Organization. Feature routes remain `/hr/employees`, `/hr/employees/:employeeId`, `/hr/leave` and `/hr/hiring/add-employee`; legacy `/departments/hr/*` paths remain compatible.

## Ownership and boundaries

- HR Core: employee employment records, protected personal profile metadata and history.
- HR Absence: leave, sick leave, trips and absence calendar projections.
- HR Lifecycle: onboarding, probation, employee changes, termination and offboarding for existing employees.
- Shared services retain ownership of identity, organization, documents, files, tasks, workflow/Camunda, notifications, audit and signatures.
- HR dashboard is a read model/aggregation endpoint, not an empty microservice.

## Hiring exclusion

Add Employee remains browser-only. It saves JSON draft metadata locally, retains files in memory, previews and creates DOCX in the browser. No Hiring endpoint/table/module/event/worker/process/upload/server DOCX or employee creation may be introduced. `AddEmployeeSubmissionRepository` remains a future boundary only.

## API, data and events

Supported backend endpoints are permission-aware and use DTO mapping, correlation IDs, validation and optimistic locking. Domain changes persist audit and outbox records in the same transaction. Future absence/lifecycle/messages modules add only additive migrations and service-owned tables; consumers are idempotent. Sensitive personal, compensation and medical values are projected by permission and excluded from logs.

## Delivery order

1. Preserve shell/design and resolve HR context from authenticated/development persona on every shared route, including `/`, `/tasks`, `/processes`, `/organization` and Incoming Messages.
2. Complete frontend-only Add Employee and ATS removal.
3. Complete dashboard/employee directory and protected profile projections.
4. Implement incoming messages and user-specific receipts.
5. Implement absence modules and calendar.
6. Implement lifecycle modules for existing employees.
7. Connect shared documents/tasks/processes/notifications and configurable Camunda adapters.
8. Add migrations/seeds, tests and browser verification for each increment.

## Risks and assumptions

External shared-service production contracts require coordination. Current mock adapters intentionally model only frontend behavior. Other department workspaces are out of scope, but department context exposes the data needed to add them without a new shell.
