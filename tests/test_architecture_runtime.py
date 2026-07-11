import ast
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
TARGETS_DIR = AGENT_DIR / "targets"
TARGET_FLOWS_PATH = AGENT_DIR / "target_flows.py"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


import agent as agent_module  # noqa: E402
from agent_runtime import (  # noqa: E402
    CommandRunner,
    PluginServices,
    TargetPlugin,
)
from capability_preflight import FlowPreflight, PreflightStatus  # noqa: E402
from skill_runtime import (  # noqa: E402
    DeterministicSkillExecutor,
    SkillExecutionRequest,
    SkillExecutionResult,
    SkillExecutionStatus,
    SkillLoader,
    SkillResultValidator,
    ToolRunRecord,
)
from target_plugins import (  # noqa: E402
    TargetHandlerRegistry,
    build_target_handlers,
    discover_target_handler_plugins,
    load_target_handler_plugins,
)
from target_examples.async_fifo import ASYNC_FIFO_SERVICE_NAMES  # noqa: E402


def _write_skill(root: Path, name: str, title: str) -> dict[str, object]:
    skill_path = root / "skills" / name / "SKILL.md"
    skill_path.parent.mkdir(parents=True)
    skill_path.write_text(
        "# {}\n\n## Contract\n\nExecute the declared action.\n".format(title),
        encoding="utf-8",
    )
    return {
        "name": name,
        "path": "./skills/{}/SKILL.md".format(name),
        "description": title,
        "action": name,
        "requiredCapabilities": [],
    }


def test_skill_loader_reads_markdown_and_executor_dispatches_distinct_actions(tmp_path):
    design_config = _write_skill(tmp_path, "design-document", "Design Skill")
    rtl_config = _write_skill(tmp_path, "rtl-implementation", "RTL Skill")
    loader = SkillLoader(tmp_path)

    design_skill = loader.load(design_config)
    rtl_skill = loader.load(rtl_config)

    assert design_skill.title == "Design Skill"
    assert "Execute the declared action." in design_skill.content
    assert rtl_skill.action == "rtl-implementation"

    calls = []

    def execute_design(request):
        calls.append(("design", request.skill.name))
        design_spec = request.output_dir / "design_spec.md"
        design_spec.write_text(
            "# Design Specification\n\n## Requirements\n\nValidated input.\n",
            encoding="utf-8",
        )
        return SkillExecutionResult(
            skill_name=request.skill.name,
            action=request.skill.action,
            status=SkillExecutionStatus.SUCCEEDED,
            artifacts=(design_spec,),
            message="design complete",
        )

    def execute_rtl(request):
        calls.append(("rtl", request.skill.name))
        return SkillExecutionResult(
            skill_name=request.skill.name,
            action=request.skill.action,
            status=SkillExecutionStatus.BLOCKED,
            message="rtl generation is unavailable",
            failure_reason="no RTL generator configured",
        )

    executor = DeterministicSkillExecutor(
        {
            "design-document": execute_design,
            "rtl-implementation": execute_rtl,
        }
    )
    design_result = executor.execute(
        SkillExecutionRequest(
            skill=design_skill,
            user_input="write a design",
            output_dir=tmp_path,
        )
    )
    rtl_result = executor.execute(
        SkillExecutionRequest(
            skill=rtl_skill,
            user_input="write rtl",
            output_dir=tmp_path,
        )
    )

    assert calls == [
        ("design", "design-document"),
        ("rtl", "rtl-implementation"),
    ]
    assert design_result.artifacts[0].name == "design_spec.md"
    assert design_result.validated_artifacts == design_result.artifacts
    assert rtl_result.status is SkillExecutionStatus.BLOCKED


def test_executor_rejects_succeeded_result_with_missing_artifacts(tmp_path):
    config = _write_skill(tmp_path, "design-document", "Design Skill")
    skill = SkillLoader(tmp_path).load(config)

    executor = DeterministicSkillExecutor(
        {
            "design-document": lambda request: SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(request.output_dir / "missing-design-spec.md",),
                message="incorrect success",
            )
        }
    )

    with pytest.raises(ValueError, match="missing artifact"):
        executor.execute(
            SkillExecutionRequest(
                skill=skill,
                user_input="write a design",
                output_dir=tmp_path,
            )
        )


