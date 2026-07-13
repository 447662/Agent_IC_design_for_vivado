import gzip
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
AGENT_PATH = AGENT_DIR / "agent.py"
ENVIRONMENT_REPORT_PATH = AGENT_DIR / "environment_report.py"

if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


def load_local_module(module_name, module_path):
    module_dir = str(module_path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
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


def test_p5_10_environment_report_writes_chinese_markdown_html_and_manifest(tmp_path):
    module = load_local_module("environment_report_split_complete", ENVIRONMENT_REPORT_PATH)

    class FakeRunner:
        def run(self, command, **_kwargs):
            output = {
                "git": "git version 2.50.0",
                "vivado": "Vivado v2025.2",
                "rwave": "rwave 0.4.0",
            }.get(Path(str(command[0])).stem.lower(), "tool 1.0")
            return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    class FakeAgent:
        project_root = ROOT
        command_runner = FakeRunner()

        def resolve_vivado_command(self):
            return "vivado"

        def resolve_rwave_command(self):
            return "rwave"

        def resolve_vcd_analyzer_path(self):
            return ROOT / "VCD_ANALYZER-main" / "VCD_ANALYZER-main" / "vcd_analyzer.py"

    result = module.write_environment_report(
        FakeAgent(),
        output_dir=tmp_path,
        env={"SESSIONNAME": "Console"},
        which=lambda name: name if name == "git" else None,
        platform_system=lambda: "Windows",
        version_info=(3, 11, 9),
        python_executable="C:/Python311/python.exe",
    )

    assert result["status"] == "PASS"
    assert result["markdown_path"] == tmp_path / "environment-report" / "environment_report.md"
    assert result["html_path"] == tmp_path / "environment-report" / "environment_report.html"
    assert result["manifest_path"] == tmp_path / "environment-report" / "artifacts.json"

    markdown = result["markdown_path"].read_text(encoding="utf-8")
    html_text = result["html_path"].read_text(encoding="utf-8")
    manifest = json.loads(result["manifest_path"].read_text(encoding="utf-8"))

    assert "Python" in markdown
    assert "Git" in markdown
    assert "Vivado" in markdown
    assert "RWave" in markdown
    assert "Traceback" not in html_text
    assert manifest["scope"] == "environment"
    assert manifest["runs"][-1]["status"] == "PASS"
    assert {
        item["path"]
        for item in manifest["runs"][-1]["artifacts"]
    } == {"environment_report.md", "environment_report.html"}


def test_history_rotation_archives_environment_manifest_runs(tmp_path):
    module = load_local_module(
        "environment_report_split_rotation",
        ENVIRONMENT_REPORT_PATH,
    )
    report_dir = tmp_path / "environment-report"
    report_dir.mkdir()
    report_paths = [
        report_dir / "environment_report.md",
        report_dir / "environment_report.html",
    ]
    for path in report_paths:
        path.write_text(path.name, encoding="utf-8")

    manifest_path = report_dir / "artifacts.json"
    for index in range(4):
        module.write_environment_manifest(
            manifest_path,
            tmp_path,
            "PASS",
            "2026-07-11T00:0{}:00.000Z".format(index),
            [{"name": "sequence", "status": "PASS", "detail": index}],
            report_paths,
            max_active_runs=2,
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [
        run["checks"][0]["detail"]
        for run in manifest["runs"]
    ] == [2, 3]
    assert manifest["history"] == {
        "active_limit": 2,
        "archive_path": "artifacts.archive.jsonl.gz",
        "archived_runs": 2,
    }

    archive_path = report_dir / "artifacts.archive.jsonl.gz"
    with gzip.open(archive_path, "rt", encoding="utf-8") as stream:
        archived = [
            json.loads(line)
            for line in stream.read().splitlines()
        ]
    assert [
        run["checks"][0]["detail"]
        for run in archived
    ] == [0, 1]


def test_p5_10_environment_report_warns_for_missing_optional_tools(tmp_path):
    module = load_local_module("environment_report_split_missing_tools", ENVIRONMENT_REPORT_PATH)

    class FakeRunner:
        def run(self, command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="git version 2.50.0",
                stderr="",
            )

    class FakeAgent:
        project_root = ROOT
        command_runner = FakeRunner()

        def resolve_vivado_command(self):
            return None

        def resolve_rwave_command(self):
            return None

        def resolve_vcd_analyzer_path(self):
            return tmp_path / "missing-vcd-analyzer.py"

    result = module.write_environment_report(
        FakeAgent(),
        output_dir=tmp_path,
        env={},
        which=lambda name: "git" if name == "git" else None,
        platform_system=lambda: "Windows",
        version_info=(3, 11, 9),
        python_executable="C:/Python311/python.exe",
    )

    assert result["status"] == "WARN"
    markdown = result["markdown_path"].read_text(encoding="utf-8")
    assert "| Vivado | WARN |" in markdown
    assert "| RWave / VCD_ANALYZER | WARN |" in markdown


def test_p5_10_environment_report_accepts_vivado_version_banner_on_nonzero_exit():
    module = load_local_module(
        "environment_report_split_vivado_banner",
        ENVIRONMENT_REPORT_PATH,
    )

    class FakeRunner:
        def run(self, command, **_kwargs):
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="Vivado v2025.2 (64-bit) SW Build 6299465",
                stderr="",
            )

    class FakeAgent:
        command_runner = FakeRunner()

        def resolve_vivado_command(self):
            return r"D:\vivado\2025.2\Vivado\bin\vivado.bat"

    check = module._check_vivado(FakeAgent())

    assert check["status"] == "PASS"
    assert "Vivado v2025.2" in check["detail"]


def test_p5_10_environment_report_rejects_unwritable_output_path(tmp_path):
    module = load_local_module("environment_report_split_unwritable", ENVIRONMENT_REPORT_PATH)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("blocked", encoding="utf-8")

    class FakeAgent:
        project_root = ROOT
        command_runner = None

    with pytest.raises(OSError):
        module.write_environment_report(FakeAgent(), output_dir=output_file)


def test_p5_10_cli_reports_output_failure_without_traceback(tmp_path):
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("blocked", encoding="utf-8")

    result = run_agent(
        "--environment-report",
        "--output-dir",
        str(output_file),
    )

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
