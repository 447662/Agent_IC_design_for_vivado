import json
from pathlib import Path


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

ALLOWED_CAPABILITY_STATUSES = {"PASS", "SKIP", "N/A"}


def _require_list(config_path, target, field):
    value = target.get(field)
    if not isinstance(value, list):
        raise ValueError("{} field must be a list: {}".format(config_path, field))
    return value


def _normalize_status(config_path, field, item):
    status = str(item.get("status", "")).strip().upper()
    if status not in ALLOWED_CAPABILITY_STATUSES:
        raise ValueError(
            "{} {} item has invalid status: {}".format(
                config_path,
                field,
                item.get("status"),
            )
        )
    item["status"] = status


def _normalize_object_list(config_path, target, field, required_fields):
    items = _require_list(config_path, target, field)
    normalized = []
    seen_ids = set()
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, dict):
            raise ValueError(
                "{} {} item {} must be an object".format(config_path, field, index)
            )
        item = dict(raw_item)
        for required_field in required_fields:
            value = str(item.get(required_field, "")).strip()
            if not value:
                raise ValueError(
                    "{} {} item {} missing required field: {}".format(
                        config_path,
                        field,
                        index,
                        required_field,
                    )
                )
            item[required_field] = value

        item_id = item.get("id")
        if item_id:
            if item_id in seen_ids:
                raise ValueError(
                    "{} {} contains duplicate id: {}".format(
                        config_path,
                        field,
                        item_id,
                    )
                )
            seen_ids.add(item_id)
        if "status" in required_fields:
            _normalize_status(config_path, field, item)
        normalized.append(item)
    target[field] = normalized
    return normalized


def _normalize_target_metadata(config_path, target):
    _normalize_object_list(
        config_path,
        target,
        "parameters",
        ("name", "default", "description"),
    )
    interfaces = _normalize_object_list(
        config_path,
        target,
        "interfaces",
        ("name", "direction", "width", "description"),
    )
    for item in interfaces:
        if item["direction"] not in {"input", "output", "inout"}:
            raise ValueError(
                "{} interfaces item has invalid direction: {}".format(
                    config_path,
                    item["direction"],
                )
            )

    checks = _require_list(config_path, target, "checks")
    target["checks"] = [str(check).strip() for check in checks if str(check).strip()]
    if not target["checks"]:
        raise ValueError("{} checks must not be empty".format(config_path))

    _normalize_object_list(
        config_path,
        target,
        "scenario_catalog",
        ("id", "type", "purpose", "status"),
    )
    _normalize_object_list(
        config_path,
        target,
        "coverage_metrics",
        ("id", "label", "source", "status"),
    )
    _normalize_object_list(
        config_path,
        target,
        "artifact_manifest",
        ("id", "path", "status"),
    )

    notes = target.get("notes", [])
    if not isinstance(notes, list):
        raise ValueError("{} field must be a list: notes".format(config_path))
    target["notes"] = [str(note).strip() for note in notes if str(note).strip()]


def load_target_registry(targets_dir):
    targets_dir = Path(targets_dir)
    if not targets_dir.exists():
        raise FileNotFoundError(
            "Target registry directory not found: {}".format(targets_dir)
        )

    targets = {}
    for config_path in sorted(targets_dir.glob("*.json")):
        with config_path.open("r", encoding="utf-8") as config_file:
            target = json.load(config_file)

        for field in REQUIRED_TARGET_FIELDS:
            if field not in target:
                raise ValueError(
                    "{} missing required field: {}".format(config_path, field)
                )

        target_name = str(target["name"]).strip().lower()
        if not target_name:
            raise ValueError("{} has empty target name".format(config_path))
        if target_name in targets:
            raise ValueError("Duplicate RTL target: {}".format(target_name))

        target["name"] = target_name
        target["aliases"] = [
            str(alias).strip()
            for alias in target.get("aliases", [])
            if str(alias).strip()
        ]
        target["flows"] = [
            str(flow).strip()
            for flow in target.get("flows", [])
            if str(flow).strip()
        ]
        _normalize_target_metadata(config_path, target)
        targets[target_name] = target

    if not targets:
        raise ValueError("No RTL target configs found in {}".format(targets_dir))
    return targets


def list_targets(targets):
    return [targets[name] for name in sorted(targets)]


def get_target(targets, target):
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
