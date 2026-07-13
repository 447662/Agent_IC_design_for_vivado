import inspect
import sys
from pathlib import Path
from typing import Any, get_type_hints


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / "src" / "digital_ic_agent" / "_runtime"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from digital_ic_agent._runtime import agent_async_fifo_reports  # noqa: E402
from digital_ic_agent._runtime import agent_async_fifo_runtime  # noqa: E402
from digital_ic_agent._runtime import agent_sim_smoke  # noqa: E402
from digital_ic_agent._runtime import agent_runtime_facades  # noqa: E402
from digital_ic_agent._runtime import agent_waveform  # noqa: E402


def test_async_fifo_runtime_exposes_typed_analysis_contracts():
    assert set(agent_async_fifo_runtime.WaveEventRow.__annotations__) >= {
        "time_h",
        "begin_h",
        "end_h",
        "at_h",
        "values",
    }
    assert set(agent_async_fifo_runtime.WaveSearchResult.__annotations__) >= {
        "total",
        "shown",
        "events",
        "segments",
        "intervals",
    }
    assert set(agent_async_fifo_runtime.AsyncFifoVcdAnalysis.__annotations__) == {
        "vcd_path",
        "info",
        "write_events",
        "read_events",
    }
    assert set(agent_async_fifo_runtime.AsyncFifoRegressionCase.__annotations__) == {
        "name",
        "data_width",
        "addr_width",
    }

    mixin = agent_async_fifo_runtime.AsyncFifoRuntimeMixin
    hints = get_type_hints(mixin.resolve_async_fifo_vcd_path)
    assert hints["return"] == Path
    hints = get_type_hints(mixin.collect_async_fifo_vcd_analysis)
    assert hints["return"] is agent_async_fifo_runtime.AsyncFifoVcdAnalysis
    hints = get_type_hints(mixin.collect_async_fifo_vcd_analysis_with_rwave_batch)
    assert hints["return"] is agent_async_fifo_runtime.AsyncFifoVcdAnalysis
    hints = get_type_hints(mixin.async_fifo_required_wcfg_objects)
    assert hints["return"] == list[str]
    hints = get_type_hints(mixin.async_fifo_regression_cases)
    assert hints["return"] == list[agent_async_fifo_runtime.AsyncFifoRegressionCase]


def test_async_fifo_report_exposes_typed_wcfg_contract():
    assert set(agent_async_fifo_reports.AsyncFifoWcfgSummary.__annotations__) == {
        "path",
        "exists",
        "object_count",
        "required_objects",
        "present_required",
        "missing_required",
        "valid",
    }

    mixin = agent_async_fifo_reports.AsyncFifoReportMixin
    hints = get_type_hints(mixin.parse_async_fifo_wcfg_summary)
    assert hints["project_dir"] == str | Path
    assert hints["return"] is agent_async_fifo_reports.AsyncFifoWcfgSummary
    hints = get_type_hints(mixin.write_async_fifo_sim_report)
    assert hints["project_dir"] == str | Path
    assert hints["vcd_path"] == str | Path
    assert hints["wave_db_path"] == str | Path
    assert hints["return"] == Path


def test_runtime_facades_expose_protocol_boundaries():
    assert inspect.isclass(agent_runtime_facades.ProjectOverviewAgent)
    assert inspect.isclass(agent_runtime_facades.ArtifactRefreshAgent)
    assert inspect.isclass(agent_runtime_facades.TargetFlowAgent)
    assert inspect.isclass(agent_runtime_facades.WaveResolverAgent)

    target_flow_hints = get_type_hints(agent_runtime_facades.TargetFlowAgent.run_target_flow)
    assert target_flow_hints["return"] is object
    hints = get_type_hints(agent_runtime_facades.refresh_project_overview)
    assert hints["agent"] is agent_runtime_facades.ProjectOverviewAgent
    assert hints["return"] == agent_runtime_facades.ProjectOverviewResult | None
    hints = get_type_hints(agent_runtime_facades.record_artifact_run)
    assert hints["agent"] is agent_runtime_facades.ArtifactRefreshAgent
    assert hints["return"] == Path
    project_overview_hints = get_type_hints(
        agent_runtime_facades.ProjectOverviewAgent.write_project_overview
    )
    assert project_overview_hints["return"] is agent_runtime_facades.ProjectOverviewResult
    artifact_refresh_hints = get_type_hints(
        agent_runtime_facades.ArtifactRefreshAgent.refresh_project_overview
    )
    assert artifact_refresh_hints["return"] == agent_runtime_facades.ProjectOverviewResult | None
    hints = get_type_hints(agent_runtime_facades.resolve_vcd_analyzer_path)
    assert hints["agent"] is agent_runtime_facades.WaveResolverAgent
    hints = get_type_hints(agent_runtime_facades.generate_rtl_project)
    assert hints["agent"] is agent_runtime_facades.TargetFlowAgent
    hints = get_type_hints(agent_runtime_facades.TargetFlowAgent.get_target)
    assert hints["return"] is agent_runtime_facades.TargetMetadata
    hints = get_type_hints(agent_runtime_facades.open_rtl_wave)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.generate_rtl_project)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.run_rtl_sim)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.run_uvm_smoke)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.run_uvm_coverage)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.run_uvm_random_regression)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.open_uvm_wave)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.regress_rtl)
    assert hints["return"] is bool
    hints = get_type_hints(agent_runtime_facades.normalize_rtl_target)
    assert hints["return"] is str
    check_hints = get_type_hints(agent_runtime_facades.check_rtl_project)
    assert check_hints["_agent"] is object
    bootstrap_hints = get_type_hints(agent_runtime_facades.render_vivado_tclstore_bootstrap)
    assert bootstrap_hints["_agent"] is object


