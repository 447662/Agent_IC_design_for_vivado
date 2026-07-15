from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "digital-ic-design"
SKILL_PATH = SKILL_DIR / "SKILL.md"
OPENAI_PATH = SKILL_DIR / "agents" / "openai.yaml"


def test_codex_skill_is_discoverable_and_defines_complete_closed_loop() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert skill.startswith("---\nname: digital-ic-design\n")
    assert "description:" in skill.split("---", maxsplit=2)[1]
    for required_step in (
        "DesignIntent",
        "VerificationIntent",
        "reference status",
        "workspace init",
        "spec validate",
        "verify",
        "diagnose",
        "resume",
        "coverage",
        "停止条件",
    ):
        assert required_step in skill
    assert "不得调用任何 LLM API" in skill


def test_codex_skill_contains_exact_once_per_task_reference_reminder() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    reminder = (
        "即将检索本地数字 IC 参考库。后续可将 RTL 或项目压缩包放入 "
        "references/inbox/rtl，将 UVM/SVA/验证代码放入 references/inbox/uvm，"
        "将论文放入 references/inbox/papers，将协议和芯片资料放入 "
        "references/inbox/specs，并将对应 LICENSE/NOTICE 放入 "
        "references/inbox/licenses。"
    )

    assert skill.count(reminder) == 1
    assert "每个设计任务只提醒一次" in skill


def test_codex_skill_openai_interface_is_explicit() -> None:
    interface = OPENAI_PATH.read_text(encoding="utf-8")

    assert 'display_name: "Digital IC Design"' in interface
    assert 'short_description: "' in interface
    assert "$digital-ic-design" in interface
    assert "allow_implicit_invocation: true" in interface
