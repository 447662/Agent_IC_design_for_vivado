import copy
import inspect
import json
import sys
from pathlib import Path
from typing import get_args, get_type_hints

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
AGENT_CONFIG_PATH = AGENT_DIR / "agent.json"
SYNC_TARGET_PATH = AGENT_DIR / "targets" / "sync_fifo.json"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime.agent_composition import build_agent  # noqa: E402
from digital_ic_agent._runtime import agent_config  # noqa: E402
from digital_ic_agent._runtime.agent_config import load_agent_config  # noqa: E402
from digital_ic_agent._runtime.target_registry import load_target_registry  # noqa: E402


def write_agent_config(tmp_path: Path, mutate) -> Path:
    config = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    mutate(config)
    path = tmp_path / "agent.json"
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_target_config(tmp_path: Path, mutate) -> Path:
    config = json.loads(SYNC_TARGET_PATH.read_text(encoding="utf-8"))
    mutate(config)
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    path = targets_dir / "sync_fifo.json"
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return targets_dir


def test_agent_config_schema_accepts_current_configuration():
    config = load_agent_config(AGENT_CONFIG_PATH)

    assert config["name"] == "digital-ic-frontend-agent"
    assert [skill["action"] for skill in config["skills"]] == [
        "design-document",
        "rtl-implementation",
        "verification-plan",
    ]


def test_agent_config_exposes_typed_contracts():
    hints = get_type_hints(agent_config.load_agent_config)
    signature = inspect.signature(agent_config.load_agent_config)

    assert hints["config_path"] == str | Path
    assert hints["return"] is agent_config.AgentConfig
    assert signature.return_annotation == "AgentConfig"
    assert agent_config.SkillAction.__name__ == "Literal"
    assert set(get_args(agent_config.SkillAction)) == {
        "design-document",
        "rtl-implementation",
        "verification-plan",
    }
    assert set(agent_config.AgentConfig.__annotations__) == {
        "name",
        "version",
        "description",
        "author",
        "createdDate",
        "skills",
        "mcpServers",
        "cliTools",
        "workflow",
        "requirementAnalysis",
    }


@pytest.mark.parametrize(
    ("mutate", "field_path", "message"),
    [
        (
            lambda config: config.__setitem__("unexpected", True),
            "$.unexpected",
            "unknown field",
        ),
        (
            lambda config: config["skills"][1].__setitem__(
                "action",
                config["skills"][0]["action"],
            ),
            "$.skills[1].action",
            "duplicate action",
        ),
        (
            lambda config: config["skills"][0].__setitem__("priority", "high"),
            "$.skills[0].priority",
            "must be an integer",
        ),
        (
            lambda config: config["skills"][0].__setitem__(
                "requiredCapabilities",
                ["missing-capability"],
            ),
            "$.skills[0].requiredCapabilities[0]",
            "unknown capability",
        ),
        (
            lambda config: config["cliTools"].append(
                copy.deepcopy(config["cliTools"][0])
            ),
            "$.cliTools[2].name",
            "duplicate tool name",
        ),
    ],
)
def test_agent_config_schema_rejects_invalid_fields(
    tmp_path,
    mutate,
    field_path,
    message,
):
    config_path = write_agent_config(tmp_path, mutate)

    with pytest.raises(ValueError) as exc_info:
        load_agent_config(config_path)

    text = str(exc_info.value)
    assert str(config_path) in text
    assert field_path in text
    assert message in text


def test_agent_builder_reports_schema_error_without_traceback(tmp_path, capsys):
    config_path = write_agent_config(
        tmp_path,
        lambda config: config["skills"][0].__setitem__("priority", 0),
    )

    class InvalidConfigAgent:
        def __init__(self):
            load_agent_config(config_path)

    assert build_agent(InvalidConfigAgent) is None
    captured = capsys.readouterr()
    assert "配置无效" in captured.err
    assert str(config_path) in captured.err
    assert "$.skills[0].priority" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("mutate", "field_path", "message"),
    [
        (
            lambda config: config.__setitem__("unexpected", True),
            "$.unexpected",
            "unknown field",
        ),
        (
            lambda config: config["flows"].append(config["flows"][0]),
            "$.flows",
            "duplicate value",
        ),
        (
            lambda config: config["aliases"].append(config["aliases"][0]),
            "$.aliases",
            "duplicate value",
        ),
    ],
)
def test_target_schema_rejects_unknown_and_duplicate_values(
    tmp_path,
    mutate,
    field_path,
    message,
):
    targets_dir = write_target_config(tmp_path, mutate)

    with pytest.raises(ValueError) as exc_info:
        load_target_registry(targets_dir)

    text = str(exc_info.value)
    assert field_path in text
    assert message in text
