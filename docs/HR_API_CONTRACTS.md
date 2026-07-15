# HR API Contracts

Implemented foundation:

- `GET /api/v1/hr/dashboard` — aggregated ATS-free HR metrics.
- `GET /api/v1/hr/employees` — permitted paginated directory.
- `GET /api/v1/hr/employees/:id` — ABAC-filtered profile.
- Existing leave endpoints — request and review flow.

Planned contracts follow the paths in `HR_FULLSTACK_IMPLEMENTATION_PLAN.md` for messages, sick leave, business trips, calendars and lifecycle cases. Errors use stable codes with appropriate 400/403/404/409 responses. List endpoints support pagination and deterministic sorting. Sensitive fields are separate projections.

Forbidden in this scope: `/api/v1/hr/hiring`, `/api/v1/hr/add-employee`, `/api/v1/hr/hiring-requests`, server drafts, Hiring attachments and server DOCX generation.
