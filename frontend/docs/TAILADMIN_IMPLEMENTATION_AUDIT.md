# TailAdmin frontend implementation audit

## Backend-to-frontend mapping

| Backend module | Endpoint group | DTO source | Frontend route/page | Frontend service | Status |
| --- | --- | --- | --- | --- | --- |
| Business processes | `/operations/dashboard` | `DashboardDto` | `/` / `DashboardPage` | `ApiOperationsRepository` | Real API |
| Business processes | `/operations/correspondence/incoming*` | `CorrespondenceDto`, `IncomingLetterRequest` | `/correspondence/incoming*` | `ApiCorrespondenceRepository` | Real API |
| Business processes | `/operations/tasks*` | `WorkTaskDto` | `/tasks` | `ApiTaskRepository` | Real API |
| Business processes | `/operations/processes*` | `ProcessDefinitionDto` | `/processes` | `ApiWorkflowRepository` | Real API |
| Business processes | `/hr/overview` | `HrOverviewDto` | `/hr` | `ApiHrRepository` | Real API |
| Business processes | `/hr/employees*` | `HrEmployeeDto` | `/hr/employees*` | `ApiHrRepository` | Real API |
| Business processes | `/hr/leave-requests*` | `LeaveRequestDto` | `/hr/leave` | `ApiHrRepository` | Real API |
| Business processes | `/operations/directory/employees` | `DirectoryEmployeeDto` | `/organization` | `ApiOrganizationRepository` | Real API, directory view |
| Business processes | `/hr/hiring/requests` | `HiringSubmission`, `HiringRequestDto` | employee add form | `ApiHrRepository` | Existing integration preserved; no new backend |
| Employees | `/employees*`, `/employee-assignments*`, `/delegations*` | employee API schemas | employee directory/profile only | no complete module client | Partial UI gap |
| Organization | `/organization/structure*`, `/positions`, `/staffing-slots` | organization API schemas | `/organization` directory only | no structure-editor client | UI gap |
| Access control | `/access/roles*`, `/access/permissions*`, `/access/role-assignments*` | access API schemas | none | none | UI gap |
| Audit | `/audit/events` | `AuditEventDto` | none | none | UI gap |

## Frontend-only modules

Calendar, sick leaves, dismissals, HR documents, notifications and the consolidated approval view use typed data from `src/features/hr/mocks/plannedHrService.ts`. Components do not contain production endpoint assumptions. Hiring remains an employee hiring request form, not an ATS.

## TailAdmin adaptation

The existing React Router, TanStack Query, React Hook Form, Zod and Lucide stack is compatible with the TailAdmin interaction patterns. Tailwind, ApexCharts, FullCalendar, map and e-commerce dependencies were intentionally not copied. Reused patterns are: responsive collapsible sidebar, sticky header, command search, notification dropdown, cards, tables, form controls, badges, modal surfaces, light/dark tokens and mobile navigation.

## Staged plan

1. Adapt design tokens and global surfaces.
2. Rebuild shell, sidebar, header and navigation groups.
3. Normalize shared cards, buttons, tables, forms and state components.
4. Preserve all real API-backed operational and HR modules.
5. Add typed frontend-only routes for planned HR modules.
6. Verify permissions, responsive behavior, tests, lint, typecheck and production build.

## Unresolved backend gaps

No production endpoints currently support the planned calendar, sick leave register, dismissal workflow, HR document archive or consolidated notification feed. The existing low-level employees, organization, access-control and audit APIs need dedicated typed clients and full workflow pages in a later delivery.
