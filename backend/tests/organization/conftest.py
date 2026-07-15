"""Shared organization-service scenario fixture."""

from uuid import uuid4

import pytest
from app.modules.organization.application.service import OrganizationService
from app.modules.organization.domain.entities import Organization
from app.modules.organization.domain.ports import Actor

from .fakes import FakeOrganizationUnitOfWork, OrganizationScenario, RecordingAuthorizer


@pytest.fixture
def scenario() -> OrganizationScenario:
    organization = Organization(
        id=uuid4(),
        code="SPK",
        legal_name="SPK Ertis JSC",
        display_name="SPK Ertis",
    )
    uow = FakeOrganizationUnitOfWork()
    uow.organizations.seed(organization)
    actor = Actor(
        user_id=uuid4(),
        organization_id=organization.id,
        permissions=frozenset({"*"}),
        request_id=uuid4(),
    )
    authorizer = RecordingAuthorizer()
    service = OrganizationService(uow, authorizer=authorizer)
    return OrganizationScenario(organization, actor, uow, authorizer, service)