def test_executor_requires_rtl_testbench_and_successful_check_for_rtl_success(tmp_path):
    config = _write_skill(tmp_path, "rtl-implementation", "RTL Skill")
    skill = SkillLoader(tmp_path).load(config)
    rtl_path = tmp_path / "rtl" / "demo.v"
    rtl_path.parent.mkdir()
    rtl_path.write_text("module demo; endmodule\n", encoding="utf-8")

    executor = DeterministicSkillExecutor(
        {
            "rtl-implementation": lambda request: SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(rtl_path,),
                tool_runs=(
                    ToolRunRecord(
                        name="rtl-check",
                        status=SkillExecutionStatus.SUCCEEDED,
                        returncode=0,
                    ),
                ),
                message="incomplete rtl result",
            )
        }
    )

    with pytest.raises(ValueError, match="testbench"):
        executor.execute(
            SkillExecutionRequest(
                skill=skill,
                user_input="write rtl",
                output_dir=tmp_path,
            )
        )


def test_skill_validator_rejects_none_returncode_for_rtl_success(tmp_path):
    config = _write_skill(tmp_path, "rtl-implementation", "RTL Skill")
    skill = SkillLoader(tmp_path).load(config)
    rtl_path = tmp_path / "rtl" / "demo.v"
    tb_path = tmp_path / "tb" / "tb_demo.v"
    rtl_path.parent.mkdir()
    tb_path.parent.mkdir()
    rtl_path.write_text("module demo; endmodule\n", encoding="utf-8")
    tb_path.write_text("module tb_demo; demo dut(); endmodule\n", encoding="utf-8")

    with pytest.raises(ValueError, match="successful RTL check"):
        SkillResultValidator().validate(
            SkillExecutionRequest(
                skill=skill,
                user_input="write rtl",
                output_dir=tmp_path,
            ),
            SkillExecutionResult(
                skill_name=skill.name,
                action=skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(rtl_path, tb_path),
                tool_runs=(
                    ToolRunRecord(
                        name="rtl-check",
                        status=SkillExecutionStatus.SUCCEEDED,
                        returncode=None,
                    ),
                ),
                message="incorrect success",
            ),
        )


def test_skill_loader_rejects_missing_empty_and_actionless_skills(tmp_path):
    loader = SkillLoader(tmp_path)

    with pytest.raises(FileNotFoundError, match="Skill file not found"):
        loader.load(
            {
                "name": "missing",
                "path": "./skills/missing/SKILL.md",
                "description": "missing",
                "action": "design-document",
            }
        )

    empty_path = tmp_path / "skills" / "empty" / "SKILL.md"
    empty_path.parent.mkdir(parents=True)
    empty_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="Skill file is empty"):
        loader.load(
            {
                "name": "empty",
                "path": "./skills/empty/SKILL.md",
                "description": "empty",
                "action": "design-document",
            }
        )

    valid_path = tmp_path / "skills" / "actionless" / "SKILL.md"
    valid_path.parent.mkdir(parents=True)
    valid_path.write_text("# Actionless\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing action"):
        loader.load(
            {
                "name": "actionless",
                "path": "./skills/actionless/SKILL.md",
                "description": "actionless",
            }
        )


def test_flow_preflight_is_capability_aware():
    preflight = FlowPreflight(
        {
            "design-document": {"required": (), "optional": ()},
            "sim-rtl": {
                "required": ("vivado",),
                "optional": ("synthpilot",),
            },
        }
    )

    document_report = preflight.evaluate("design-document", lambda _name: False)
    simulation_report = preflight.evaluate("sim-rtl", lambda _name: False)

    assert document_report.ok is True
    assert document_report.status_for("vivado") is PreflightStatus.NOT_APPLICABLE
    assert simulation_report.ok is False
    assert simulation_report.status_for("vivado") is PreflightStatus.MISSING_REQUIRED
    assert simulation_report.status_for("synthpilot") is PreflightStatus.MISSING_OPTIONAL

    with pytest.raises(ValueError, match="Unknown flow"):
        preflight.evaluate("unknown-flow", lambda _name: True)


