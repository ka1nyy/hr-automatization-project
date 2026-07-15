"""Destructive-but-guarded fixtures for a dedicated PostgreSQL test database."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Coroutine, Iterator
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _run[T](awaitable: Coroutine[Any, Any, T]) -> T:
    """Run psycopg async work on a selector loop, including on Windows."""

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(awaitable)


def _validated_test_url() -> URL:
    raw_url = os.getenv("SPK_TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip(
            "real PostgreSQL tests require an explicit SPK_TEST_DATABASE_URL",
            allow_module_level=False,
        )

    try:
        url = make_url(raw_url)
    except ArgumentError as exc:
        raise pytest.UsageError("SPK_TEST_DATABASE_URL is not a valid SQLAlchemy URL") from exc

    if url.drivername != "postgresql+psycopg":
        raise pytest.UsageError("SPK_TEST_DATABASE_URL must use the postgresql+psycopg driver")
    database_name = url.database or ""
    if "test" not in database_name.casefold():
        raise pytest.UsageError(
            "refusing destructive integration tests: the database name must visibly contain 'test'"
        )

    configured_url = os.getenv("SPK_DATABASE_URL")
    configured_environment = os.getenv("SPK_ENVIRONMENT", "development").casefold()
    if configured_url and configured_environment == "development":
        try:
            development_url = make_url(configured_url)
        except ArgumentError:
            development_url = None
        same_database = development_url is not None and (
            development_url.host,
            development_url.port or 5432,
            development_url.database,
        ) == (
            url.host,
            url.port or 5432,
            url.database,
        )
        if same_database:
            raise pytest.UsageError(
                "refusing to reset SPK_DATABASE_URL while SPK_ENVIRONMENT is development"
            )
    return url


def _reset_public_schema(url: URL) -> None:
    """Return the explicitly guarded test database to a genuinely empty schema."""

    reset_engine = create_engine(
        url,
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        with reset_engine.connect() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    finally:
        reset_engine.dispose()


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires a dedicated PostgreSQL test database",
    )


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[AsyncEngine]:
    """Reset a safe test DB, migrate it from empty, and bind app DB helpers to it."""

    url = _validated_test_url()
    rendered_url = url.render_as_string(hide_password=False)
    environment = pytest.MonkeyPatch()
    environment.setenv("SPK_DATABASE_URL", rendered_url)
    environment.setenv("SPK_ENVIRONMENT", "test")
    environment.setenv("SPK_DEV_AUTH_ENABLED", "false")

    test_engine: AsyncEngine | None = None
    database_session: Any | None = None
    database_package: Any | None = None
    original_runtime: tuple[Any, Any, Any, Any] | None = None
    try:
        from app.core.config import get_settings

        get_settings.cache_clear()
        _reset_public_schema(url)

        alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "head")

        database_session = import_module("app.core.database.session")
        database_package = import_module("app.core.database")
        original_runtime = (
            database_session.engine,
            database_session.async_session_factory,
            database_package.engine,
            database_package.async_session_factory,
        )

        test_engine = create_async_engine(rendered_url, poolclass=NullPool)
        test_factory = async_sessionmaker(
            bind=test_engine,
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )
        database_session.engine = test_engine
        database_session.async_session_factory = test_factory
        database_package.engine = test_engine
        database_package.async_session_factory = test_factory
        yield test_engine
    finally:
        if test_engine is not None:
            _run(test_engine.dispose())
        if database_session is not None and database_package is not None and original_runtime:
            (
                database_session.engine,
                database_session.async_session_factory,
                database_package.engine,
                database_package.async_session_factory,
            ) = original_runtime
        try:
            _reset_public_schema(url)
        finally:
            environment.undo()
            from app.core.config import get_settings

            get_settings.cache_clear()


@pytest.fixture(scope="session")
def seeded_database(migrated_database: AsyncEngine) -> AsyncEngine:
    """Run the deterministic seed twice so consumers also prove idempotence."""

    from app.seed import seed_database

    _run(seed_database())
    _run(seed_database())
    return migrated_database
