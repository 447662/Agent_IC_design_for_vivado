import json
from pathlib import Path
from collections.abc import Iterable
from typing import Any, NoReturn, cast


REQUIRED_TARGET_FIELDS = (
    "name",
    "display_name",
    "design_family",
    "aliases",
    "flows",
    "description",
    "parameters",
    "interfaces",
    "checks",
    "scenario_catalog",
    "coverage_metrics",
    "artifact_manifest",
)

ALLOWED_TARGET_FIELDS = set(REQUIRED_TARGET_FIELDS) | {"notes", "handler"}
ALLOWED_CAPABILITY_STATUSES = {"PASS", "SKIP", "N/A"}

PARAMETER_FIELDS = {"name", "default", "description"}
INTERFACE_FIELDS = {"name", "direction", "width", "description"}
SCENARIO_FIELDS = {"id", "type", "purpose", "status", "coverage_match"}
COVERAGE_FIELDS = {"id", "label", "source", "status"}
ARTIFACT_FIELDS = {"id", "path", "status"}


def _fail(config_path: Path, field_path: str, message: str) -> NoReturn:
    raise ValueError("{}: {}: {}".format(config_path, field_path, message))


def _require_object(
    config_path: Path,
    value: Any,
    field_path: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(config_path, field_path, "must be an object")
    return cast(dict[str, Any], value)


def _require_list(
    config_path: Path,
    value: Any,
    field_path: str,
) -> list[Any]:
    if not isinstance(value, list):
        _fail(config_path, field_path, "must be a list")
    return value


def _validate_fields(
    config_path: Path,
    value: dict[str, Any],
    field_path: str,
    allowed: set[str],
    required: Iterable[str] | None = None,
) -> None:
    for field in sorted(set(value) - allowed):
        _fail(config_path, "{}.{}".format(field_path, field), "unknown field")
    required_fields = required if required is not None else sorted(allowed)
    for field in required_fields:
        if field not in value:
            _fail(
                config_path,
                "{}.{}".format(field_path, field),
                "missing required field: {}".format(field),
            )


def _require_string(
    config_path: Path,
    value: Any,
    field_path: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(config_path, field_path, "must be a non-empty string")
    return value.strip()


def _require_unique_string_list(
    config_path: Path,
    value: Any,
    field_path: str,
    *,
    normalize_for_duplicates: bool = False,
    allow_empty: bool = False,
) -> list[str]:
    raw_items = _require_list(config_path, value, field_path)
    if not allow_empty and not raw_items:
        _fail(config_path, field_path, "must not be empty")
    items: list[str] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        item = _require_string(
            config_path,
            raw_item,
            "{}[{}]".format(field_path, index),
        )
        duplicate_key = (
            item.lower().replace("_", "-")
            if normalize_for_duplicates
            else item
        )
        if duplicate_key in seen:
            _fail(config_path, field_path, "duplicate value")
        seen.add(duplicate_key)
        items.append(item)
    return items


def _normalize_status(
    config_path: Path,
    field_path: str,
    item: dict[str, Any],
) -> None:
    status = _require_string(
        config_path,
        item["status"],
        field_path + ".status",
    ).upper()
    if status not in ALLOWED_CAPABILITY_STATUSES:
        _fail(config_path, field_path + ".status", "invalid status")
    item["status"] = status


def _normalize_object_list(
    config_path: Path,
    target: dict[str, Any],
    field: str,
    allowed_fields: set[str],
    required_fields: set[str],
) -> list[dict[str, Any]]:
    field_path = "$.{}".format(field)
    raw_items = _require_list(config_path, target[field], field_path)
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        item_path = "{}[{}]".format(field_path, index)
        item = _require_object(config_path, raw_item, item_path)
        _validate_fields(
            config_path,
            item,
            item_path,
            allowed_fields,
            required_fields,
        )
        for required_field in required_fields:
            item[required_field] = _require_string(
                config_path,
                item[required_field],
                "{}.{}".format(item_path, required_field),
            )

        item_id = item.get("id")
        if item_id is not None:
            normalized_id = _require_string(
                config_path,
                item_id,
                item_path + ".id",
            )
            if normalized_id in seen_ids:
                _fail(config_path, field_path, "duplicate id")
            seen_ids.add(normalized_id)
            item["id"] = normalized_id
        if "status" in required_fields:
            _normalize_status(config_path, item_path, item)
        normalized.append(item)
    target[field] = normalized
    return normalized


def _normalize_target_metadata(
    config_path: Path,
    target: dict[str, Any],
) -> None:
    _normalize_object_list(
        config_path,
        target,
        "parameters",
        PARAMETER_FIELDS,
        PARAMETER_FIELDS,
    )
    interfaces = _normalize_object_list(
        config_path,
        target,
        "interfaces",
        INTERFACE_FIELDS,
        INTERFACE_FIELDS,
    )
    for index, item in enumerate(interfaces):
        if item["direction"] not in {"input", "output", "inout"}:
            _fail(
                config_path,
                "$.interfaces[{}].direction".format(index),
                "invalid direction",
            )

    target["checks"] = _require_unique_string_list(
        config_path,
        target["checks"],
        "$.checks",
    )

    _normalize_object_list(
        config_path,
        target,
        "scenario_catalog",
        SCENARIO_FIELDS,
        {"id", "type", "purpose", "status"},
    )
    _normalize_object_list(
        config_path,
        target,
        "coverage_metrics",
        COVERAGE_FIELDS,
        COVERAGE_FIELDS,
    )
    _normalize_object_list(
        config_path,
        target,
        "artifact_manifest",
        ARTIFACT_FIELDS,
        ARTIFACT_FIELDS,
    )

    notes = target.get("notes", [])
    if notes:
        target["notes"] = _require_unique_string_list(
            config_path,
            notes,
            "$.notes",
        )
    elif not isinstance(notes, list):
        _fail(config_path, "$.notes", "must be a list")
    else:
        target["notes"] = []


def load_target_registry(targets_dir: Any) -> dict[str, dict[str, Any]]:
    resolved_dir = Path(targets_dir)
    if not resolved_dir.exists():
        raise FileNotFoundError(
            "Target registry directory not found: {}".format(resolved_dir)
        )

    targets: dict[str, dict[str, Any]] = {}
    claimed_names: dict[str, str] = {}
    for config_path in sorted(resolved_dir.glob("*.json")):
        with config_path.open("r", encoding="utf-8") as config_file:
            raw_target = json.load(config_file)
        target = _require_object(config_path, raw_target, "$")
        _validate_fields(
            config_path,
            target,
            "$",
            ALLOWED_TARGET_FIELDS,
            REQUIRED_TARGET_FIELDS,
        )

        target_name = _require_string(
            config_path,
            target["name"],
            "$.name",
        ).lower().replace("_", "-")
        if target_name in targets:
            _fail(config_path, "$.name", "duplicate target")

        target["name"] = target_name
        target["display_name"] = _require_string(
            config_path,
            target["display_name"],
            "$.display_name",
        )
        target["design_family"] = _require_string(
            config_path,
            target["design_family"],
            "$.design_family",
        )
        target["description"] = _require_string(
            config_path,
            target["description"],
            "$.description",
        )
        target["aliases"] = _require_unique_string_list(
            config_path,
            target["aliases"],
            "$.aliases",
            allow_empty=True,
        )
        target["flows"] = _require_unique_string_list(
            config_path,
            target["flows"],
            "$.flows",
            allow_empty=True,
        )

        normalized_names = {
            target_name,
            *(
                alias.lower().replace("_", "-")
                for alias in cast(list[str], target["aliases"])
            ),
        }
        for normalized_name in normalized_names:
            owner = claimed_names.get(normalized_name)
            if owner is not None and owner != target_name:
                _fail(
                    config_path,
                    "$.aliases",
                    "alias conflict: {} is claimed by {} and {}".format(
                        normalized_name,
                        owner,
                        target_name,
                    ),
                )
        for normalized_name in normalized_names:
            claimed_names[normalized_name] = target_name

        _normalize_target_metadata(config_path, target)
        if "handler" not in target:
            _fail(
                config_path,
                "$.handler",
                "missing required field: handler",
            )
        target["handler"] = _require_string(
            config_path,
            target["handler"],
            "$.handler",
        )
        targets[target_name] = target

    if not targets:
        raise ValueError("No RTL target configs found in {}".format(resolved_dir))
    return targets


def list_targets(
    targets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [targets[name] for name in sorted(targets)]


def get_target(
    targets: dict[str, dict[str, Any]],
    target: Any,
) -> dict[str, Any]:
    target_name = str(target).strip().lower().replace("_", "-")
    for registered in list_targets(targets):
        candidate_names = [registered["name"], *registered.get("aliases", [])]
        normalized_names = {
            str(name).strip().lower().replace("_", "-")
            for name in candidate_names
        }
        if target_name in normalized_names:
            return registered
    raise ValueError("Unsupported RTL target: {}".format(target))