def _write_plugin_package(
    root: Path,
    package_name: str,
    modules: dict[str, tuple[str, tuple[str, ...]]],
) -> None:
    package_dir = root / package_name
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    for module_name, (handler_id, flows) in modules.items():
        flow_items = ", ".join(
            '"{}": (lambda **_kwargs: "{}")'.format(flow, flow)
            for flow in flows
        )
        (package_dir / "{}.py".format(module_name)).write_text(
            "\n".join(
                [
                    "from agent_runtime import TargetHandler",
                    "",
                    'HANDLER_ID = "{}"'.format(handler_id),
                    "",
                    "def create_handler(agent, target):",
                    "    return TargetHandler(target['name'], {{{}}})".format(flow_items),
                    "",
                ]
            ),
            encoding="utf-8",
        )


def test_target_plugins_auto_discover_without_central_mapping(tmp_path):
    _write_plugin_package(
        tmp_path,
        "demo_target_plugins",
        {"sample": ("sample-handler", ("generate-rtl",))},
    )
    registry = TargetHandlerRegistry()
    discover_target_handler_plugins(
        registry,
        "demo_target_plugins",
        search_path=tmp_path,
    )
    targets = {
        "sample-target": {
            "name": "sample-target",
            "handler": "sample-handler",
            "aliases": [],
            "flows": ["generate-rtl"],
        }
    }

    handlers = build_target_handlers(object(), targets, registry)

    assert set(handlers) == {"sample-target"}
    assert handlers["sample-target"].run("generate-rtl") == "generate-rtl"


def test_target_plugin_discovery_failure_does_not_partially_register_handlers(tmp_path):
    _write_plugin_package(
        tmp_path,
        "partial_target_plugins",
        {
            "first": ("first-handler", ("generate-rtl",)),
            "second": ("first-handler", ("generate-rtl",)),
        },
    )
    registry = TargetHandlerRegistry()

    with pytest.raises(ValueError, match="Duplicate target handler"):
        discover_target_handler_plugins(
            registry,
            "partial_target_plugins",
            search_path=tmp_path,
        )

    assert registry.ids() == ()


def test_target_plugins_reject_duplicate_unknown_and_mismatched_handlers(tmp_path):
    _write_plugin_package(
        tmp_path,
        "duplicate_target_plugins",
        {
            "first": ("duplicate", ("generate-rtl",)),
            "second": ("duplicate", ("generate-rtl",)),
        },
    )
    with pytest.raises(ValueError, match="Duplicate target handler"):
        discover_target_handler_plugins(
            TargetHandlerRegistry(),
            "duplicate_target_plugins",
            search_path=tmp_path,
        )

    registry = TargetHandlerRegistry()
    with pytest.raises(ValueError, match="Unknown target handler"):
        build_target_handlers(
            object(),
            {
                "unknown-target": {
                    "name": "unknown-target",
                    "handler": "missing-handler",
                    "aliases": [],
                    "flows": ["generate-rtl"],
                }
            },
            registry,
        )

    _write_plugin_package(
        tmp_path,
        "mismatched_target_plugins",
        {"sample": ("mismatch", ("generate-rtl", "sim-rtl"))},
    )
    discover_target_handler_plugins(
        registry,
        "mismatched_target_plugins",
        search_path=tmp_path,
    )
    with pytest.raises(ValueError, match="flow mismatch"):
        build_target_handlers(
            object(),
            {
                "mismatch-target": {
                    "name": "mismatch-target",
                    "handler": "mismatch",
                    "aliases": [],
                    "flows": ["generate-rtl"],
                }
            },
            registry,
        )


def test_builtin_target_handlers_use_explicit_module_whitelist():
    target_configs = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(TARGETS_DIR.glob("*.json"))
    ]
    assert target_configs
    assert all(config.get("handler") for config in target_configs)

    from target_flows import BUILTIN_HANDLER_MODULES

    assert BUILTIN_HANDLER_MODULES == (
        "target_handlers.async_fifo",
        "target_handlers.round_robin_arbiter",
        "target_handlers.sync_fifo",
    )
    registry = load_target_handler_plugins(
        TargetHandlerRegistry(),
        BUILTIN_HANDLER_MODULES,
    )
    assert set(registry.ids()) == {
        "async-fifo",
        "round-robin-arbiter",
        "sync-fifo",
    }

    from agent import DigitalICAgent

    agent = DigitalICAgent()
    assert set(agent.target_handlers) == {
        config["name"] for config in target_configs
    }


