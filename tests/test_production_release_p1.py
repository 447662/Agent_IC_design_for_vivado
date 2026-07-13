from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tomllib
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "src" / "digital_ic_agent" / "_runtime"
QUALITY_GENERATOR = ROOT / "scripts" / "generate_quality_summary.py"
RISK_COVERAGE_GATE = ROOT / "scripts" / "check_risk_coverage.py"
PYPROJECT = ROOT / "pyproject.toml"
QUALITY_WORKFLOW = ROOT / ".github" / "workflows" / "python-quality.yml"
VIVADO_WORKFLOW = ROOT / ".github" / "workflows" / "vivado-integration.yml"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_quality_provenance_is_validated_and_rendered():
    generator = _load_module("p1_quality_provenance", QUALITY_GENERATOR)
    provenance = generator.validate_provenance(
        source="ci",
        commit_sha="a" * 40,
        generated_at="2026-07-14T10:11:12Z",
        run_id="12345",
        run_url="https://github.com/447662/Agent_IC_design_for_vivado/actions/runs/12345",
    )

    summary = generator.build_quality_summary(
        {"tests": 12, "failures": 0, "errors": 0, "skipped": 0, "time": 1.0},
        {"line_rate": 0.91, "branch_rate": 0.82},
        60,
        {"failure_handling": 2},
        provenance=provenance,
    )

    assert provenance == {
        "source": "ci",
        "commit_sha": "a" * 40,
        "generated_at": "2026-07-14T10:11:12Z",
        "run_id": "12345",
        "run_url": "https://github.com/447662/Agent_IC_design_for_vivado/actions/runs/12345",
    }
    for field, value in provenance.items():
        assert f"| {field} | {value} |" in summary
    assert "CI full quality artifact" not in summary


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"source": "unknown"}, "source"),
        ({"commit_sha": "short"}, "commit_sha"),
        ({"generated_at": "2026-07-14"}, "generated_at"),
        ({"run_id": "", "run_url": ""}, "CI provenance"),
        ({"run_id": "123", "run_url": "https://example.test/run/456"}, "run_url"),
    ],
)
def test_quality_provenance_rejects_untraceable_ci_evidence(overrides, message):
    generator = _load_module("p1_quality_provenance_invalid", QUALITY_GENERATOR)
    values = {
        "source": "ci",
        "commit_sha": "b" * 40,
        "generated_at": "2026-07-14T10:11:12Z",
        "run_id": "123",
        "run_url": "https://github.com/example/project/actions/runs/123",
    }
    values.update(overrides)

    with pytest.raises(ValueError, match=message):
        generator.validate_provenance(**values)


def test_quality_outputs_include_machine_readable_provenance(tmp_path):
    generator = _load_module("p1_quality_provenance_output", QUALITY_GENERATOR)
    provenance = generator.validate_provenance(
        source="local",
        commit_sha="c" * 40,
        generated_at="2026-07-14T10:11:12Z",
        run_id="",
        run_url="",
    )

    generator.write_outputs(tmp_path, "# summary\n", "# matrix\n", provenance)

    assert json.loads((tmp_path / "quality_provenance.json").read_text(encoding="utf-8")) == provenance


def test_ci_generates_commit_bound_quality_artifacts_outside_tracked_docs():
    workflow = QUALITY_WORKFLOW.read_text(encoding="utf-8")

    assert '--source ci' in workflow
    assert '--commit-sha "${{ github.sha }}"' in workflow
    assert '--run-id "${{ github.run_id }}"' in workflow
    assert "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}" in workflow
    assert "--output-dir .tmp/generated-quality" in workflow
    assert "test -s .tmp/generated-quality/quality_provenance.json" in workflow
    assert "docs/generated" not in workflow
    assert "--write-readme" not in workflow


def test_risk_coverage_gate_has_elevated_module_thresholds(tmp_path):
    gate = _load_module("p1_risk_coverage", RISK_COVERAGE_GATE)
    expected = {
        "_runtime/agent_provider.py": {"line": 0.85, "branch": 0.75},
        "_runtime/mcp_client.py": {"line": 0.93, "branch": 0.87},
        "_runtime/plugin_guard_runner.py": {"line": 0.87, "branch": 0.78},
        "_runtime/agent_execution.py": {"line": 0.94, "branch": 0.90},
        "_runtime/agent_cli_dispatch.py": {"line": 0.82, "branch": 0.75},
        "_runtime/agent_async_fifo_flows.py": {"line": 0.70, "branch": 0.80},
    }
    assert expected == gate.RISK_MODULE_THRESHOLDS

    classes = "\n".join(
        '<class name="{name}" filename="{name}" line-rate="1" branch-rate="1"/>'.format(
            name=name
        )
        for name in expected
    )
    coverage_xml = tmp_path / "coverage.xml"
    coverage_xml.write_text(
        '<coverage><packages><package><classes>{}</classes></package></packages></coverage>'.format(
            classes
        ),
        encoding="utf-8",
    )
    assert gate.find_coverage_violations(coverage_xml) == []

    coverage_xml.write_text(
        '<coverage><packages><package><classes>'
        '<class name="agent_provider.py" filename="_runtime/agent_provider.py" '
        'line-rate="0.84" branch-rate="0.74"/>'
        '</classes></package></packages></coverage>',
        encoding="utf-8",
    )
    violations = gate.find_coverage_violations(coverage_xml)
    assert any("agent_provider.py line coverage" in item for item in violations)
    assert any("agent_provider.py branch coverage" in item for item in violations)
    assert any("missing coverage data" in item for item in violations)


