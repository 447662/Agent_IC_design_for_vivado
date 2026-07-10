import json
from pathlib import Path


REQUIRED_TARGET_FIELDS = (
    "name",
    "display_name",
    "design_family",
    "aliases",
    "flows",
    "description",
)


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
