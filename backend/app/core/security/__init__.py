"""Provider-neutral authentication contracts and adapters."""

from app.core.security.authorization import DenyAllAuthorization, get_authorization_port
from app.core.security.dependencies import get_current_principal, get_optional_principal
from app.core.security.factory import build_token_authenticator
from app.core.security.identity import Principal
from app.core.security.middleware import AuthenticationMiddleware
from app.core.security.ports import AuthenticationPort, AuthorizationPort

__all__ = [
    "AuthenticationMiddleware",
    "AuthenticationPort",
    "AuthorizationPort",
    "DenyAllAuthorization",
    "Principal",
    "build_token_authenticator",
    "get_authorization_port",
    "get_current_principal",
    "get_optional_principal",
]
