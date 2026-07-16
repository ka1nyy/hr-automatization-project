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
from app.modules.documents.infrastructure import models as document_models
from app.modules.employees.infrastructure.models import (
    DelegationModel,
    EmployeeAssignmentModel,
    EmployeeModel,
    PersonModel,
)
from app.modules.hiring_requests.infrastructure import models as hiring_request_models
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
from app.modules.recruitment.infrastructure import models as recruitment_models
from app.modules.termination.infrastructure import models as termination_models
from app.modules.workflow.infrastructure import models as workflow_models

__all__ = [
    "AccessScopeModel",
    "AccessScopeUnitModel",
    "AuditEventModel",
    "DelegationModel",
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

# Keep module namespaces referenced: importing them registers every owned table in Base.metadata.
_MODULE2_MODELS = (
    document_models,
    hiring_request_models,
    recruitment_models,
    termination_models,
    workflow_models,
)
