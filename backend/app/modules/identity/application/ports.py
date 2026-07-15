"""Persistence ports for provider-neutral identities."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.entities import UserAccount


class UserAccountRepository(Protocol):
    async def get(self, account_id: UUID) -> UserAccount | None: ...

    async def get_by_external_subject(self, external_subject: str) -> UserAccount | None: ...

    async def get_by_username(self, username: str) -> UserAccount | None: ...

    async def add(self, account: UserAccount) -> None: ...

    async def update(self, account: UserAccount, *, expected_revision: int) -> bool: ...


class IdentityTransaction(Protocol):
    async def __aenter__(self) -> IdentityTransaction: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    @property
    def accounts(self) -> UserAccountRepository: ...
