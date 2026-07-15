# API contracts

The production API base is `/api/v1`. DTO field names are camelCase. UUIDs and ISO-8601 dates or
UTC timestamps are strings; FTE values are JSON decimals. SQLAlchemy models are never serialized.

Swagger UI is served at `/docs`, ReDoc at `/redoc`, and the machine contract at `/openapi.json`.

## Envelopes

Single-resource success:

```json
{"data":{"id":"uuid"},"meta":{"requestId":"uuid"}}
```

List success:

```json
{
  "data": [],
  "meta": {"requestId":"uuid","page":1,"pageSize":20,"total":0}
}
```

Failure:

```json
{
  "error": {
    "code": "ORG_STRUCTURE_CYCLE",
    "message": "The operation would create a cycle.",
    "details": {},
    "requestId": "uuid"
  }
}
```

Unknown exceptions are not converted into false success responses. They produce a server error
and remain visible to logging/observability. Validation errors return every Pydantic field problem;
draft validation returns every structural problem in one result.

## Pagination, filtering, and concurrency

List endpoints accept `page` (default 1) and `pageSize` (default 20, maximum documented per
endpoint). Supported filters are named in OpenAPI. Sorting uses `sort` with an allow-listed field;
a leading `-` means descending. Unsupported sort values return HTTP 422.

| Collection | Allowed `sort` fields (prefix with `-` for descending) | Default |
| --- | --- | --- |
| Employees | `employeeNumber`, `hireDate`, `createdAt` | `employeeNumber` |
| Delegations | `effectiveFrom`, `createdAt`, `status` | `-effectiveFrom` |
| Structure versions | `versionNumber`, `createdAt` | `-versionNumber` |
| Positions | `code`, `name`, `createdAt` | `name` |
| Staffing slots | `organizationUnitId`, `status`, `fullTimeEquivalent` | `organizationUnitId` |
| Roles | `code`, `name`, `createdAt` | `code` |
| Permissions | `code`, `name`, `createdAt` | `code` |
| Audit events | `occurredAt`, `action`, `entityType` | `-occurredAt` |

Sorting is applied before pagination. Every database-backed ordering includes the immutable ID as
a deterministic tie-breaker.

Every editable DTO returns `revision`. Mutations send the revision in the JSON body. A stale value
returns HTTP 409 with `CONCURRENCY_CONFLICT`; the server never performs last-write-wins.

## Health

| Method and path | Authentication | Result |
| --- | --- | --- |
| `GET /health/live` | none | Process liveness; no external dependency |
| `GET /health/ready` | none | PostgreSQL readiness; 503 when unavailable |

## Organization structures

| Method and path | Permission | Important input/result |
| --- | --- | --- |
| `GET /organization` | `organization.read` | Legal/display identity and status |
| `GET /organization/structure/active` | `organization.structure.read` | Tree-friendly active version; graph arrows separate |
| `GET /organization/structure/versions` | `organization.structure.read` | Paginated history/drafts visible to actor |
| `GET /organization/structure/versions/{id}` | `organization.structure.read` | Historical version without remapping |
| `GET /organization/structure/versions/{fromVersionId}/compare/{toVersionId}` | `organization.structure.read` | Added/removed/changed stable keys |
| `POST /organization/structure/drafts` | `organization.structure.draft.create` | `basedOnVersionId`, `name`, optional effective date |
| `POST /organization/structure/drafts/{id}/validate` | `organization.structure.edit` | `{valid, problems[]}`; audit recorded |
| `POST /organization/structure/drafts/{id}/submit-review` | `organization.structure.edit` | `revision`, `reason`; freezes a valid draft |
| `POST /organization/structure/drafts/{id}/return` | `organization.structure.review` | Structure revision, review revision, required reason |
| `POST /organization/structure/drafts/{id}/publish` | `organization.structure.publish` | `revision`, `effectiveFrom`, required reason |

Draft creation clones the full active snapshot. Publish revalidates and may return validation
problems without changing either version.

## Units

