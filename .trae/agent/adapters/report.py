from pathlib import Path


def target_spec_catalog(self, target):
    target_info = self.get_target(target)
    return {
        "target": target_info,
        "parameters": target_info["parameters"],
        "interfaces": target_info["interfaces"],
        "checks": target_info["checks"],
        "scenarios": target_info["scenario_catalog"],
        "coverage_metrics": target_info["coverage_metrics"],
        "artifact_manifest": target_info["artifact_manifest"],
        "notes": target_info.get("notes", []),
    }


def target_scenario_catalog(self, target):
    return [dict(item) for item in self.target_spec_catalog(target)["scenarios"]]


def render_target_design_spec(self, target, requirement=None):
    catalog = self.target_spec_catalog(target)
    target_info = catalog["target"]
    requirement_text = (
        requirement.strip()
        if requirement
        else "未提供额外自然语言需求；当前规格由 target 配置生成。"
    )
    lines = [
        "# 设计规格",
        "",
        "## 目标概览",
        "",
        "| 字段 | 内容 |",
        "| --- | --- |",
        "| Target | {} |".format(target_info["name"]),
        "| 显示名称 | {} |".format(target_info["display_name"]),
        "| 设计族 | {} |".format(target_info["design_family"]),
        "| 描述 | {} |".format(target_info.get("description", "")),
        "",
        "## 自然语言需求",
        "",
        requirement_text,
        "",
        "## 参数",
        "",
        "| 参数 | 默认值 | 说明 |",
        "| --- | --- | --- |",
    ]
    for item in catalog["parameters"]:
        lines.append(
            "| {} | {} | {} |".format(
                item["name"],
                item["default"],
                item["description"],
            )
        )
    lines.extend(
        [
            "",
            "## 接口定义",
            "",
            "| 信号 | 方向 | 位宽 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for item in catalog["interfaces"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                item["name"],
                item["direction"],
                item["width"],
                item["description"],
            )
        )
    lines.extend(
        [
            "",
            "## 功能场景",
            "",
            "| 场景 ID | 类型 | 状态 | 说明 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for scenario in catalog["scenarios"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                scenario["id"],
                scenario["type"],
                scenario["status"],
                scenario["purpose"],
            )
        )
    lines.extend(["", "## 关键检查点", ""])
    for check in catalog["checks"]:
        lines.append("- {}".format(check))
    lines.extend(
        [
            "",
            "## 覆盖率能力",
            "",
            "| Metric ID | 名称 | 数据源 | 状态 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for metric in catalog["coverage_metrics"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                metric["id"],
                metric["label"],
                metric["source"],
                metric["status"],
            )
        )
    lines.extend(
        [
            "",
            "## Artifact Manifest",
            "",
            "| Artifact ID | 路径 | 状态 |",
            "| --- | --- | --- |",
        ]
    )
    for artifact in catalog["artifact_manifest"]:
        lines.append(
            "| {} | `{}` | {} |".format(
                artifact["id"],
                artifact["path"],
                artifact["status"],
            )
        )
    if catalog["notes"]:
        lines.extend(["", "## 备注", ""])
        for note in catalog["notes"]:
            lines.append("- {}".format(note))
    return "\n".join(lines) + "\n"


def write_target_design_spec(self, target, output_dir="outputs", requirement=None):
    target_info = self.get_target(target)
    reports_dir = Path(output_dir) / target_info["name"] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_text = self.render_target_design_spec(
        target_info["name"],
        requirement=requirement,
    )
    md_path = reports_dir / "design_spec.md"
    html_path = reports_dir / "design_spec.html"
    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(
        self.render_markdown_document_html(
            "{} 设计规格".format(target_info["display_name"]),
            markdown_text,
        ),
        encoding="utf-8",
    )
    self.record_artifact_run(
        target_info["name"],
        "generate-spec",
        output_dir=output_dir,
        status="PASS",
        options={"requirement": requirement},
        extra_artifacts=[
            {"id": "design_spec_html", "path": html_path, "status": "PASS"},
        ],
    )
    return {"md_path": md_path, "html_path": html_path}


def render_target_verification_plan(self, target):
    catalog = self.target_spec_catalog(target)
    target_info = catalog["target"]
    lines = [
        "# 验证计划",
        "",
        "## 目标概览",
        "",
        "| 字段 | 内容 |",
        "| --- | --- |",
        "| Target | {} |".format(target_info["name"]),
        "| 显示名称 | {} |".format(target_info["display_name"]),
        "| 设计族 | {} |".format(target_info["design_family"]),
        "",
        "## scenario catalog",
        "",
        "| 场景 ID | 类型 | 状态 | 验证目的 |",
        "| --- | --- | --- | --- |",
    ]
    for scenario in catalog["scenarios"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                scenario["id"],
                scenario["type"],
                scenario["status"],
                scenario["purpose"],
            )
        )
    lines.extend(
        [
            "",
            "## coverage_metrics",
            "",
            "| Metric ID | 名称 | 数据源 | 状态 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for metric in catalog["coverage_metrics"]:
        lines.append(
            "| {} | {} | {} | {} |".format(
                metric["id"],
                metric["label"],
                metric["source"],
                metric["status"],
            )
        )
    lines.extend(
        [
            "",
            "## 检查点与断言建议",
            "",
            "| 检查点 | 建议落点 |",
            "| --- | --- |",
        ]
    )
    for check in catalog["checks"]:
        lines.append(
            "| {} | RTL/TB scoreboard 或后续 SVA/UVM monitor |".format(check)
        )
    lines.extend(
        [
            "",
            "## 验证执行顺序",
            "",
            "- 先生成 RTL/TB/Vivado Tcl，确认目标目录结构完整。",
            "- 运行 Vivado/xsim smoke 仿真，生成 VCD/WDB。",
            "- 打开 Vivado GUI 查看关键波形，不只依赖终端日志。",
            "- 使用 VCD/RWave 分析关键握手、边界和公平性事件。",
            "- 将 Markdown/HTML 报告作为评审入口，后续再扩展 UVM 与覆盖率。",
            "",
            "## 出口准则",
            "",
            "- scenario catalog 中 PASS 项必须有可追溯证据。",
            "- SKIP 项必须记录未执行原因，N/A 项必须说明不适用范围。",
            "- 所有关键检查点均能在 TB scoreboard、日志或波形分析中定位。",
            "- 仿真报告、波形数据库和验证计划在 target reports 目录可追溯。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_target_verification_plan(self, target, output_dir="outputs"):
    target_info = self.get_target(target)
    reports_dir = Path(output_dir) / target_info["name"] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_text = self.render_target_verification_plan(target_info["name"])
    md_path = reports_dir / "verification_plan.md"
    html_path = reports_dir / "verification_plan.html"
    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(
        self.render_markdown_document_html(
            "{} 验证计划".format(target_info["display_name"]),
            markdown_text,
            variant="scenario",
        ),
        encoding="utf-8",
    )
    self.record_artifact_run(
        target_info["name"],
        "generate-verification-plan",
        output_dir=output_dir,
        status="PASS",
        extra_artifacts=[
            {
                "id": "verification_plan_html",
                "path": html_path,
                "status": "PASS",
            },
        ],
    )
    return {"md_path": md_path, "html_path": html_path}
