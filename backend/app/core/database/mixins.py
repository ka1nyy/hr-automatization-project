"""Reusable UUID, timestamp, and optimistic-locking columns."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.shared.identifiers import new_uuid
from app.shared.time import utc_now


class UUIDPrimaryKeyMixin:
    """UUID primary key generated in the application for event/audit correlation."""

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )


class TimestampMixin:
    """UTC creation/update timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )


class RevisionMixin:
    """SQLAlchemy version column that rejects stale updates."""

    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:
        return {
            "version_id_col": cls.revision,
            "version_id_generator": lambda current: 1 if current is None else current + 1,
        }
