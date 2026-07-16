"""Import every persistence model so :class:`Base` metadata is complete.

Alembic and bootstrap utilities import this module before inspecting metadata.  Keeping
the registration in one place prevents a migration or seed run from silently omitting
tables owned by a module.
"""

from app.core.audit.models import AuditEventModel
from app.core.events.models import OutboxEventModel
from app.modules.access_control.infrastructure.models import (
    AccessScopeModel,
    AccessScopeUnitModel,
    PermissionModel,
    RoleModel,
    RolePermissionModel,
    UserRoleAssignmentModel,
)
from app.modules.employees.infrastructure.models import (
    DelegationModel,
    EmployeeAbsenceModel,
    EmployeeAssignmentModel,
    EmployeeModel,
    PersonModel,
)
from app.modules.identity.infrastructure.models import UserAccountModel
from app.modules.organization.infrastructure.models import (
    OrganizationModel,
    OrganizationPolicyModel,
    OrganizationRelationshipModel,
    OrganizationRelationshipTypeModel,
    OrganizationStructureVersionModel,
    OrganizationUnitModel,
    OrganizationUnitTypeAllowedParentModel,
    OrganizationUnitTypeModel,
    PositionDefinitionModel,
    StaffingSlotModel,
    StructureReviewRequestModel,
)

__all__ = [
    "AccessScopeModel",
    "AccessScopeUnitModel",
    "AuditEventModel",
    "DelegationModel",
    "EmployeeAbsenceModel",
    "EmployeeAssignmentModel",
    "EmployeeModel",
    "OrganizationModel",
    "OrganizationPolicyModel",
    "OrganizationRelationshipModel",
    "OrganizationRelationshipTypeModel",
    "OrganizationStructureVersionModel",
    "OrganizationUnitModel",
    "OrganizationUnitTypeAllowedParentModel",
    "OrganizationUnitTypeModel",
    "OutboxEventModel",
    "PermissionModel",
    "PersonModel",
    "PositionDefinitionModel",
    "RoleModel",
    "RolePermissionModel",
    "StaffingSlotModel",
    "StructureReviewRequestModel",
    "UserAccountModel",
    "UserRoleAssignmentModel",
]
