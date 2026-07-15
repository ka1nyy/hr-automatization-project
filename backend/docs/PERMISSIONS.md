# Permissions and organization scope

Permissions are stable machine codes stored as reference data. Displayed role, unit, and position
names can be changed without changing any authorization decision.

## Catalog

| Permission | Capability |
| --- | --- |
| `organization.read` | Read organization legal/display data |
| `organization.structure.read` | Read active and historical structures |
| `organization.structure.draft.create` | Clone a published version into a draft |
| `organization.structure.edit` | Edit/validate owned drafts |
| `organization.structure.review` | Submit/return review decisions |
| `organization.structure.publish` | Publish a valid reviewed structure |
| `organization.unit.manage` | Add, edit, move, reorder, deactivate units |
| `organization.relationship.manage` | Manage additional graph arrows |
| `organization.staffing.manage` | Manage positions and staffing slots |
| `employees.read` | Read non-sensitive employee data in scope |
| `employees.read_sensitive` | Add sensitive person fields to an authorized employee read |
| `employees.create` | Create employee drafts according to policy/scope |
| `employees.edit` | Edit employee records in scope |
| `employees.assign` | Start/end slot assignments in scope |
| `delegations.manage` | Create/read/revoke bounded delegation grants |
| `roles.manage` | Manage roles and temporal role assignments |
| `audit.read` | Read immutable audit history in scope |

## Seed roles

Seed roles are demonstrations and may be edited or replaced:

| Role | Typical permission intent |
| --- | --- |
| System Administrator | All permissions, organization scope |
| Organization Viewer | Organization identity and structure read only |
| HR Administrator | Employee, assignment, delegation and structure/staffing administration |
| Department Director | Read/manage allowed HR actions in own unit and descendants |
| Employee | Self and organization read needed for the employee portal |
| Organization Reviewer | Read, validate, submit/return review |
| Organization Publisher | Read and publish reviewed structures |
| Auditor | Read structures, employees (non-sensitive unless separately granted), and audit |

The demo director keeps the `Department Director` role at
`own_unit_and_descendants` scope, and the demo employee keeps the `Employee` role at `self`
scope. Each also receives a separate, organization-scoped `Organization Viewer` assignment so
organization and structure navigation works without broadening employee-management authority.

## Scope evaluation

`UserRoleAssignment` is effective-dated and points to one `AccessScope`:

| Scope | Evaluation |
| --- | --- |
| `self` | Target user is the actor and target organization matches the stored scope organization |
| `own_unit` | Target has the same stable unit identity as a current actor assignment unit |
| `own_unit_and_descendants` | Target is actor unit or a descendant in the applicable structure |
| `selected_units` | Target has the same stable unit identity as one selected scope unit |
| `organization` | Stored target organization matches scope organization |

Every scope, including `self`, is bound to an organization. Creating a self assignment verifies
that the target user has a current authoritative assignment in that organization. All conditions
must hold at the requested/effective instant: account active, role active,
permission active, role assignment effective and unrevoked, organization match, and scope match.

The backend first loads the target record and follows its foreign keys to the authoritative
organization/unit. It does not trust `organizationId` or `unitId` supplied in a request as proof
of ownership. A director changing a URL or body unit UUID therefore receives
`AUTH_SCOPE_VIOLATION` (or a deliberately undisclosed not-found response).

## Delegated permission evaluation

A delegation augments, but never permanently changes, the role or organization tree. A grant is
considered only when it is unrevoked, within its UTC interval, includes the requested permission,
and its scope reference covers the stored target. The delegator must possess delegable authority;
a scoped actor may delegate only their own authority, and unit references follow stable identity
across organization versions. A future policy can further restrict which permissions are delegable.

## Frontend behavior

The frontend may hide controls using permission summaries, but this is usability only. It must
handle 401, 403, and 409 from every operation. It must never infer authority from titles such as
“Director” or names such as “HR.”
