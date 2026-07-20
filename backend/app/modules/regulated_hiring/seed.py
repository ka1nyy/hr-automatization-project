"""Idempotent reference data for the regulated hiring process."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.organization.infrastructure.models import StaffingSlotModel
from app.shared.identifiers import deterministic_uuid

from .domain.catalog import FORM_POLICIES, STAGE_POLICIES
from .infrastructure.models import (
    AuthorityBindingModel,
    HiringFormDefinitionModel,
    HiringStageDefinitionModel,
    NormativeSourceModel,
)

SEED_TIME = datetime(2026, 1, 8, 9, 0, tzinfo=UTC)
EFFECTIVE_DATE = date(2026, 1, 8)


def _id(kind: str, key: str) -> UUID:
    return deterministic_uuid(f"seed:regulated-hiring:{kind}:{key}")


async def _insert(session: AsyncSession, table: Table, rows: list[dict[str, Any]]) -> None:
    if rows:
        await session.execute(postgresql_insert(table).values(rows).on_conflict_do_nothing())


SOURCE_ROWS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "HIERARCHY_PDF",
        "СПК ЕРТЫС: иерархия, роли и модель данных",
        "process_model",
        "model",
        "СПК ЕРТЫС ИЕРАРХИЯ.pdf",
    ),
    ("HIRING_PDF", "Регламент бизнес-процесса НАЙМ", "hiring_regulation", "confirmed", "НАЙМ.pdf"),
    (
        "REG_DDO",
        "Положение о ДДО",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение ДДО.docx",
    ),
    (
        "REG_DEP",
        "Положение о ДЭП",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение_о_ДЭП 2026.doc",
    ),
    (
        "REG_LEGAL",
        "Положение о юридическом департаменте",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение об ЮД 08.01.2026.doc",
    ),
    (
        "REG_DI",
        "Положение о ДИ",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение ДИ.docx",
    ),
    (
        "REG_DK",
        "Положение о ДК",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение ДК.doc",
    ),
    (
        "REG_DS",
        "Положение о ДС",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение ДС.doc",
    ),
    (
        "REG_DSF",
        "Положение о ДСФ",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение ДСФ.doc",
    ),
    (
        "REG_DA",
        "Положение о ДА",
        "department_regulation",
        "confirmed",
        "СПК положения/Положение  ДА.doc",
    ),
)

CONFIRMED_DIRECTOR_SOURCES: dict[str, str] = {
    "stabilization-fund-director": "REG_DSF",
    "economic-planning-director": "REG_DEP",
    "legal-director": "REG_LEGAL",
    "investment-director": "REG_DI",
    "credit-director": "REG_DK",
    "construction-director": "REG_DS",
    "asset-director": "REG_DA",
    "document-support-personnel-director": "REG_DDO",
}


async def seed_regulated_hiring(session: AsyncSession, *, organization_id: UUID) -> None:
    source_ids = {code: _id("source", code) for code, *_ in SOURCE_ROWS}
    await _insert(
        session,
        cast(Table, NormativeSourceModel.__table__),
        [
            {
                "id": source_ids[code],
                "organization_id": organization_id,
                "code": code,
                "title": title,
                "source_type": source_type,
                "authority_status": status,
                "file_reference": reference,
                "effective_from": EFFECTIVE_DATE if status == "confirmed" else None,
                "approved_at": SEED_TIME if status == "confirmed" else None,
                "notes": (
                    "Project model; every assertion is separately classified."
                    if code == "HIERARCHY_PDF"
                    else "Registered from the source package designated by the customer."
                ),
                "revision": 1,
                "created_at": SEED_TIME,
                "updated_at": SEED_TIME,
            }
            for code, title, source_type, status, reference in SOURCE_ROWS
        ],
    )
    await _insert(
        session,
        cast(Table, HiringStageDefinitionModel.__table__),
        [
            {
                "id": _id("stage", item.code.value),
                "organization_id": organization_id,
                "source_id": source_ids["HIRING_PDF"],
                "version_number": 1,
                "sequence": item.sequence,
                "code": item.code.value,
                "name": item.name,
                "owner_role_code": item.owner_role_code,
                "sla_min_days": item.sla_min_days,
                "sla_max_days": item.sla_max_days,
                "working_days": item.working_days,
                "entry_criteria": {},
                "exit_criteria": {},
                "active": True,
                "revision": 1,
                "created_at": SEED_TIME,
                "updated_at": SEED_TIME,
            }
            for item in STAGE_POLICIES
        ],
    )
    await _insert(
        session,
        cast(Table, HiringFormDefinitionModel.__table__),
        [
            {
                "id": _id("form", item.code),
                "organization_id": organization_id,
                "source_id": source_ids["HIRING_PDF"],
                "version_number": 1,
                "sequence": item.sequence,
                "code": item.code,
                "name": item.name,
                "owner_role_code": item.owner_role_code,
                "signer_role_codes": list(item.signer_role_codes),
                "data_schema": {},
                "immutable_after_signing": True,
                "active": True,
                "revision": 1,
                "created_at": SEED_TIME,
                "updated_at": SEED_TIME,
            }
            for item in FORM_POLICIES
        ],
    )

    slot_ids = set(await session.scalars(select(StaffingSlotModel.id)))
    confirmed = {
        deterministic_uuid(f"seed:staffing-slot:{slot_key}"): source_code
        for slot_key, source_code in CONFIRMED_DIRECTOR_SOURCES.items()
    }
    await _insert(
        session,
        cast(Table, AuthorityBindingModel.__table__),
        [
            {
                "id": _id("authority", str(slot_id)),
                "organization_id": organization_id,
                "entity_type": "staffing_slot",
                "entity_id": slot_id,
                "authority_status": "confirmed" if slot_id in confirmed else "document_required",
                "source_id": (
                    source_ids[confirmed[slot_id]]
                    if slot_id in confirmed
                    else source_ids["HIERARCHY_PDF"]
                ),
                "assertion": (
                    "Department director position is established by the department regulation."
                    if slot_id in confirmed
                    else (
                        "The slot exists in the project model but requires an approved "
                        "staffing schedule or equivalent authority document."
                    )
                ),
                "effective_from": EFFECTIVE_DATE,
                "effective_to": None,
                "granted_permissions": [],
                "revision": 1,
                "created_at": SEED_TIME,
                "updated_at": SEED_TIME,
            }
            for slot_id in sorted(slot_ids, key=str)
        ],
    )
