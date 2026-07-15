from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_agent_surfaces.py"
TRAE_CONFIG = ROOT / ".trae" / "config.json"
TRAE_AGENT_CONFIG = ROOT / ".trae" / "agent" / "agent.json"


def _declared_skill_names(root: Path) -> list[str]:
    payload = json.loads(
        (root / ".trae" / "agent" / "agent.json").read_text(encoding="utf-8")
    )
    return [str(skill["name"]) for skill in payload["skills"]]


def test_repository_codex_and_agents_surfaces_match_trae() -> None:
    assert SYNC_SCRIPT.is_file()
    trae_config = json.loads(TRAE_CONFIG.read_text(encoding="utf-8"))
    codex_config = tomllib.loads(
        (ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert codex_config["mcp_servers"] == trae_config["mcpServers"]

    for skill_name in _declared_skill_names(ROOT):
        source = ROOT / ".trae" / "skills" / skill_name / "SKILL.md"
        assert source.is_file()
        for surface in (".codex", ".agents"):
            mirror = ROOT / surface / "skills" / skill_name / "SKILL.md"
            assert mirror.read_bytes() == source.read_bytes()

    result = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_sync_preserves_unmanaged_skills_and_detects_drift(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    trae_skill = root / ".trae" / "skills" / "legacy-skill"
    trae_skill.mkdir(parents=True)
    (trae_skill / "SKILL.md").write_text(
        "---\nname: legacy-skill\ndescription: Legacy skill.\n---\n\nUse it.\n",
        encoding="utf-8",
    )
    (root / ".trae" / "config.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "synthpilot": {
                        "command": "uvx",
                        "args": ["synthpilot==0.1.0"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    agent_dir = root / ".trae" / "agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "agent.json").write_text(
        json.dumps(
            {
                "skills": [
                    {
                        "name": "legacy-skill",
                        "path": "./skills/legacy-skill/SKILL.md",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    unmanaged = root / ".agents" / "skills" / "digital-ic-design" / "SKILL.md"
    unmanaged.parent.mkdir(parents=True)
    unmanaged.write_text("keep me\n", encoding="utf-8")

    synchronized = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--root", str(root)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert synchronized.returncode == 0, synchronized.stderr
    assert unmanaged.read_text(encoding="utf-8") == "keep me\n"
    assert tomllib.loads(
        (root / ".codex" / "config.toml").read_text(encoding="utf-8")
    )["mcp_servers"]["synthpilot"]["command"] == "uvx"
    for surface in (".codex", ".agents"):
        assert (
            root / surface / "skills" / "legacy-skill" / "SKILL.md"
        ).read_bytes() == (trae_skill / "SKILL.md").read_bytes()

    (trae_skill / "SKILL.md").write_text("changed\n", encoding="utf-8")
    drift = subprocess.run(
        [sys.executable, str(SYNC_SCRIPT), "--root", str(root), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert drift.returncode == 1
    assert "AGENT_SURFACE_DRIFT" in drift.stderr
