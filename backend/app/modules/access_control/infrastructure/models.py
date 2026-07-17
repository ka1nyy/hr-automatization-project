"""SQLAlchemy mappings for RBAC and organization-scoped grants."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base


class RoleModel(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_roles_revision_positive"),
        Index(
            "uq_roles_global_code",
            "code",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        Index(
            "uq_roles_organization_code",
            "organization_id",
            "code",
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
        Index("ix_roles_active", "active"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class PermissionModel(Base):
    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_permissions_code"),
        Index("ix_permissions_active", "active"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # A system permission is one the source tree checks by code. Its wording is editable,
    # but it cannot be deleted or deactivated: doing so would silently disable the
    # authorization check that depends on it. Administrator-defined permissions are false.
    system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class RolePermissionModel(Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        PrimaryKeyConstraint("role_id", "permission_id", name="pk_role_permissions"),
        Index("ix_role_permissions_permission_id", "permission_id"),
    )

    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    granted_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL")
    )


class AccessScopeModel(Base):
    __tablename__ = "access_scopes"
    __table_args__ = (
        CheckConstraint(
            "organization_id IS NOT NULL",
            name="ck_access_scopes_organization_required",
        ),
        Index("ix_access_scopes_organization", "organization_id", "scope_type"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    organization_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    units: Mapped[list[AccessScopeUnitModel]] = relationship(
        back_populates="scope",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AccessScopeUnitModel(Base):
    __tablename__ = "access_scope_units"
    __table_args__ = (
        PrimaryKeyConstraint("scope_id", "unit_id", name="pk_access_scope_units"),
        Index("ix_access_scope_units_unit_id", "unit_id"),
    )

    scope_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("access_scopes.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope: Mapped[AccessScopeModel] = relationship(back_populates="units")


class UserRoleAssignmentModel(Base):
    __tablename__ = "user_role_assignments"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_user_role_assignments_effective_range",
        ),
        CheckConstraint("revision > 0", name="ck_user_role_assignments_revision_positive"),
        Index(
            "ix_user_role_assignments_user_effective",
            "user_id",
            "effective_from",
            "effective_to",
        ),
        Index(
            "ix_user_role_assignments_active",
            "user_id",
            "role_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("access_scopes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL")
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    scope: Mapped[AccessScopeModel] = relationship(lazy="selectin")
