"""SQLAlchemy adapters for the organization module."""

from app.modules.organization.infrastructure.uow import SqlAlchemyOrganizationUnitOfWorkFactory

__all__ = ["SqlAlchemyOrganizationUnitOfWorkFactory"]
