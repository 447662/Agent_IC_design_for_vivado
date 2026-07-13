from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SYNC_SCRIPT = ROOT / "scripts" / "sync_agent_config.py"
QUALITY_GENERATOR = ROOT / "scripts" / "generate_quality_summary.py"
QUALITY_WORKFLOW = ROOT / ".github" / "workflows" / "python-quality.yml"
TRAE_README = ROOT / ".trae" / "agent" / "README.md"
CANONICAL_CONFIG = ROOT / "src" / "digital_ic_agent" / "_runtime" / "agent.json"
MIRROR_CONFIG = ROOT / ".trae" / "agent" / "agent.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_package_metadata_is_complete_without_guessing_a_license():
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]

    assert project["description"] == (
        "Evidence-driven digital IC frontend agent for RTL, UVM, Vivado, and waveform workflows."
    )
    assert project["readme"] == "README.md"
    assert project["authors"] == [{"name": "Digital IC Designer Team"}]
    assert {
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    } <= set(project["classifiers"])
    assert project["urls"] == {
        "Homepage": "https://github.com/447662/Agent_IC_design_for_vivado",
        "Repository": "https://github.com/447662/Agent_IC_design_for_vivado",
        "Issues": "https://github.com/447662/Agent_IC_design_for_vivado/issues",
    }
    assert "license" not in project
    assert not any(item.startswith("License ::") for item in project["classifiers"])


def test_agent_config_sync_detects_drift_without_mutating_in_check_mode(tmp_path):
    sync = _load_module("p2_agent_config_sync", SYNC_SCRIPT)
    canonical = tmp_path / "canonical.json"
    mirror = tmp_path / "mirror.json"
    canonical.write_text('{"name":"canonical"}\n', encoding="utf-8")
    mirror.write_text('{"name":"drifted"}\n', encoding="utf-8")
    original_mirror = mirror.read_bytes()

    assert sync.synchronize_agent_config(canonical, mirror, check=True) is False
    assert mirror.read_bytes() == original_mirror
    assert sync.synchronize_agent_config(canonical, mirror, check=False) is True
    assert mirror.read_bytes() == canonical.read_bytes()
    assert sync.synchronize_agent_config(canonical, mirror, check=True) is True


def test_agent_config_sync_rejects_invalid_canonical_json(tmp_path):
    sync = _load_module("p2_agent_config_sync_invalid", SYNC_SCRIPT)
    canonical = tmp_path / "canonical.json"
    mirror = tmp_path / "mirror.json"
    canonical.write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        sync.synchronize_agent_config(canonical, mirror, check=False)


def test_repository_enforces_package_agent_config_as_single_source():
    sync = _load_module("p2_agent_config_sync_repository", SYNC_SCRIPT)
    generator = _load_module("p2_quality_canonical_config", QUALITY_GENERATOR)
    workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")
    trae_readme = TRAE_README.read_text(encoding="utf-8")

    assert sync.CANONICAL_AGENT_CONFIG == CANONICAL_CONFIG
    assert sync.MIRROR_AGENT_CONFIG == MIRROR_CONFIG
    assert CANONICAL_CONFIG.read_bytes() == MIRROR_CONFIG.read_bytes()
    assert sync.synchronize_agent_config(check=True) is True
    assert generator.DEFAULT_AGENT_CONFIG == CANONICAL_CONFIG
    assert "scripts/sync_agent_config.py --check" in workflow
    assert "scripts/sync_agent_config.py" in trae_readme
    assert "生成镜像" in trae_readme
