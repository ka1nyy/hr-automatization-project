"""FastAPI adapter for organization use cases."""

from app.modules.organization.api.routes import create_organization_router, router

__all__ = ["create_organization_router", "router"]