def test_core_targets_build_without_async_fifo_plugin(tmp_path):
    from target_flows import build_plugin_services

    agent = agent_module.DigitalICAgent()
    registry = load_target_handler_plugins(
        TargetHandlerRegistry(),
        (
            "target_handlers.round_robin_arbiter",
            "target_handlers.sync_fifo",
        ),
    )
    targets = {
        name: agent.targets[name]
        for name in ("round-robin-arbiter", "sync-fifo")
    }

    handlers = build_target_handlers(
        build_plugin_services(agent),
        targets,
        registry,
    )

    assert set(handlers) == {"round-robin-arbiter", "sync-fifo"}
    assert handlers["sync-fifo"].run(
        "generate-rtl",
        output_dir=tmp_path,
    ).is_dir()
    assert handlers["round-robin-arbiter"].run(
        "generate-rtl",
        output_dir=tmp_path,
    ).is_dir()
    assert "async-fifo" not in handlers


def test_plugin_services_expose_only_explicit_operations():
    services = PluginServices(
        command_runner=CommandRunner(),
        project_root=ROOT,
        operations={"sample_action": lambda: "first"},
    )

    assert services.call("sample_action") == "first"
    assert not hasattr(services, "agent")

    with pytest.raises(ValueError, match="Plugin service is not available"):
        services.call("undeclared_action")


def test_async_fifo_example_is_installed_by_plugin_not_core_agent_mixin():
    source = (AGENT_DIR / "agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    agent_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DigitalICAgent"
    )
    base_names = {
        base.id
        for base in agent_class.bases
        if isinstance(base, ast.Name)
    }

    assert not any(name.startswith("agent_async_fifo") for name in imported_modules)
    assert not any(name.startswith("AsyncFifo") for name in base_names)

    agent = agent_module.DigitalICAgent()
    handler = agent.target_handlers["async-fifo"]
    plugin = handler.plugin

    assert handler.target_name == "async-fifo"
    assert callable(handler.run)
    assert "write_async_fifo_project" in handler.extension_methods
    assert isinstance(plugin, TargetPlugin)
    assert agent.target_plugins["async-fifo"] is plugin
    assert isinstance(plugin.services, PluginServices)
    assert not hasattr(plugin.services, "agent")
    assert not hasattr(agent, "write_async_fifo_project")
    assert "write_async_fifo_project" not in plugin.services.operations
    assert set(plugin.services.operations) == set(ASYNC_FIFO_SERVICE_NAMES)
    assert not any(
        getattr(operation, "__self__", None) is agent
        for operation in plugin.services.operations.values()
    )


def test_target_registry_rejects_alias_collisions_between_targets(tmp_path):
    from target_registry import load_target_registry

    source = json.loads(
        (TARGETS_DIR / "sync_fifo.json").read_text(encoding="utf-8")
    )
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()
    for target_name in ("first-target", "second-target"):
        config = dict(source)
        config["name"] = target_name
        config["display_name"] = target_name
        config["handler"] = target_name
        config["aliases"] = ["shared_alias"]
        (targets_dir / "{}.json".format(target_name)).write_text(
            json.dumps(config, ensure_ascii=False),
            encoding="utf-8",
        )

    with pytest.raises(ValueError, match="alias conflict"):
        load_target_registry(targets_dir)


def test_target_flow_preflight_blocks_before_handler_execution(
    tmp_path,
    monkeypatch,
):
    from agent import DigitalICAgent

    agent = DigitalICAgent()
    calls = []
    monkeypatch.setattr(agent, "check_capability", lambda _name: False)
    monkeypatch.setattr(agent, "record_artifact_run", lambda *_args, **_kwargs: None)
    agent.target_handlers["sync-fifo"].flows["generate-rtl"] = (
        lambda **_kwargs: calls.append("generate-rtl") or True
    )
    agent.target_handlers["sync-fifo"].flows["sim-rtl"] = (
        lambda **_kwargs: calls.append("sim-rtl") or True
    )

    assert agent.run_target_flow(
        "sync-fifo",
        "generate-rtl",
        output_dir=tmp_path,
    )
    assert agent.run_target_flow(
        "sync-fifo",
        "sim-rtl",
        output_dir=tmp_path,
    ) is False
    assert calls == ["generate-rtl"]


