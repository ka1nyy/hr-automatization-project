# Domain model

## Organization and structure versions

`Organization` is a legal/employing entity identified by UUID and stable code. The MVP seed has
one organization but all structural, access, audit, and policy records carry organization scope.

`OrganizationStructureVersion` is a complete, temporal snapshot. Its lifecycle is `draft ->
in_review -> published -> archived`. A new draft clones stable business keys from the active
published version while allocating new record UUIDs. `basedOnVersionId` records lineage;
`revision` provides optimistic concurrency.

Published versions overlap neither each other nor their effective intervals. Historical employee
assignments continue to reference the staffing slot and structure version that existed when the
assignment began.

## Primary tree and graph arrows

`OrganizationUnit` forms the primary tree within one structure version:

- one root;
- every non-root unit has a parent in the same version;
- no cycle or orphan;
- code is unique per version;
- `stableKey` connects the conceptual unit across versions;
- unit type is configurable reference data, not a name-based rule.

`OrganizationRelationship` contains additional graph arrows such as functional supervision,
curation, shared service, coordination, and temporary supervision. Its configurable relationship
type determines whether cycles or cross-unit links are allowed. Self-links and duplicates are
always rejected. These arrows never replace the primary tree.

## Positions and staffing

`PositionDefinition` is a reusable catalog entry. A title or grade grants no permission.

`StaffingSlot` places one approved position in a versioned unit. `stableKey` links it between
structure versions. Slots can report to another slot in the same version, with cycle validation.
FTE must be positive and within configured limits. Closing ends availability but preserves the
slot and its assignments. A unit normally has one active head unless versioned policy explicitly
allows more; acting heads are represented by acting employee assignments.

## Human identity and employment

`Person` holds human identity separately from employment. IIN is encrypted at rest; birth date,
personal email, phone, and IIN are sensitive DTO fields.

`Employee` represents organization-owned employment. Employee number and Person linkage are unique
inside that organization. `createdBy` lets a scoped manager revisit only their own unassigned draft;
hire/termination dates, status, and corporate email remain separate from human identity.

`EmployeeAssignment` is a temporal link to a staffing slot. Permanent, temporary, acting,
part-time, and concurrent types are supported. Invariants include:

- at most one overlapping primary assignment per employee;
- assignment interval inside the slot interval;
- no employee or slot FTE overflow;
- secondary and acting assignments may overlap when capacity remains;
- ending an assignment preserves it as history and emits an event.

Manager-created assignments enter `pending_review` when policy requires HR approval. A dedicated
`AssignmentReviewRequest` records submission and decision, and the assignment-started event is
emitted only after approval. Effective dates remain authoritative for overlap and authorization,
including an assignment whose future end has already been scheduled.

`reportsToSlotId` supplies the primary reporting relationship. Configurable organization arrows
supply functional relationships. Temporary acting assignments and `Delegation` supply temporary
operational authority without rewriting the tree.

## Delegation

`Delegation` transfers an explicit permission set for a bounded UTC interval and a scope reference.
Delegator and delegate differ, intervals are valid, overlapping duplicate grants are rejected,
and revocation is audited. Effective status is calculated at read/authorization time, so an expired
delegation stops applying without a scheduled database update.

## Access control

`UserAccount` maps an OIDC subject to an internal stable identity. `Role` groups `Permission`
records through `RolePermission`. `UserRoleAssignment` applies a role for an effective interval
and an `AccessScope`:

- `self`;
- `own_unit`;
- `own_unit_and_descendants`;
- `selected_units`;
- `organization`.

Roles, assignments, scopes, employee assignments, and organization hierarchy—not display names—
determine authority.

## Policies and review

`OrganizationPolicy` versions configurable booleans for manager and publication behavior.
`ReviewRequest` is a deliberately small internal state machine for direct-apply versus
submit-for-review behavior. It is not a workflow engine; its ID and state form the integration
point for Module 2/Camunda.

## Audit and outbox

`AuditEvent` is append-only and records actor, action, entity, safe before/after state, reason,
request ID, organization, and UTC occurrence. ORM listeners reject update and delete operations.

`OutboxEvent` stores an application event in the business transaction. Processing metadata is
mutable, but the event identity, name, aggregate, safe payload, occurrence, and schema version are
not rewritten.