def test_ci_supports_python_312_and_pins_uv_tool_version():
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    quality = QUALITY_WORKFLOW.read_text(encoding="utf-8")
    vivado = VIVADO_WORKFLOW.read_text(encoding="utf-8")

    assert config["project"]["requires-python"] == ">=3.11,<3.14"
    assert 'python-version: ["3.11", "3.12", "3.13"]' in quality
    for workflow in (quality, vivado):
        assert 'version: "0.11.26"' in workflow
    assert "scripts/check_risk_coverage.py --coverage-xml coverage.xml" in quality


def test_provider_rejects_invalid_plans_and_skill_selections(tmp_path):
    from digital_ic_agent._runtime.agent_contracts import AgentRequest, ExecutionPlan
    from digital_ic_agent._runtime.agent_provider import (
        ConfiguredAgentProvider,
        DeterministicProvider,
    )

    request = AgentRequest("request", "rtl", tmp_path)
    invalid_plans = (
        object(),
        ExecutionPlan("", "skill"),
        ExecutionPlan("plan", ""),
    )
    for plan in invalid_plans:
        provider = DeterministicProvider(lambda _request, value=plan: value)  # type: ignore[arg-type]
        with pytest.raises((TypeError, ValueError)):
            provider.create_plan(request)

    skills = ({"name": "rtl", "action": "generate"},)
    provider = ConfiguredAgentProvider(skills)
    invalid_contexts = (
        {"selected_skills": "rtl"},
        {"selected_skills": [1]},
        {"selected_skills": ["missing"]},
        {"selected_skills": ["rtl", "rtl"]},
    )
    for context in invalid_contexts:
        with pytest.raises(ValueError):
            provider.create_plan(AgentRequest("request", "rtl", tmp_path, context))
    with pytest.raises(ValueError, match="request_id"):
        provider.create_plan(AgentRequest("", "rtl", tmp_path, {"selected_skills": ["rtl"]}))


def test_mcp_boundary_branches_reject_invalid_limits_and_protocol_data(monkeypatch):
    from digital_ic_agent._runtime.mcp_client import MCPProtocolError, StdioMCPClient

    with pytest.raises(ValueError, match="max_message_bytes"):
        StdioMCPClient(("server",), max_message_bytes=0)

    client = StdioMCPClient(("server",), max_message_bytes=4)
    client._process = SimpleNamespace(stdout=iter(("oversized\n",)), stderr=None)
    client._read_stdout()
    with pytest.raises(MCPProtocolError, match="message size limit"):
        client._wait_for_response(1, "initialize", float("inf"))

    invalid = StdioMCPClient(("server",))
    monkeypatch.setattr(invalid, "_request", lambda *_args: {"protocolVersion": ""})
    with pytest.raises(MCPProtocolError, match="protocolVersion"):
        invalid.initialize()


def test_plugin_guard_covers_allowed_and_denied_read_boundaries(tmp_path, capsys):
    from digital_ic_agent._runtime import plugin_guard_runner

    output_root = tmp_path / "outputs"
    allowed_file = tmp_path / "plugin.py"
    output_root.mkdir()
    allowed_file.write_text("# plugin\n", encoding="utf-8")
    context = plugin_guard_runner.GuardContext(
        output_root=output_root.resolve(),
        allowed_reads=frozenset({allowed_file.resolve()}),
        stdlib_roots=(),
    )

    plugin_guard_runner.guard_path(context, allowed_file, "r")
    plugin_guard_runner.guard_path(context, output_root / "artifact.txt", "r")
    with pytest.raises(SystemExit) as denied:
        plugin_guard_runner.guard_path(context, tmp_path / "secret.txt", "r")
    assert denied.value.code == 13
    assert json.loads(capsys.readouterr().out)["event"]["reason"] == "read_outside_allowed_root"