| Method and path | Permission | Notes |
| --- | --- | --- |
| `POST /organization/structure/{versionId}/units` | `organization.unit.manage` | Add unit to an editable draft |
| `PATCH /organization/structure/{versionId}/units/{unitId}` | `organization.unit.manage` | Rename, type, order, active/custom fields; revision required |
| `POST /organization/structure/{versionId}/units/{unitId}/move` | `organization.unit.manage` | New stored parent ID and revision; cycle checked |
| `POST /organization/structure/{versionId}/units/reorder` | `organization.unit.manage` | Parent plus ordered unit IDs, revisions, and sort orders |
| `DELETE /organization/structure/{versionId}/units/{unitId}` | `organization.unit.manage` | Deactivate/archive; no historical physical delete |

Create fields include `code`, `name`, `shortName`, `unitTypeId`, `parentUnitId`, `sortOrder`,
`description`, `active`, and validated `customFields`. The backend generates the immutable
`stableKey`.

## Additional relationships

| Method and path | Permission | Notes |
| --- | --- | --- |
| `GET /organization/structure/{versionId}/relationships` | `organization.structure.read` | List graph arrows; optionally include inactive rows |
| `POST /organization/structure/{versionId}/relationships` | `organization.relationship.manage` | Type, stored source/target, effective interval, metadata |
| `PATCH /organization/structure/{versionId}/relationships/{relationshipId}` | `organization.relationship.manage` | Revision/effective/state changes |
| `DELETE /organization/structure/{versionId}/relationships/{relationshipId}` | `organization.relationship.manage` | Deactivate while preserving history |

Self-links, duplicates, prohibited cycles, wrong-version IDs, invalid dates, and policy-prohibited
cross-unit arrows are rejected.

## Reference types, policy, and reviews

| Method and path | Permission | Notes |
| --- | --- | --- |
| `GET /organization/reference/unit-types` | `organization.structure.read` | Configurable unit types and parent rules |
| `POST /organization/reference/unit-types` | `organization.structure.edit` | Create type with parent IDs and custom-field schema |
| `PATCH /organization/reference/unit-types/{id}` | `organization.structure.edit` | Revision required |
| `GET /organization/reference/relationship-types` | `organization.structure.read` | Configurable arrow semantics |
| `POST /organization/reference/relationship-types` | `organization.structure.edit` | Create type and validation metadata |
| `PATCH /organization/reference/relationship-types/{id}` | `organization.structure.edit` | Revision required |
| `GET /organization/structure/{versionId}/policy` | `organization.structure.read` | Effective version policy or inherited default |
| `PUT /organization/structure/{versionId}/policy` | `organization.structure.edit` | Draft/version and policy revisions required |
| `GET /organization/structure/{versionId}/reviews` | `organization.structure.review` | Review history for the version |

## Position definitions and staffing slots

| Method and path | Permission | Notes |
| --- | --- | --- |
| `GET /positions` | `organization.structure.read` | `includeInactive` filter; paginated and sorted |
| `POST /positions` | `organization.staffing.manage` | Catalog item; title grants no authority |
| `PATCH /positions/{id}` | `organization.staffing.manage` | Revision required; deactivate instead of delete |
| `GET /staffing-slots` | `organization.structure.read` | Filter by version, unit, and status; paginated and sorted |
| `POST /staffing-slots` | `organization.staffing.manage` | Draft slot and reporting reference |
| `PATCH /staffing-slots/{id}` | `organization.staffing.manage` | Revision, FTE/status/reporting changes |
| `POST /staffing-slots/{id}/close` | `organization.staffing.manage` | Revision, effective date, reason; future closure returns `closing` and requires direct reports to be reassigned first |

The service resolves unit/version and reporting-slot references from storage before checking actor
scope. Reporting cycles and FTE constraints return stable conflict errors.

## Employees and assignments