def test_runtime_facades_waveform_and_smoke_wrappers_avoid_broad_any():
    waveform_hints = get_type_hints(agent_runtime_facades.analyze_waveform)
    vcd_hints = get_type_hints(agent_runtime_facades.analyze_vcd)
    smoke_loop_hints = get_type_hints(agent_runtime_facades.run_smoke_loop)
    detect_hints = get_type_hints(agent_runtime_facades.detect_simulator)
    sources_hints = get_type_hints(agent_runtime_facades.write_sim_smoke_sources)
    icarus_hints = get_type_hints(agent_runtime_facades.run_icarus_sim_smoke)
    gui_hints = get_type_hints(agent_runtime_facades.open_vivado_wave_gui)
    vivado_hints = get_type_hints(agent_runtime_facades.run_vivado_sim_smoke)
    dispatch_hints = get_type_hints(agent_runtime_facades.run_sim_smoke)

    assert waveform_hints["agent"] is agent_waveform.WaveformAnalysisAgent
    assert waveform_hints["report_title"] is str
    assert waveform_hints["return"] is bool
    assert vcd_hints["agent"] is agent_waveform.WaveformAnalysisAgent
    assert vcd_hints["return"] is bool
    assert smoke_loop_hints["agent"] is agent_sim_smoke.SmokeLoopAgent
    assert smoke_loop_hints["return"] is bool
    assert detect_hints["agent"] is agent_sim_smoke.SimulatorDetector
    assert sources_hints["return"] == tuple[Path, Path, Path, Path]
    assert icarus_hints["agent"] is agent_sim_smoke.IcarusSmokeAgent
    assert gui_hints["agent"] is agent_sim_smoke.VivadoGuiAgent
    assert vivado_hints["agent"] is agent_sim_smoke.VivadoSmokeAgent
    assert dispatch_hints["agent"] is agent_sim_smoke.SimSmokeAgent

    for hints in (
        waveform_hints,
        vcd_hints,
        smoke_loop_hints,
        detect_hints,
        sources_hints,
        icarus_hints,
        gui_hints,
        vivado_hints,
        dispatch_hints,
    ):
        assert Any not in hints.values()


class _WcfgPlugin(agent_async_fifo_reports.AsyncFifoReportMixin):
    def async_fifo_required_wcfg_objects(self) -> list[str]:
        return [
            "/tb_async_fifo/scenario_id",
            "/tb_async_fifo/wr_clk",
        ]

    def write_async_fifo_regression_matrix(self, project_dir: str | Path) -> Path:
        path = Path(project_dir) / "reports" / "regression_matrix.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# matrix\n", encoding="utf-8")
        return path

    def write_async_fifo_summary_report(self, **_kwargs: object) -> Path:
        return Path(_kwargs["project_dir"]) / "reports" / "sim_summary.md"


def test_parse_async_fifo_wcfg_summary_handles_missing_file(tmp_path):
    summary = _WcfgPlugin().parse_async_fifo_wcfg_summary(tmp_path / "async-fifo")

    assert summary["path"] == tmp_path / "async-fifo" / "sim" / "async_fifo_debug.wcfg"
    assert summary["exists"] is False
    assert summary["object_count"] == 0
    assert summary["present_required"] == []
    assert summary["missing_required"] == [
        "/tb_async_fifo/scenario_id",
        "/tb_async_fifo/wr_clk",
    ]
    assert summary["valid"] is False


def test_parse_async_fifo_wcfg_summary_uses_declared_object_size(tmp_path):
    project_dir = tmp_path / "async-fifo"
    wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
    wcfg_path.parent.mkdir(parents=True)
    wcfg_path.write_text(
        '<WVObjectSize size="7" />\n'
        "/tb_async_fifo/scenario_id\n"
        "/tb_async_fifo/wr_clk\n",
        encoding="utf-8",
    )

    summary = _WcfgPlugin().parse_async_fifo_wcfg_summary(project_dir)

    assert summary["exists"] is True
    assert summary["object_count"] == 7
    assert summary["present_required"] == [
        "/tb_async_fifo/scenario_id",
        "/tb_async_fifo/wr_clk",
    ]
    assert summary["missing_required"] == []
    assert summary["valid"] is True


def test_parse_async_fifo_wcfg_summary_falls_back_to_signal_count(tmp_path):
    project_dir = tmp_path / "async-fifo"
    wcfg_path = project_dir / "sim" / "async_fifo_debug.wcfg"
    wcfg_path.parent.mkdir(parents=True)
    wcfg_path.write_text(
        "/tb_async_fifo/scenario_id\n"
        "/tb_async_fifo/wr_clk\n"
        "/tb_async_fifo/extra_signal\n",
        encoding="utf-8",
    )

    summary = _WcfgPlugin().parse_async_fifo_wcfg_summary(project_dir)

    assert summary["exists"] is True
    assert summary["object_count"] == 3
    assert summary["missing_required"] == []
    assert summary["valid"] is True
