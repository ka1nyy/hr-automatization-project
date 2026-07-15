"""Identifier helpers used by domain and persistence layers."""

from __future__ import annotations

from uuid import UUID, uuid4, uuid5

SPK_DETERMINISTIC_NAMESPACE = UUID("0b9beac5-f4a9-5cf1-9c13-a5d2c8bf0f81")


def new_uuid() -> UUID:
    """Generate a random entity identifier."""

    return uuid4()


def deterministic_uuid(value: str, *, namespace: UUID = SPK_DETERMINISTIC_NAMESPACE) -> UUID:
    """Generate repeatable identifiers for development users and seed data."""

    return uuid5(namespace, value.strip().casefold())
