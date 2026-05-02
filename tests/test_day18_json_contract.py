from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUCCESS_SCHEMA = PROJECT_ROOT / "schemas" / "detection_response.schema.json"
ERROR_SCHEMA = PROJECT_ROOT / "schemas" / "detection_error_response.schema.json"
EXAMPLE_FILES = [
    PROJECT_ROOT / "examples" / "day18_success_ai_generated.json",
    PROJECT_ROOT / "examples" / "day18_success_real_photo.json",
    PROJECT_ROOT / "examples" / "day18_success_uncertain.json",
    PROJECT_ROOT / "examples" / "day18_error_invalid_image.json",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_minimal_schema(instance: Any, schema: dict[str, Any], path: str = "$") -> None:
    if "const" in schema:
        assert instance == schema["const"], f"{path}: expected const {schema['const']!r}"
    if "enum" in schema:
        assert instance in schema["enum"], f"{path}: {instance!r} not in {schema['enum']!r}"

    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        assert any(_matches_type(instance, item) for item in expected_types), (
            f"{path}: {type(instance).__name__} does not match {expected_types!r}"
        )

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema:
            assert instance >= schema["minimum"], f"{path}: below minimum"
        if "maximum" in schema:
            assert instance <= schema["maximum"], f"{path}: above maximum"

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            assert key in instance, f"{path}: missing required key {key!r}"
        if schema.get("additionalProperties") is False:
            allowed = set(schema.get("properties", {}).keys())
            extra = set(instance.keys()) - allowed
            assert not extra, f"{path}: unexpected keys {sorted(extra)!r}"
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                validate_minimal_schema(instance[key], subschema, f"{path}.{key}")

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            validate_minimal_schema(item, schema["items"], f"{path}[{index}]")


def _matches_type(instance: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(instance, dict)
    if expected_type == "array":
        return isinstance(instance, list)
    if expected_type == "string":
        return isinstance(instance, str)
    if expected_type == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected_type == "boolean":
        return isinstance(instance, bool)
    if expected_type == "null":
        return instance is None
    return False


def test_schema_files_define_required_contract_fields() -> None:
    success_schema = load_json(SUCCESS_SCHEMA)
    error_schema = load_json(ERROR_SCHEMA)

    assert success_schema["required"] == ["schema_version", "status", "request_id", "data", "meta"]
    assert error_schema["required"] == ["schema_version", "status", "request_id", "error", "data", "meta"]
    assert success_schema["properties"]["status"]["enum"] == ["success"]
    assert error_schema["properties"]["status"]["enum"] == ["error"]


def test_example_json_files_validate_against_schemas() -> None:
    success_schema = load_json(SUCCESS_SCHEMA)
    error_schema = load_json(ERROR_SCHEMA)

    for path in EXAMPLE_FILES:
        payload = load_json(path)
        schema = error_schema if payload["status"] == "error" else success_schema
        validate_minimal_schema(payload, schema)


def test_success_schema_locks_key_enums_and_confidence_range() -> None:
    schema = load_json(SUCCESS_SCHEMA)
    result_props = schema["properties"]["data"]["properties"]["result"]["properties"]

    assert result_props["final_label"]["enum"] == ["ai_generated", "real_photo", "uncertain"]
    assert result_props["risk_level"]["enum"] == ["low", "medium", "high"]
    assert result_props["recommendation"]["properties"]["action"]["enum"] == ["allow", "review", "warn"]
    assert result_props["confidence"]["minimum"] == 0
    assert result_props["confidence"]["maximum"] == 1
