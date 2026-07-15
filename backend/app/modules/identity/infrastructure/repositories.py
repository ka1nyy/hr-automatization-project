"""SQLAlchemy identity repository and unit of work."""

from __future__ import annotations

from types import TracebackType
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from app.core.errors import ConcurrencyConflictError
from app.modules.identity.application.ports import UserAccountRepository
from app.modules.identity.domain.entities import UserAccount, UserAccountStatus
from app.modules.identity.infrastructure.models import UserAccountModel


def _to_domain(model: UserAccountModel) -> UserAccount:
    return UserAccount(
        id=model.id,
        external_subject=model.external_subject,
        username=model.username,
        email=model.email,
        display_name=model.display_name,
        employee_id=model.employee_id,
        status=UserAccountStatus(model.status),
        last_login_at=model.last_login_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        revision=model.revision,
    )


class SqlAlchemyUserAccountRepository(UserAccountRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, account_id: UUID) -> UserAccount | None:
        model = await self._session.get(UserAccountModel, account_id)
        return _to_domain(model) if model is not None else None

    async def get_by_external_subject(self, external_subject: str) -> UserAccount | None:
        model = await self._session.scalar(
            select(UserAccountModel).where(
                UserAccountModel.external_subject == external_subject,
                UserAccountModel.active.is_(True),
            )
        )
        return _to_domain(model) if model is not None else None

    async def get_by_username(self, username: str) -> UserAccount | None:
        model = await self._session.scalar(
            select(UserAccountModel).where(
                UserAccountModel.username == username,
                UserAccountModel.active.is_(True),
            )
        )
        return _to_domain(model) if model is not None else None

    async def add(self, account: UserAccount) -> None:
        self._session.add(
            UserAccountModel(
                id=account.id,
                external_subject=account.external_subject,
                username=account.username,
                email=account.email,
                display_name=account.display_name,
                employee_id=account.employee_id,
                status=account.status.value,
                active=account.is_active,
                last_login_at=account.last_login_at,
                created_at=account.created_at,
                updated_at=account.updated_at,
                revision=account.revision,
            )
        )
        await self._session.flush()

    async def update(self, account: UserAccount, *, expected_revision: int) -> bool:
        result = await self._session.execute(
            update(UserAccountModel)
            .where(
                UserAccountModel.id == account.id,
                UserAccountModel.revision == expected_revision,
            )
            .values(
                username=account.username,
                email=account.email,
                display_name=account.display_name,
                employee_id=account.employee_id,
                status=account.status.value,
                active=account.is_active,
                last_login_at=account.last_login_at,
                updated_at=account.updated_at,
                revision=account.revision,
            )
        )
        await self._session.flush()
        rowcount = getattr(result, "rowcount", None)
        if not isinstance(rowcount, int):
            raise RuntimeError("Database driver did not report the updated row count")
        return rowcount == 1


class SqlAlchemyIdentityTransaction:
    """Request-scoped SQLAlchemy transaction implementing the application port."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._accounts = SqlAlchemyUserAccountRepository(session)
        self._context: AsyncSessionTransaction | None = None

    @property
    def accounts(self) -> UserAccountRepository:
        return self._accounts

    async def __aenter__(self) -> SqlAlchemyIdentityTransaction:
        self._context = self._session.begin()
        await self._context.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._context is None:
            raise RuntimeError("Identity transaction was not entered")
        try:
            await self._context.__aexit__(exc_type, exc, traceback)
        except IntegrityError as error:
            await self._session.rollback()
            raise ConcurrencyConflictError(
                "The identity change conflicts with persisted data."
            ) from error
        if isinstance(exc, IntegrityError):
            raise ConcurrencyConflictError(
                "The identity change conflicts with persisted data."
            ) from exc