def test_execution_engine_covers_unregistered_mismatched_and_empty_evidence_names(tmp_path):
    from digital_ic_agent._runtime.agent_contracts import (
        AgentRequest,
        AgentRunStatus,
        ExecutionPlan,
        ToolCall,
        ToolResult,
        ToolResultStatus,
    )
    from digital_ic_agent._runtime.agent_execution import AgentExecutionEngine, MCPToolExecutor
    from digital_ic_agent._runtime.agent_provider import DeterministicProvider

    request = AgentRequest("request", "rtl", tmp_path)
    call = ToolCall("call", "missing")
    provider = DeterministicProvider(lambda _request: ExecutionPlan("plan", "skill", (call,)))
    unregistered = AgentExecutionEngine(provider, {}).run(request)
    assert unregistered.status is AgentRunStatus.FAILED
    assert unregistered.tool_results[0].returncode == 127

    mismatch = ToolResult("call", "different", ToolResultStatus.SUCCEEDED, 0)
    mismatched = AgentExecutionEngine(
        provider,
        {"missing": lambda *_args: mismatch},
    ).run(request)
    assert "tool_name" in str(mismatched.failure_reason)

    evidence_call = ToolCall("!!!", "echo")
    evidence_provider = DeterministicProvider(
        lambda _request: ExecutionPlan("plan", "skill", (evidence_call,))
    )

    class Client:
        @staticmethod
        def call_tool(_name, _arguments):
            return {"content": [{"type": "text", "text": "ok"}], "isError": False}

    evidence_run = AgentExecutionEngine(
        evidence_provider,
        {"echo": MCPToolExecutor(Client())},
    ).run(request)
    assert evidence_run.status is AgentRunStatus.SUCCEEDED
    assert evidence_run.artifacts[0].name == "mcp-tool-result.json"


def test_cli_dispatch_covers_operational_command_branches(tmp_path):
    from digital_ic_agent._runtime.agent_cli import parse_args
    from digital_ic_agent._runtime.agent_cli_dispatch import dispatch_cli_command

    calls: list[str] = []

    class Agent:
        def list_skills(self):
            calls.append("list-skills")

        def print_targets(self):
            calls.append("list-targets")

        def run_diagnostic(self):
            calls.append("diagnostic")
            return True

        def run_smoke_loop(self, **_kwargs):
            calls.append("smoke-loop")
            return True

        def create_target_scaffold(self, *_args, **_kwargs):
            calls.append("create-target")
            return {
                "project_dir": tmp_path / "target",
                "config_path": tmp_path / "target" / "target.json",
                "todo_path": tmp_path / "target" / "TODO.md",
            }

    agent = Agent()
    for option in ("--list-skills", "--list-targets", "--diagnostic", "--smoke-loop"):
        assert dispatch_cli_command(parse_args([option]), agent) == 0
    assert dispatch_cli_command(parse_args(["--create-target", "demo"]), agent) == 0

    assert calls == [
        "list-skills",
        "list-targets",
        "diagnostic",
        "smoke-loop",
        "create-target",
    ]


def test_async_fifo_flows_cover_regression_gui_and_uvm_launch_failures(tmp_path):
    from digital_ic_agent._runtime.agent_async_fifo_flows import AsyncFifoFlowMixin

    class RegressionFlow(AsyncFifoFlowMixin):
        def __init__(self):
            self.opened = []

        def write_async_fifo_project(self, output_dir):
            return Path(output_dir) / "async-fifo"

        def write_async_fifo_regression_matrix(self, _project_dir):
            return None

        def async_fifo_regression_cases(self):
            return ({"name": "base", "data_width": 8, "addr_width": 4},)

        def run_async_fifo_vivado_sim(self, **_kwargs):
            return True

        def write_async_fifo_regression_summary(self, _project_dir, _results):
            return None

        def open_async_fifo_project_gui(self, project_dir):
            self.opened.append(project_dir)

    regression = RegressionFlow()
    assert regression.run_async_fifo_regression(tmp_path, open_wave_gui=True) is True
    assert regression.opened == [tmp_path / "async-fifo"]

    class UvmSmokeFlow(AsyncFifoFlowMixin):
        def __init__(self, command, returncode=1):
            self.command = command
            self.returncode = returncode

        def generate_rtl_project(self, _target, output_dir, **_kwargs):
            project = Path(output_dir) / "async-fifo"
            (project / "sim").mkdir(parents=True)
            return project

        def write_async_fifo_uvm_smoke_project(self, *_args, **_kwargs):
            return None

        def resolve_vivado_command(self):
            return self.command

        def run_vivado_batch(self, *_args, **_kwargs):
            return subprocess.CompletedProcess(
                [],
                self.returncode,
                stdout="",
                stderr="uvm failed",
            )

        def write_async_fifo_uvm_smoke_report(self, *_args, **_kwargs):
            return {"passed": False}

    assert UvmSmokeFlow(None).run_async_fifo_uvm_smoke(tmp_path / "missing") is False
    assert UvmSmokeFlow("vivado").run_async_fifo_uvm_smoke(tmp_path / "failed") is False
    assert UvmSmokeFlow("vivado", 0).run_async_fifo_uvm_smoke(tmp_path / "markers") is False
