import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol, TypedDict


TARGET_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
PathLike = str | os.PathLike[str]


class TargetParameter(TypedDict):
    name: str
    default: str
    description: str


class TargetInterface(TypedDict):
    name: str
    direction: str
    width: str
    description: str


class TargetScenario(TypedDict):
    id: str
    type: str
    purpose: str
    status: str


class TargetCoverageMetric(TypedDict):
    id: str
    label: str
    source: str
    status: str


class TargetArtifact(TypedDict):
    id: str
    path: str
    status: str


class TargetScaffoldConfig(TypedDict):
    name: str
    display_name: str
    design_family: str
    handler: str
    aliases: list[str]
    flows: list[str]
    description: str
    parameters: list[TargetParameter]
    interfaces: list[TargetInterface]
    checks: list[str]
    scenario_catalog: list[TargetScenario]
    coverage_metrics: list[TargetCoverageMetric]
    artifact_manifest: list[TargetArtifact]
    notes: list[str]


class TargetScaffoldResult(TypedDict):
    project_dir: Path
    config_path: Path
    rtl_path: Path
    tb_path: Path
    todo_path: Path
    readme_path: Path
    manifest_path: Path


class TargetScaffolderAgent(Protocol):
    def get_target(self, target: str) -> Mapping[str, object]: ...

    def record_artifact_run(self, *args: object, **kwargs: object) -> Path: ...


def normalize_target_name(target_name: str) -> str:
    raw_name = str(target_name).strip().lower()
    normalized = raw_name.replace("_", "-")
    if not TARGET_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "invalid target name: {}; use lowercase letters, numbers, '-' or '_'".format(
                target_name
            )
        )
    return normalized


def build_target_config(
    target_name: str,
    description: str | None = None,
) -> TargetScaffoldConfig:
    target_slug = normalize_target_name(target_name)
    module_name = target_slug.replace("-", "_")
    display_name = " ".join(part.capitalize() for part in target_slug.split("-"))
    target_description = str(description or "").strip() or (
        "TODO: describe the {} design target".format(display_name)
    )
    aliases = [module_name] if module_name != target_slug else []

    return {
        "name": target_slug,
        "display_name": display_name,
        "design_family": "custom",
        "handler": target_slug,
        "aliases": aliases,
        "flows": [],
        "description": target_description,
        "parameters": [
            {
                "name": "DATA_WIDTH",
                "default": "8",
                "description": "TODO: define the primary data width",
            }
        ],
        "interfaces": [
            {
                "name": "clk",
                "direction": "input",
                "width": "1",
                "description": "Primary design clock",
            },
            {
                "name": "rst_n",
                "direction": "input",
                "width": "1",
                "description": "Active-low reset",
            },
        ],
        "checks": [
            "TODO: define protocol, ordering, reset, and error checks",
        ],
        "scenario_catalog": [
            {
                "id": "smoke",
                "type": "functional",
                "purpose": "TODO: define the minimum smoke scenario",
                "status": "SKIP",
            }
        ],
        "coverage_metrics": [
            {
                "id": "statement",
                "label": "Statement coverage",
                "source": "not-enabled",
                "status": "SKIP",
            },
            {
                "id": "branch",
                "label": "Branch coverage",
                "source": "not-enabled",
                "status": "SKIP",
            },
            {
                "id": "condition",
                "label": "Condition coverage",
                "source": "not-enabled",
                "status": "SKIP",
            },
            {
                "id": "toggle",
                "label": "Toggle coverage",
                "source": "not-enabled",
                "status": "SKIP",
            },
            {
                "id": "functional",
                "label": "Functional coverage",
                "source": "no-verification-flow",
                "status": "N/A",
            },
        ],
        "artifact_manifest": [
            {
                "id": "design_spec",
                "path": "reports/design_spec.md",
                "status": "SKIP",
            },
            {
                "id": "verification_plan",
                "path": "reports/verification_plan.md",
                "status": "SKIP",
            },
            {
                "id": "rtl",
                "path": "rtl/{}.v".format(module_name),
                "status": "SKIP",
            },
            {
                "id": "testbench",
                "path": "tb/tb_{}.v".format(module_name),
                "status": "SKIP",
            },
            {
                "id": "sim_report",
                "path": "reports/sim_report.md",
                "status": "SKIP",
            },
            {
                "id": "todo",
                "path": "TODO.md",
                "status": "PASS",
            },
        ],
        "notes": [
            "Generated by --create-target; complete TODO items before registry installation.",
        ],
    }


def render_rtl_placeholder(target_slug: str) -> str:
    module_name = target_slug.replace("-", "_")
    return """`timescale 1ns/1ps

module {module_name} #(
    parameter integer DATA_WIDTH = 8
) (
    input wire clk,
    input wire rst_n
);

    // TODO: implement the {target_slug} RTL behavior.

endmodule
""".format(module_name=module_name, target_slug=target_slug)


def render_tb_placeholder(target_slug: str) -> str:
    module_name = target_slug.replace("-", "_")
    return """`timescale 1ns/1ps

module tb_{module_name};
    reg clk = 1'b0;
    reg rst_n = 1'b0;

    {module_name} dut (
        .clk(clk),
        .rst_n(rst_n)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("{module_name}_trace.vcd");
        $dumpvars(0, tb_{module_name});
        #20 rst_n = 1'b1;
        // TODO: add stimulus, checks, and a stable PASS/FAIL marker.
        #100 $finish;
    end
endmodule
""".format(module_name=module_name)


