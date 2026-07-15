"""Identity use cases independent of the authentication provider."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.modules.identity.application.ports import IdentityTransaction
from app.modules.identity.domain.entities import UserAccount, UserAccountStatus


class IdentityNotFoundError(LookupError):
    """Raised when an account cannot be resolved."""


class IdentityInactiveError(PermissionError):
    """Raised when an identity exists but cannot authenticate."""


class IdentityConcurrencyError(RuntimeError):
    """Raised when an identity was changed by another transaction."""


class IdentityService:
    def __init__(self, transaction_factory: Callable[[], IdentityTransaction]) -> None:
        self._transaction_factory = transaction_factory

    async def get_active_account(self, account_id: UUID) -> UserAccount:
        async with self._transaction_factory() as transaction:
            account = await transaction.accounts.get(account_id)
        if account is None:
            raise IdentityNotFoundError("User account was not found")
        if not account.is_active:
            raise IdentityInactiveError("User account is not active")
        return account

    async def resolve_external_subject(self, external_subject: str) -> UserAccount:
        async with self._transaction_factory() as transaction:
            account = await transaction.accounts.get_by_external_subject(external_subject)
        if account is None:
            raise IdentityNotFoundError("External identity is not linked to an account")
        if not account.is_active:
            raise IdentityInactiveError("User account is not active")
        return account

    async def provision_external_account(
        self,
        *,
        external_subject: str,
        username: str,
        display_name: str,
        email: str | None,
    ) -> UserAccount:
        """Idempotently provision an account after a trusted provider authenticates it."""

        async with self._transaction_factory() as transaction:
            existing = await transaction.accounts.get_by_external_subject(external_subject)
            if existing is not None:
                return existing
            account = UserAccount(
                external_subject=external_subject,
                username=username,
                display_name=display_name,
                email=email,
                status=UserAccountStatus.ACTIVE,
            )
            await transaction.accounts.add(account)
            return account

    async def record_login(self, account_id: UUID) -> UserAccount:
        async with self._transaction_factory() as transaction:
            current = await transaction.accounts.get(account_id)
            if current is None:
                raise IdentityNotFoundError("User account was not found")
            if not current.is_active:
                raise IdentityInactiveError("User account is not active")
            updated = current.record_login(at=datetime.now(UTC))
            saved = await transaction.accounts.update(
                updated,
                expected_revision=current.revision,
            )
            if not saved:
                raise IdentityConcurrencyError("User account was concurrently modified")
            return updated