| Method and path | Permission | Notes |
| --- | --- | --- |
| `GET /employees` | `employees.read` | Unit-scoped, paginated; never includes sensitive fields |
| `POST /employees` | `employees.create` | Person plus employee draft; IIN encrypted before persistence |
| `GET /employees/{id}` | `employees.read` | `includeSensitive=true` additionally needs `employees.read_sensitive` |
| `PATCH /employees/{id}` | `employees.edit` | Stored assignment determines scope; revision required |
| `POST /employee-assignments` | `employees.assign` | Permanent/temporary/acting/part-time/concurrent |
| `POST /employee-assignments/{id}/review` | organization-scoped `employees.assign` | Approve/reject a pending assignment; revision and reason required |
| `POST /employee-assignments/{id}/end` | `employees.assign` | End date, revision, reason; retains history |

Employee responses include authoritative `organizationId` and `createdBy` ownership fields.
Assignment creation checks the persisted staffing slot's organization/unit/published version,
availability, date interval, primary conflict, employee FTE, and slot FTE in one transaction.
When a scoped manager is allowed to assign but policy requires HR approval, creation returns
`status: "pending_review"` and creates an internal review request. Only an organization-scoped HR
actor may approve or reject it; `employeeAssignmentStarted` is emitted only after approval. A
future end returns effective status `active` until `effectiveTo` and emits
`employeeAssignmentEndScheduled` with that date.

## Delegations

| Method and path | Permission | Notes |
| --- | --- | --- |
| `GET /delegations` | `delegations.manage` | Filter by employee and `activeAt` |
| `POST /delegations` | `delegations.manage` | Explicit permission set, scope, UTC interval, reason |
| `POST /delegations/{id}/revoke` | `delegations.manage` | Revision and reason; audit/outbox emitted |

Expired status is evaluated against current time; it does not require a cleanup job to stop
authorization.

## Access control

| Method and path | Permission | Notes |
| --- | --- | --- |
| `GET /access/roles` | `roles.manage` | System and organization roles |
| `POST /access/roles` | `roles.manage` | Permission codes validated against catalog |
| `GET /access/permissions` | `roles.manage` | Stable permission catalog |
| `POST /access/role-assignments` | `roles.manage` | User, role, effective interval, access scope |
| `POST /access/role-assignments/{id}/revoke` | `roles.manage` | Revision and reason |

## Audit

`GET /audit/events` requires `audit.read`. Filters include organization, actor, entity type,
entity ID, and action. Results are reverse chronological. No API allows audit mutation.

## Stable errors

| Code | Typical HTTP | Meaning |
| --- | --- | --- |
| `AUTH_UNAUTHENTICATED` | 401 | Missing/invalid identity |
| `AUTH_FORBIDDEN` | 403 | Permission absent |
| `AUTH_SCOPE_VIOLATION` | 403 | Permission exists but resource is outside scope |
| `RESOURCE_NOT_FOUND` | 404 | Resource is absent or intentionally undisclosed |
| `VALIDATION_FAILED` | 422 | DTO or aggregate validation problems |
| `CONCURRENCY_CONFLICT` | 409 | Revision is stale |
| `ORG_STRUCTURE_NOT_EDITABLE` | 409 | Target version is not an editable draft |
| `ORG_STRUCTURE_CYCLE` | 409 | Primary/reporting/prohibited graph cycle |
| `ORG_STRUCTURE_MULTIPLE_ROOTS` | 409/422 | Candidate does not have exactly one root |
| `ORG_STRUCTURE_INVALID_RELATIONSHIP` | 409/422 | Invalid graph arrow |
| `ORG_STRUCTURE_VERSION_CONFLICT` | 409 | Effective versions overlap or state transition invalid |
| `VERSION_CONFLICT` | 409 | Employee assignment/review is not in the requested state |
| `STAFFING_SLOT_NOT_AVAILABLE` | 409 | Slot cannot receive the requested operation |
| `STAFFING_FTE_EXCEEDED` | 409 | Employee or slot capacity exceeded |
| `EMPLOYEE_ALREADY_ASSIGNED` | 409 | Overlapping primary assignment |
| `ASSIGNMENT_DATE_CONFLICT` | 409 | Assignment/slot dates conflict |
| `DELEGATION_DATE_CONFLICT` | 409 | Invalid or duplicate delegation interval |
| `SENSITIVE_DATA_FORBIDDEN` | 403 | Explicit sensitive-read permission absent |
