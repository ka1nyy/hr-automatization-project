"""FastAPI adapter for employee use cases."""

from .dependencies import get_employee_actor
from .routes import create_employee_router, employee_exception_handler

__all__ = ["create_employee_router", "employee_exception_handler", "get_employee_actor"]
