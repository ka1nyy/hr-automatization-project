from app.core.config import Environment, Settings
from app.main import create_app
from app.open_api import validate


def test_module2_openapi_contract_contains_required_operations() -> None:
    schema = create_app(
        Settings(
            environment=Environment.TEST,
            dev_auth_enabled=False,
            oidc_issuer=None,
            oidc_audience=None,
            oidc_jwks_url=None,
        )
    ).openapi()
    assert validate(schema) == []
    required = {
        "/api/v1/workflow/definitions",
        "/api/v1/workflow/tasks/{task_id}/actions",
        "/api/v1/documents/records/{document_id}/generate",
        "/api/v1/recruitment/requests",
        "/api/v1/recruitment/hiring-cases/{item_id}/complete",
        "/api/v1/terminations/{item_id}/schedule",
        "/api/v1/terminations/{item_id}/economic-review",
        "/api/v1/terminations/{item_id}/complete",
    }
    assert required <= set(schema["paths"])
