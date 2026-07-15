"""Small, deterministic validator for configured JSON extension fields.

The supported schema subset is intentionally modest for Module 1: object
properties, required, additionalProperties, primitive type, enum, length, and
numeric bounds. A future form engine may replace this behind an application port.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any


class CustomFieldValidationError(ValueError):
    def __init__(self, issues: Sequence[dict[str, Any]]) -> None:
        super().__init__("Custom fields do not conform to their configured schema.")
        self.issues = tuple(issues)


def validate_json_object(
    value: Mapping[str, Any],
    schema: Mapping[str, Any] | None = None,
    *,
    path: str = "customFields",
) -> None:
    issues: list[dict[str, Any]] = []
    _ensure_json_value(value, path, issues)
    if schema:
        _validate_schema_value(value, schema, path, issues)
    if issues:
        raise CustomFieldValidationError(issues)


def _ensure_json_value(value: Any, path: str, issues: list[dict[str, Any]]) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, Decimal):
        issues.append({"path": path, "message": "Decimal values must be sent as JSON numbers."})
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                issues.append({"path": path, "message": "JSON object keys must be strings."})
            _ensure_json_value(item, f"{path}.{key}", issues)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _ensure_json_value(item, f"{path}[{index}]", issues)
        return
    issues.append(
        {"path": path, "message": f"{type(value).__name__} is not a supported JSON value."}
    )


def _validate_schema_value(
    value: Any,
    schema: Mapping[str, Any],
    path: str,
    issues: list[dict[str, Any]],
) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_type(value, expected_type):
        issues.append(
            {"path": path, "message": f"Expected {expected_type}.", "expectedType": expected_type}
        )
        return
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        issues.append({"path": path, "message": "Value is not in the configured enum."})
    if isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append({"path": path, "message": f"Minimum length is {minimum}."})
        if isinstance(maximum, int) and len(value) > maximum:
            issues.append({"path": path, "message": f"Maximum length is {maximum}."})
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum_value = schema.get("minimum")
        maximum_value = schema.get("maximum")
        if isinstance(minimum_value, (int, float)) and value < minimum_value:
            issues.append({"path": path, "message": f"Minimum value is {minimum_value}."})
        if isinstance(maximum_value, (int, float)) and value > maximum_value:
            issues.append({"path": path, "message": f"Maximum value is {maximum_value}."})
    if isinstance(value, Mapping):
        properties = schema.get("properties")
        configured = properties if isinstance(properties, Mapping) else {}
        required = schema.get("required")
        required_fields = required if isinstance(required, list) else []
        for field_name in required_fields:
            if isinstance(field_name, str) and field_name not in value:
                issues.append(
                    {"path": f"{path}.{field_name}", "message": "This custom field is required."}
                )
        if schema.get("additionalProperties") is False:
            for field_name in value:
                if field_name not in configured:
                    issues.append(
                        {
                            "path": f"{path}.{field_name}",
                            "message": "This custom field is not configured.",
                        }
                    )
        for field_name, field_value in value.items():
            field_schema = configured.get(field_name)
            if isinstance(field_schema, Mapping):
                _validate_schema_value(field_value, field_schema, f"{path}.{field_name}", issues)
    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                _validate_schema_value(item, item_schema, f"{path}[{index}]", issues)


def _matches_type(value: Any, expected_type: str) -> bool:
    return {
        "object": isinstance(value, Mapping),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected_type, False)
