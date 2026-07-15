"""SQLAlchemy 2 mappings for organization structures and staffing."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("code", name="uq_organizations_code"),
        Index("ix_organizations_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class OrganizationStructureVersionModel(Base):
    __tablename__ = "organization_structure_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "version_number",
            name="uq_organization_structure_versions_number",
        ),
        CheckConstraint(
            "version_number > 0", name="ck_organization_structure_versions_number_positive"
        ),
        CheckConstraint(
            "revision > 0", name="ck_organization_structure_versions_revision_positive"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_organization_structure_versions_effective_range",
        ),
        CheckConstraint(
            "status <> 'published' OR effective_from IS NOT NULL",
            name="ck_organization_structure_versions_published_effective_from",
        ),
        ExcludeConstraint(
            ("organization_id", "="),
            (text("daterange(effective_from, effective_to, '[]')"), "&&"),
            where=text("status = 'published'"),
            using="gist",
            name="excl_organization_structure_versions_published_overlap",
        ),
        Index(
            "ix_organization_structure_versions_active",
            "organization_id",
            "status",
            "effective_from",
            "effective_to",
        ),
        Index("ix_organization_structure_versions_based_on", "based_on_version_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    based_on_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_structure_versions.id", ondelete="RESTRICT"),
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    published_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationUnitTypeModel(Base):
    __tablename__ = "organization_unit_types"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_organization_unit_types_code"),
        CheckConstraint("revision > 0", name="ck_organization_unit_types_revision_positive"),
        Index("ix_organization_unit_types_active", "organization_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    custom_fields_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class OrganizationUnitTypeAllowedParentModel(Base):
    __tablename__ = "organization_unit_type_allowed_parents"
    __table_args__ = (
        PrimaryKeyConstraint(
            "unit_type_id", "parent_type_id", name="pk_organization_unit_type_allowed_parents"
        ),
    )

    unit_type_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_unit_types.id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_type_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_unit_types.id", ondelete="RESTRICT"),
        nullable=False,
    )


class OrganizationRelationshipTypeModel(Base):
    __tablename__ = "organization_relationship_types"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_organization_relationship_types_code"),
        CheckConstraint(
            "revision > 0", name="ck_organization_relationship_types_revision_positive"
        ),
        Index("ix_organization_relationship_types_active", "organization_id", "active"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    directed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    prevents_cycles: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    allow_self_link: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    metadata_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class OrganizationPolicyModel(Base):
    __tablename__ = "organization_policies"
    __table_args__ = (
        UniqueConstraint("structure_version_id", name="uq_organization_policies_structure_version"),
        CheckConstraint("revision > 0", name="ck_organization_policies_revision_positive"),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_organization_policies_effective_range",
        ),
        Index(
            "uq_organization_policies_default",
            "organization_id",
            unique=True,
            postgresql_where=text("structure_version_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    structure_version_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_structure_versions.id", ondelete="RESTRICT"),
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    managers_can_create_employee_drafts: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    managers_can_assign_existing_employees: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    manager_changes_require_hr_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    managers_can_create_staffing_slots: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    staffing_changes_require_finance_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    structure_publish_requires_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    allow_multiple_unit_heads: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    allow_cross_unit_relationships: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class StructureReviewRequestModel(Base):
    __tablename__ = "organization_structure_review_requests"
    __table_args__ = (
        CheckConstraint(
            "revision > 0", name="ck_organization_structure_review_requests_revision_positive"
        ),
        Index(
            "uq_organization_structure_review_requests_pending",
            "structure_version_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_organization_structure_review_requests_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    structure_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_structure_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    submitted_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_reason: Mapped[str | None] = mapped_column(Text)
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class OrganizationUnitModel(Base):
    __tablename__ = "organization_units"
    __table_args__ = (
        UniqueConstraint("id", "structure_version_id", name="uq_organization_units_id_version"),
        UniqueConstraint("structure_version_id", "code", name="uq_organization_units_version_code"),
        UniqueConstraint(
            "structure_version_id",
            "stable_key",
            name="uq_organization_units_version_stable_key",
        ),
        ForeignKeyConstraint(
            ["parent_unit_id", "structure_version_id"],
            ["organization_units.id", "organization_units.structure_version_id"],
            name="fk_organization_units_parent_same_version",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("revision > 0", name="ck_organization_units_revision_positive"),
        CheckConstraint("sort_order >= 0", name="ck_organization_units_sort_order_nonnegative"),
        Index(
            "uq_organization_units_single_active_root",
            "structure_version_id",
            unique=True,
            postgresql_where=text("parent_unit_id IS NULL AND active"),
        ),
        Index(
            "ix_organization_units_tree",
            "structure_version_id",
            "parent_unit_id",
            "active",
            "sort_order",
        ),
        Index("ix_organization_units_stable_key", "stable_key"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    structure_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_structure_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stable_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(255))
    unit_type_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_unit_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    parent_unit_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class OrganizationRelationshipModel(Base):
    __tablename__ = "organization_relationships"
    __table_args__ = (
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_organization_relationships_effective_range",
        ),
        CheckConstraint("revision > 0", name="ck_organization_relationships_revision_positive"),
        Index(
            "ix_organization_relationships_version_active",
            "structure_version_id",
            "active",
        ),
        Index(
            "ix_organization_relationships_source_target",
            "source_unit_id",
            "target_unit_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    structure_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_structure_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship_type_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_relationship_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    target_unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))


class PositionDefinitionModel(Base):
    __tablename__ = "position_definitions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "code", name="uq_position_definitions_organization_code"
        ),
        CheckConstraint("revision > 0", name="ck_position_definitions_revision_positive"),
        Index("ix_position_definitions_active", "organization_id", "active"),
        Index("ix_position_definitions_job_family", "organization_id", "job_family"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    job_family: Mapped[str | None] = mapped_column(String(128))
    grade: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class StaffingSlotModel(Base):
    __tablename__ = "staffing_slots"
    __table_args__ = (
        UniqueConstraint(
            "structure_version_id", "stable_key", name="uq_staffing_slots_version_stable_key"
        ),
        CheckConstraint("revision > 0", name="ck_staffing_slots_revision_positive"),
        CheckConstraint(
            "full_time_equivalent > 0 AND full_time_equivalent <= 1",
            name="ck_staffing_slots_fte_range",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_staffing_slots_effective_range",
        ),
        Index(
            "ix_staffing_slots_version_unit_status",
            "structure_version_id",
            "organization_unit_id",
            "status",
        ),
        Index("ix_staffing_slots_reports_to", "reports_to_slot_id"),
        Index(
            "ix_staffing_slots_active_head",
            "organization_unit_id",
            "head_of_unit",
            postgresql_where=text("status NOT IN ('closing', 'closed')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    structure_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_structure_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stable_key: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    organization_unit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organization_units.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position_definition_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("position_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reports_to_slot_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "staffing_slots.id",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    head_of_unit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    full_time_equivalent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("1.00")
    )
    employment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    custom_fields: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
