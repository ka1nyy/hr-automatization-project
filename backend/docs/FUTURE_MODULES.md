# Future modules and extension points

Module 1 establishes stable identity, authorization, organization, employment, audit, and event
foundations. It deliberately does not simulate later capabilities.

## Declared ports

Application-layer protocols exist for:

- `WorkflowOrchestratorPort`;
- `DocumentServicePort`;
- `SignatureServicePort`;
- `NotificationServicePort`;
- `EmploymentRegistryPort`;
- `PayrollIntegrationPort`.

No adapter claims success in Module 1. A use case requiring one of these capabilities must receive
a real later adapter or remain unavailable. Camunda, MinIO, electronic signatures, ESUTD, payroll,
and a broker are not installed.

## Module 2 — workflow and documents

Expected additions include configurable/versioned forms, approval routes, documents, tasks,
Camunda process definitions, notifications, and digital signatures. The current small
`ReviewRequest` can be correlated to a process instance without changing organization aggregates.
Process variables should carry UUIDs and version numbers, not department or position names.

The outbox provides reliable event handoff. A future dispatcher should claim rows with
`FOR UPDATE SKIP LOCKED`, call idempotent adapters, mark processed, and retry with bounded backoff.

## Module 3 — recruitment and hiring

Recruitment requests, vacancies, candidates, interviews, commission decisions, document
collection, contracts/orders, acknowledgements, onboarding, and ESUTD integration will reference:

- a structure version and staffing-slot stable identity;
- requested effective date;
- actor/approver IDs and permission snapshots;
- resulting person, employee, and assignment IDs.

Module 1 does not implement candidate or employment-document states.

## Module 4 — HR administration

Timesheets, working time, leave, sick leave, time off, business trips, transfers, salary changes,
additional agreements, termination, settlement, handover, and exit interview will add their own
temporal aggregates. Transfers should end one assignment and begin another under a workflow; they
must not overwrite Module 1 assignment history.

## Evolution rules

- Keep one deployable modular monolith until scaling/ownership evidence justifies another shape.
- Add module-owned tables and ports; do not create a generic low-code database engine.
- Version forms, processes, documents, and external payload schemas.
- Use the transactional outbox for side effects; never call an external system inside a database
  transaction and assume it is atomic.
- Retain UUID, UTC, effective-date, audit-redaction, optimistic-concurrency, and stable-error
  conventions.
- Continue resolving routes/authority from IDs, roles, scopes, assignments, and relationships;
  never introduce name-based routing.
