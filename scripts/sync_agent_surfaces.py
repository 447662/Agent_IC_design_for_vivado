from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
import re
import sys
import tomllib
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BEGIN_MARKER = "# BEGIN GENERATED: .trae/config.json"
END_MARKER = "# END GENERATED: .trae/config.json"
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$|^[a-z0-9]$")


class AgentSurfaceSyncError(ValueError):
    pass


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentSurfaceSyncError(f"Invalid UTF-8 JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AgentSurfaceSyncError(f"Expected a JSON object: {path}")
    return payload


def _toml_literal(value: object) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return "[{}]".format(", ".join(_toml_literal(item) for item in value))
    if isinstance(value, Mapping):
        entries = []
        for key in sorted(value):
            if not isinstance(key, str) or not SAFE_NAME.fullmatch(key):
                raise AgentSurfaceSyncError(f"Unsupported TOML inline-table key: {key!r}")
            entries.append(f"{key} = {_toml_literal(value[key])}")
        return "{ " + ", ".join(entries) + " }"
    raise AgentSurfaceSyncError(f"Unsupported MCP config value: {value!r}")


def _render_mcp_block(trae_config: Mapping[str, object]) -> str:
    raw_servers = trae_config.get("mcpServers")
    if not isinstance(raw_servers, Mapping):
        raise AgentSurfaceSyncError(".trae/config.json must define mcpServers")
    lines = [BEGIN_MARKER]
    for raw_name in sorted(raw_servers):
        if not isinstance(raw_name, str) or not SAFE_NAME.fullmatch(raw_name):
            raise AgentSurfaceSyncError(f"Invalid MCP server name: {raw_name!r}")
        server = raw_servers[raw_name]
        if not isinstance(server, Mapping):
            raise AgentSurfaceSyncError(f"MCP server must be an object: {raw_name}")
        lines.extend((f"[mcp_servers.{raw_name}]",))
        for key in sorted(server):
            if not isinstance(key, str) or not SAFE_NAME.fullmatch(key):
                raise AgentSurfaceSyncError(
                    f"Invalid MCP option name for {raw_name}: {key!r}"
                )
            lines.append(f"{key} = {_toml_literal(server[key])}")
        lines.append("")
    if lines[-1] == "":
        lines.pop()
    lines.extend((END_MARKER, ""))
    return "\n".join(lines)


def _expected_codex_config(path: Path, generated_block: str) -> bytes:
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    begin = current.find(BEGIN_MARKER)
    end = current.find(END_MARKER)
    if (begin == -1) != (end == -1) or (begin != -1 and end < begin):
        raise AgentSurfaceSyncError(f"Malformed generated block markers: {path}")
    if begin != -1:
        end += len(END_MARKER)
        before = current[:begin].rstrip()
        after = current[end:].strip()
        unmanaged = "\n\n".join(part for part in (before, after) if part)
    else:
        unmanaged = current.strip()
        if unmanaged:
            try:
                parsed = tomllib.loads(unmanaged)
            except tomllib.TOMLDecodeError as exc:
                raise AgentSurfaceSyncError(f"Invalid existing Codex TOML: {path}") from exc
            generated = tomllib.loads(
                generated_block.replace(BEGIN_MARKER, "").replace(END_MARKER, "")
            )
            existing_servers = parsed.get("mcp_servers", {})
            generated_servers = generated.get("mcp_servers", {})
            if isinstance(existing_servers, Mapping) and isinstance(
                generated_servers, Mapping
            ):
                overlap = set(existing_servers) & set(generated_servers)
                if overlap:
                    raise AgentSurfaceSyncError(
                        "Unmanaged Codex MCP config conflicts with .trae: {}".format(
                            ", ".join(sorted(overlap))
                        )
                    )
    expected = "\n\n".join(part for part in (unmanaged, generated_block.strip()) if part)
    expected += "\n"
    try:
        tomllib.loads(expected)
    except tomllib.TOMLDecodeError as exc:
        raise AgentSurfaceSyncError("Generated Codex config is invalid TOML") from exc
    return expected.encode("utf-8")


def _declared_skill_names(agent_config: Mapping[str, object]) -> list[str]:
    raw_skills = agent_config.get("skills")
    if not isinstance(raw_skills, Sequence) or isinstance(raw_skills, str | bytes):
        raise AgentSurfaceSyncError(".trae/agent/agent.json must define a skills array")
    names: list[str] = []
    for entry in raw_skills:
        if not isinstance(entry, Mapping):
            raise AgentSurfaceSyncError("Agent skill entries must be objects")
        name = entry.get("name")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
            raise AgentSurfaceSyncError(f"Invalid agent skill name: {name!r}")
        if name in names:
            raise AgentSurfaceSyncError(f"Duplicate agent skill name: {name}")
        names.append(name)
    return names


def _write_if_changed(path: Path, expected: bytes, *, check: bool) -> bool:
    current = path.read_bytes() if path.is_file() else None
    if current == expected:
        return False
    if check:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.sync.tmp")
    temporary.write_bytes(expected)
    temporary.replace(path)
    return True


def synchronize_agent_surfaces(root: Path, *, check: bool = False) -> list[Path]:
    root = Path(root).resolve()
    trae_config = _load_json_object(root / ".trae" / "config.json")
    agent_config = _load_json_object(root / ".trae" / "agent" / "agent.json")
    changed: list[Path] = []

    codex_config = root / ".codex" / "config.toml"
    generated_block = _render_mcp_block(trae_config)
    expected_config = _expected_codex_config(codex_config, generated_block)
    if _write_if_changed(codex_config, expected_config, check=check):
        changed.append(codex_config)

    for skill_name in _declared_skill_names(agent_config):
        source = root / ".trae" / "skills" / skill_name / "SKILL.md"
        if not source.is_file():
            raise AgentSurfaceSyncError(f"Declared skill is missing: {source}")
        expected = source.read_bytes()
        for surface in (".codex", ".agents"):
            mirror = root / surface / "skills" / skill_name / "SKILL.md"
            if _write_if_changed(mirror, expected, check=check):
                changed.append(mirror)
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Synchronize .trae MCP and skill config into Codex agent surfaces."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        changed = synchronize_agent_surfaces(args.root, check=args.check)
    except AgentSurfaceSyncError as exc:
        print(f"AGENT_SURFACE_INVALID: {exc}", file=sys.stderr)
        return 2
    if args.check and changed:
        for path in changed:
            print(f"AGENT_SURFACE_DRIFT: {path}", file=sys.stderr)
        return 1
    action = "verified" if args.check else "synchronized"
    print(f"Agent surfaces {action}: {len(changed)} changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
