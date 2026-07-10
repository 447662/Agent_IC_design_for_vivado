from typing import Any
from pathlib import Path


def check_rtl_project(
    target_name: Any,
    output_dir: Any,
    rtl_name: Any,
    tb_name: Any,
    sim_script_name: Any,
    project_script_name: Any,
    gui_script_name: Any,
    xpr_name: Any,
    vcd_name: Any,
    wave_db_resolver: Any,
    rtl_markers: Any,
    tb_markers: Any,
) -> Any:
    project_dir = Path(output_dir) / target_name
    rtl_path = project_dir / "rtl" / rtl_name
    tb_path = project_dir / "tb" / tb_name
    sim_dir = project_dir / "sim"
    sim_script_path = sim_dir / sim_script_name
    project_script_path = sim_dir / project_script_name
    gui_script_path = sim_dir / gui_script_name
    xpr_path = project_dir / "vivado_project" / xpr_name
    vcd_path = sim_dir / vcd_name
    wave_db_path = wave_db_resolver(sim_dir)
    report_path = project_dir / "reports" / "sim_report.md"

    checks = [
        ("RTL exists", rtl_path.exists(), rtl_path),
        ("Testbench exists", tb_path.exists(), tb_path),
        ("Vivado sim script exists", sim_script_path.exists(), sim_script_path),
        (
            "Vivado project script exists",
            project_script_path.exists(),
            project_script_path,
        ),
        ("Vivado GUI script exists", gui_script_path.exists(), gui_script_path),
        ("Vivado project exists", xpr_path.exists(), xpr_path),
        ("VCD exists", vcd_path.exists(), vcd_path),
        ("WDB exists", wave_db_path.exists(), wave_db_path),
        ("Simulation report exists", report_path.exists(), report_path),
    ]

    if rtl_path.exists():
        rtl_text = rtl_path.read_text(encoding="utf-8")
        checks.extend(
            (label, token in rtl_text, rtl_path)
            for label, token in rtl_markers
        )

    if tb_path.exists():
        tb_text = tb_path.read_text(encoding="utf-8")
        checks.extend(
            (label, token in tb_text, tb_path)
            for label, token in tb_markers
        )

    print("{} RTL check".format(target_name))
    print("=" * 60)
    ok = True
    for label, passed, path in checks:
        print("[{}] {}: {}".format("OK" if passed else "NO", label, path))
        ok = ok and passed
    return ok
