"""Access-control domain model."""

from app.modules.access_control.domain.entities import (
    AccessScope,
    Permission,
    Role,
    RolePermission,
    ScopeType,
    UserRoleAssignment,
)
from app.modules.access_control.domain.permissions import REQUIRED_PERMISSION_CODES
from app.modules.access_control.domain.seed_roles import SEED_ROLES

__all__ = [
    "REQUIRED_PERMISSION_CODES",
    "SEED_ROLES",
    "AccessScope",
    "Permission",
    "Role",
    "RolePermission",
    "ScopeType",
    "UserRoleAssignment",
]
