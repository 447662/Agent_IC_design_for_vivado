from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_AGENT_CONFIG = ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent.json"
MIRROR_AGENT_CONFIG = ROOT / ".trae" / "agent" / "agent.json"


def _validated_config_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Canonical agent config must be valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Canonical agent config must be a JSON object")
    return payload


def synchronize_agent_config(
    canonical_path: Path = CANONICAL_AGENT_CONFIG,
    mirror_path: Path = MIRROR_AGENT_CONFIG,
    *,
    check: bool = False,
) -> bool:
    canonical = _validated_config_bytes(canonical_path)
    current = mirror_path.read_bytes() if mirror_path.is_file() else None
    if current == canonical:
        return True
    if check:
        return False
    mirror_path.parent.mkdir(parents=True, exist_ok=True)
    mirror_path.write_bytes(canonical)
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or verify the .trae compatibility agent config mirror."
    )
    parser.add_argument("--canonical", type=Path, default=CANONICAL_AGENT_CONFIG)
    parser.add_argument("--mirror", type=Path, default=MIRROR_AGENT_CONFIG)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    synchronized = synchronize_agent_config(
        args.canonical,
        args.mirror,
        check=args.check,
    )
    if not synchronized:
        print(
            "AGENT_CONFIG_DRIFT: run python scripts/sync_agent_config.py to regenerate {}".format(
                args.mirror
            ),
            file=sys.stderr,
        )
        return 1
    action = "verified" if args.check else "synchronized"
    print("Agent config mirror {}: {}".format(action, args.mirror))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
