import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_agent_module():
    spec = importlib.util.spec_from_file_location(
        "digital_ic_agent_target_report_rendering_split",
        AGENT_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run_agent(*args):
    return subprocess.run(
        [sys.executable, str(AGENT_PATH), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_p5_4_generate_design_spec_from_round_robin_target_config(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    report = agent.write_target_design_spec(
        "round-robin-arbiter",
        output_dir=tmp_path,
        requirement="生成一个 4 requester round-robin arbiter，用于通用数字 IC Agent 规格文档验证。",
    )

    md_path = tmp_path / "round-robin-arbiter" / "reports" / "design_spec.md"
    html_path = tmp_path / "round-robin-arbiter" / "reports" / "design_spec.html"
    assert report["md_path"] == md_path
    assert report["html_path"] == html_path
    assert md_path.exists()
    assert html_path.exists()

    text = md_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    assert "# 设计规格" in text
    assert "round-robin-arbiter" in text
    assert "Round-Robin Arbiter" in text
    assert "arbiter" in text
    assert "req[3:0]" in text
    assert "grant[3:0]" in text
    assert "grant_valid" in text
    assert "single_request" in text
    assert "one-hot grant" in text
    assert '<html lang="zh-CN">' in html_text
    assert 'class="doc-card"' in html_text


def test_p5_4_cli_generate_spec_creates_markdown_and_html(tmp_path):
    result = run_agent(
        "--generate-spec",
        "round-robin-arbiter",
        "--output-dir",
        str(tmp_path),
        "生成一个 4 requester round-robin arbiter",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "design_spec.md" in result.stdout
    assert (tmp_path / "round-robin-arbiter" / "reports" / "design_spec.md").exists()
    assert (tmp_path / "round-robin-arbiter" / "reports" / "design_spec.html").exists()


def test_p5_5_generate_verification_plan_from_scenario_catalog(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    report = agent.write_target_verification_plan(
        "round-robin-arbiter",
        output_dir=tmp_path,
    )

    md_path = tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.md"
    html_path = tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.html"
    assert report["md_path"] == md_path
    assert report["html_path"] == html_path
    assert md_path.exists()
    assert html_path.exists()

    text = md_path.read_text(encoding="utf-8")
    html_text = html_path.read_text(encoding="utf-8")
    assert "# 验证计划" in text
    assert "scenario catalog" in text
    assert "single_request" in text
    assert "multiple_requests" in text
    assert "rotating_grant" in text
    assert "reset_recovery" in text
    assert "fairness_window" in text
    assert "one-hot" in text
    assert "grant implies request" in text
    assert '<html lang="zh-CN">' in html_text
    assert 'class="scenario-card"' in html_text


def test_p5_5_cli_generate_verification_plan_creates_markdown_and_html(tmp_path):
    result = run_agent(
        "--generate-verification-plan",
        "round-robin-arbiter",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "verification_plan.md" in result.stdout
    assert (
        tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.md"
    ).exists()
    assert (
        tmp_path / "round-robin-arbiter" / "reports" / "verification_plan.html"
    ).exists()


def test_p5_4_p5_5_sync_fifo_spec_and_plan_are_target_generic(tmp_path):
    module = load_agent_module()
    agent = module.DigitalICAgent()

    spec_report = agent.write_target_design_spec("sync_fifo", output_dir=tmp_path)
    plan_report = agent.write_target_verification_plan("sync_fifo", output_dir=tmp_path)

    spec_text = spec_report["md_path"].read_text(encoding="utf-8")
    plan_text = plan_report["md_path"].read_text(encoding="utf-8")
    assert "sync-fifo" in spec_text
    assert "Synchronous FIFO" in spec_text
    assert "clk" in spec_text
    assert "wr_en" in spec_text
    assert "rd_en" in spec_text
    assert "basic_ordered" in plan_text
    assert "full_boundary" in plan_text
    assert "empty_boundary" in plan_text
