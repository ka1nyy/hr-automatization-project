"""Pydantic DTO base classes and consistent camelCase response envelopes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.logging.context import get_request_id


def _require_request_id(schema: dict[str, Any]) -> None:
    existing = schema.get("required")
    required = list(existing) if isinstance(existing, list) else []
    if "requestId" not in required:
        required.append("requestId")
    schema["required"] = required


def _require_meta(schema: dict[str, Any]) -> None:
    existing = schema.get("required")
    required = list(existing) if isinstance(existing, list) else []
    for field in ("data", "meta"):
        if field not in required:
            required.append(field)
    schema["required"] = required


class CamelModel(BaseModel):
    """DTO base; persistence models must be mapped into these API-safe schemas."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class ResponseMeta(CamelModel):
    model_config = ConfigDict(json_schema_extra=_require_request_id)

    request_id: str = Field(default_factory=get_request_id)


class PageMeta(ResponseMeta):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)


class DataResponse[T](CamelModel):
    model_config = ConfigDict(json_schema_extra=_require_meta)

    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)


class ListResponse[T](CamelModel):
    data: list[T]
    meta: PageMeta


class PageParams(CamelModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
