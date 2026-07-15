from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_root_readme_is_a_stable_user_entrypoint():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for heading in (
        "## 安装",
        "## 快速开始",
        "## 能力矩阵",
        "## Vivado 要求",
        "## 常用流程",
        "## 质量证据",
        "## 故障排查",
    ):
        assert heading in readme
    assert not re.search(r"^## P\d", readme, flags=re.MULTILINE)
    assert "tests/test_agent.py" not in readme
    assert "uv sync --frozen --group dev" in readme
    assert "uv run digital-ic-agent --diagnostic" in readme
    assert "uv run digital-ic-agent --generate-rtl async-fifo" in readme


def test_readmes_document_current_vivado_and_async_fifo_flow():
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    agent_readme = (ROOT / ".trae" / "agent" / "README.md").read_text(encoding="utf-8")
    lessons = (ROOT / "docs" / "vivado_async_fifo_lessons_learned.md").read_text(encoding="utf-8")
    combined = root_readme + "\n" + agent_readme + "\n" + lessons

    assert "--sim-smoke" in combined
    assert "--no-wave-gui" in combined
    assert "--generate-rtl async-fifo" in combined
    assert "--sim-rtl async-fifo" in combined
    assert "--analyze-rtl-vcd async-fifo" in combined
    assert "--check-rtl async-fifo" in combined
    assert "--open-wave async-fifo" in combined
    assert "--regress-rtl async-fifo" in combined
    assert "handshake_smoke.wdb" in combined
    assert "async_fifo.v" in combined
    assert "async_fifo_smoke.wdb" in combined
    assert "create_async_fifo_project.tcl" in combined
    assert "open_async_fifo_project_gui.tcl" in combined
    assert "regression_summary.html" in combined
    assert "wave_visibility.html" in combined
    assert "wave_screenshot.html" in combined
    assert "reports/index.html" in combined
    assert "P2.9" in combined
    assert "P2.10" in combined
    assert "P2.11" in combined
    assert "P2.12" in combined