def render_report_placeholder(title: str, target_slug: str, purpose: str) -> str:
    return """# {title}

- Target: `{target_slug}`
- Status: SKIP
- Purpose: {purpose}

## TODO

- [ ] Replace this placeholder with generated or measured content.
- [ ] Record commands, tools, inputs, outputs, and PASS/FAIL evidence.
""".format(title=title, target_slug=target_slug, purpose=purpose)


def render_todo(target_slug: str, module_name: str) -> str:
    return """# {target_slug} Target TODO

- [ ] Refine `target/{module_name}.json` parameters, interfaces, checks, and scenarios.
- [ ] Implement `rtl/{module_name}.v`.
- [ ] Implement `tb/tb_{module_name}.v` with deterministic PASS/FAIL markers.
- [ ] Add a `TargetHandler` and declare only implemented flows.
- [ ] Copy the reviewed config to `.trae/agent/targets/{module_name}.json`.
- [ ] Generate and review `design_spec.md` and `verification_plan.md`.
- [ ] Add unit, integration, and real Vivado/xsim validation where applicable.
- [ ] Run Ruff, Mypy, pytest, and coverage gates.
""".format(target_slug=target_slug, module_name=module_name)


def render_readme(target_slug: str, module_name: str) -> str:
    return """# {target_slug} Target Scaffold

This directory is a candidate target scaffold. It is intentionally not installed
into the active registry because the Agent requires every registered target to
have a matching `TargetHandler`.

## Contents

- `target/{module_name}.json`: P5.6-compatible candidate metadata.
- `rtl/{module_name}.v`: minimal synthesizable RTL placeholder.
- `tb/tb_{module_name}.v`: minimal simulation placeholder.
- `reports/`: design, verification, and simulation report placeholders.
- `TODO.md`: implementation and acceptance checklist.

## Installation

1. Complete the RTL, testbench, metadata, and target handler.
2. Copy `target/{module_name}.json` to
   `.trae/agent/targets/{module_name}.json`.
3. Add the handler module under `.trae/agent/target_handlers/`.
4. Run `--list-targets`, target tests, Ruff, Mypy, and coverage gates.
""".format(target_slug=target_slug, module_name=module_name)


def create_target_scaffold(
    self: TargetScaffolderAgent,
    target_name: str,
    output_dir: PathLike = "outputs",
    description: str | None = None,
) -> TargetScaffoldResult:
    target_slug = normalize_target_name(target_name)
    try:
        self.get_target(target_slug)
    except ValueError:
        pass
    else:
        raise ValueError("target already registered: {}".format(target_slug))

    project_dir = Path(output_dir) / target_slug
    if project_dir.exists():
        raise FileExistsError("target scaffold already exists: {}".format(project_dir))

    module_name = target_slug.replace("-", "_")
    target_dir = project_dir / "target"
    rtl_dir = project_dir / "rtl"
    tb_dir = project_dir / "tb"
    reports_dir = project_dir / "reports"
    for directory in (target_dir, rtl_dir, tb_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=False)

    config_path = target_dir / "{}.json".format(module_name)
    rtl_path = rtl_dir / "{}.v".format(module_name)
    tb_path = tb_dir / "tb_{}.v".format(module_name)
    design_spec_path = reports_dir / "design_spec.md"
    verification_plan_path = reports_dir / "verification_plan.md"
    sim_report_path = reports_dir / "sim_report.md"
    todo_path = project_dir / "TODO.md"
    readme_path = project_dir / "README.md"

    config = build_target_config(target_slug, description=description)
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    rtl_path.write_text(render_rtl_placeholder(target_slug), encoding="utf-8")
    tb_path.write_text(render_tb_placeholder(target_slug), encoding="utf-8")
    design_spec_path.write_text(
        render_report_placeholder(
            "设计规格占位",
            target_slug,
            "完成参数、接口、行为和约束定义。",
        ),
        encoding="utf-8",
    )
    verification_plan_path.write_text(
        render_report_placeholder(
            "验证计划占位",
            target_slug,
            "完成场景、检查、覆盖率和退出准则定义。",
        ),
        encoding="utf-8",
    )
    sim_report_path.write_text(
        render_report_placeholder(
            "仿真报告占位",
            target_slug,
            "记录仿真工具、命令、日志、波形和结果。",
        ),
        encoding="utf-8",
    )
    todo_path.write_text(render_todo(target_slug, module_name), encoding="utf-8")
    readme_path.write_text(render_readme(target_slug, module_name), encoding="utf-8")

    manifest_path = self.record_artifact_run(
        target_slug,
        "create-target",
        output_dir=output_dir,
        status="PASS",
        options={"description": description},
        target_info=config,
        project_dir=project_dir,
        extra_artifacts=[
            {"id": "target_config", "path": config_path, "status": "PASS"},
            {"id": "readme", "path": readme_path, "status": "PASS"},
        ],
    )
    return {
        "project_dir": project_dir,
        "config_path": config_path,
        "rtl_path": rtl_path,
        "tb_path": tb_path,
        "todo_path": todo_path,
        "readme_path": readme_path,
        "manifest_path": manifest_path,
    }
