"""Generate and validate the frontend-facing OpenAPI contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.main import app

REQUIRED_PATHS = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/api/v1/organization/structure/active",
        "/api/v1/organization/structure/versions",
        "/api/v1/organization/structure/drafts",
        "/api/v1/positions",
        "/api/v1/staffing-slots",
        "/api/v1/employees",
        "/api/v1/employee-assignments",
        "/api/v1/delegations",
        "/api/v1/access/roles",
        "/api/v1/access/permissions",
        "/api/v1/audit/events",
    }
)


def validate(schema: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    paths = set(schema.get("paths", {}))
    missing = sorted(REQUIRED_PATHS - paths)
    if missing:
        problems.append(f"Missing required paths: {', '.join(missing)}")
    for name, component in schema.get("components", {}).get("schemas", {}).items():
        for property_name in component.get("properties", {}):
            if "_" in property_name:
                problems.append(f"Schema {name} exposes non-camelCase field {property_name}")
    operation_ids: list[str] = []
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "operationId" in operation:
                operation_ids.append(str(operation["operationId"]))
    duplicates = sorted(
        operation_id for operation_id in set(operation_ids) if operation_ids.count(operation_id) > 1
    )
    if duplicates:
        problems.append(f"Duplicate operation IDs: {', '.join(duplicates)}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Validate required API invariants")
    parser.add_argument("--output", type=Path, help="Write formatted OpenAPI JSON")
    arguments = parser.parse_args()
    schema = app.openapi()
    problems = validate(schema)
    if arguments.output is not None:
        arguments.output.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if arguments.check and problems:
        raise SystemExit("\n".join(problems))
    print(f"OpenAPI valid: {len(schema['paths'])} paths; {len(problems)} problems")


if __name__ == "__main__":
    main()
