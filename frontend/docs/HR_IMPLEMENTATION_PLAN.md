# HR department frontend plan

## Existing architecture reused

- `AppShell`, lazy React Router routes and the existing navigation.
- CSS tokens and shared `PageHeader`, `Section`, loading, empty and error states.
- TanStack Query for repository data and Zustand only for the persisted developer persona.
- Existing permission gates, task/process concepts and deterministic local mock storage.

## Scope of this branch

This first HR slice deliberately supports two sides of one workflow instead of creating many empty modules:

1. `HR Specialist`: role-aware overview, employee directory, employee profile, restricted compensation fields and leave-review queue.
2. `Employee`: personal overview, leave balance, own requests and leave submission.

## Routes

- `/departments/hr`
- `/departments/hr/employees`
- `/departments/hr/employees/:employeeId`
- `/departments/hr/leave`

## Entities and repositories

`HrEmployee`, `LeaveRequest`, `HrOverview` and `HrAuditEvent` are accessed through `HrRepository`. The mock adapter persists HR mutations separately from page components. The API adapter boundary is documented for future BFF integration.

## Workflow and document integration

A leave submission creates a `LeaveRequest`, a mock leave-application document number and a workflow state. HR review updates the same entity and appends audit events. Production authorization and business routing remain backend responsibilities.

## Risks and assumptions

- Employee identity is mapped from the selected developer persona in mock mode.
- This branch does not implement production authentication, payroll or medical records.
- Recruitment, onboarding and lifecycle flows remain later vertical slices; no placeholder routes are exposed.