def test_diagnostic_reports_required_optional_and_not_applicable(
    capsys,
    monkeypatch,
):
    from agent import DigitalICAgent

    agent = DigitalICAgent()
    monkeypatch.setattr(agent, "check_capability", lambda _name: False)

    assert agent.run_diagnostic(flow="design-document") is True
    document_output = capsys.readouterr().out
    assert "vivado" in document_output
    assert "N/A" in document_output
    assert "当前动作不适用" in document_output

    assert agent.run_diagnostic(flow="sim-rtl") is False
    simulation_output = capsys.readouterr().out
    assert "vivado" in simulation_output
    assert "必需" in simulation_output
    assert "synthpilot" in simulation_output
    assert "可选" in simulation_output
    assert "降级" in simulation_output


def test_default_document_workflow_executes_loaded_skill_without_external_tools(
    tmp_path,
    monkeypatch,
):
    from agent import DigitalICAgent

    calls = []

    class RecordingExecutor:
        def execute(self, request):
            calls.append(request)
            return SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.SUCCEEDED,
                artifacts=(Path(request.context["design_spec_path"]),),
                message="recorded",
            )

    agent = DigitalICAgent(skill_executor=RecordingExecutor())
    monkeypatch.setattr(agent, "check_cli_tool", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(agent, "check_mcp_server", lambda *_args, **_kwargs: False)

    assert agent.execute_workflow(
        "请生成设计文档和架构方案",
        output_dir=tmp_path,
        skip_tool_check=False,
    )
    assert len(calls) == 1
    assert calls[0].skill.name == "digital-ic-designer"
    assert calls[0].skill.title == "数字IC设计架构师"
    assert 'name: "digital-ic-designer"' in calls[0].skill.content
    assert len(calls[0].skill.content_digest) == 64
    assert Path(calls[0].context["design_spec_path"]).exists()


def test_default_document_workflow_records_real_agent_run(tmp_path):
    from agent import DigitalICAgent
    from agent_contracts import AgentRunStatus, ToolResultStatus

    agent = DigitalICAgent()

    assert agent.execute_workflow(
        "请生成设计文档和架构方案",
        output_dir=tmp_path,
        skip_tool_check=False,
    )
    assert agent.last_agent_run.status is AgentRunStatus.SUCCEEDED
    assert agent.last_agent_run.tool_results
    assert all(
        result.status is ToolResultStatus.SUCCEEDED
        and result.returncode == 0
        and result.artifacts
        for result in agent.last_agent_run.tool_results
    )
    assert agent.last_agent_run.artifacts


def test_workflow_rejects_empty_skill_selection(tmp_path):
    from agent import DigitalICAgent
    from agent_contracts import AgentRunStatus

    agent = DigitalICAgent()

    assert agent.execute_workflow(
        "\u4e0d\u8981 RTL",
        output_dir=tmp_path,
        skip_tool_check=True,
    ) is False
    assert agent.last_agent_run.status is AgentRunStatus.FAILED
    assert "skill" in agent.last_agent_run.failure_reason.lower()


def test_default_rtl_and_verification_skills_do_not_report_success(tmp_path):
    from agent import DigitalICAgent

    agent = DigitalICAgent()
    spec_path = tmp_path / "design_spec.md"
    spec_path.write_text(
        "# Design Specification\n\n## Requirements\n\nExample.\n",
        encoding="utf-8",
    )

    for skill_name in ("digital-ic-rtl-designer", "digital-ic-verifier"):
        skill = agent.loaded_skills[skill_name]
        result = agent.skill_executor.execute(
            SkillExecutionRequest(
                skill=skill,
                user_input="execute the requested skill",
                output_dir=tmp_path,
                context={"design_spec_path": str(spec_path)},
            )
        )

        assert result.status is SkillExecutionStatus.BLOCKED
        assert result.failure_reason
        assert not result.validated_artifacts or spec_path.resolve() in result.validated_artifacts


def test_workflow_rejects_partial_result_from_custom_executor(tmp_path):
    from agent import DigitalICAgent

    class PartialExecutor:
        def execute(self, request):
            plan_path = request.output_dir / "verification_plan.md"
            plan_path.write_text("# Verification Plan\n", encoding="utf-8")
            return SkillExecutionResult(
                skill_name=request.skill.name,
                action=request.skill.action,
                status=SkillExecutionStatus.PARTIAL,
                artifacts=(plan_path,),
                message="plan generated",
            )

    agent = DigitalICAgent(skill_executor=PartialExecutor())

    assert agent.execute_workflow(
        "请使用 UVM 进行验证",
        output_dir=tmp_path,
        skip_tool_check=True,
    ) is False
