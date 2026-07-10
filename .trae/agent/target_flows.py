from pathlib import Path

from agent_runtime import TargetHandler


def build_target_handlers(agent):
    return {
        "async-fifo": TargetHandler(
            "async-fifo",
            {
                "generate-rtl": (
                    lambda output_dir="outputs", data_width=8, addr_width=4, **_:
                    agent.write_async_fifo_project(
                        output_dir,
                        data_width=data_width,
                        addr_width=addr_width,
                    )
                ),
                "sim-rtl": (
                    lambda output_dir="outputs", open_wave_gui=True, **_:
                    agent.run_async_fifo_vivado_sim(
                        output_dir=output_dir,
                        open_wave_gui=open_wave_gui,
                    )
                ),
                "regress-rtl": (
                    lambda output_dir="outputs", open_wave_gui=False, **_:
                    agent.run_async_fifo_regression(
                        output_dir=output_dir,
                        open_wave_gui=open_wave_gui,
                    )
                ),
                "uvm-smoke": (
                    lambda output_dir="outputs", open_wave_gui=True, **_:
                    agent.run_async_fifo_uvm_smoke(
                        output_dir=output_dir,
                        open_wave_gui=open_wave_gui,
                    )
                ),
                "uvm-coverage": (
                    lambda output_dir="outputs",
                    coverage_threshold=None,
                    coverage_percent=None,
                    **_: agent.run_async_fifo_uvm_coverage(
                        output_dir=output_dir,
                        coverage_threshold=coverage_threshold,
                        coverage_percent=coverage_percent,
                    )
                ),
                "uvm-random-regress": (
                    lambda output_dir="outputs", seeds=None, **_:
                    agent.run_async_fifo_uvm_random_regression(
                        output_dir=output_dir,
                        seeds=seeds,
                    )
                ),
                "analyze-rtl-vcd": (
                    lambda output_dir="outputs",
                    limit=20,
                    waveform_backend="auto",
                    **_: agent.analyze_async_fifo_vcd(
                        output_dir=output_dir,
                        limit=limit,
                        waveform_backend=waveform_backend,
                    )
                ),
                "check-rtl": (
                    lambda output_dir="outputs", **_:
                    agent.check_async_fifo_rtl(output_dir=output_dir)
                ),
                "open-wave": (
                    lambda output_dir="outputs", **_:
                    agent.open_async_fifo_project_gui(
                        Path(output_dir) / "async-fifo"
                    )
                ),
                "open-uvm-wave": (
                    lambda output_dir="outputs", wave_kind="coverage", **_:
                    agent.open_async_fifo_uvm_wave_gui(
                        Path(output_dir) / "async-fifo",
                        wave_kind=wave_kind,
                    )
                ),
            },
        ),
        "sync-fifo": TargetHandler(
            "sync-fifo",
            {
                "generate-rtl": (
                    lambda output_dir="outputs", data_width=8, addr_width=4, **_:
                    agent.write_sync_fifo_project(
                        output_dir,
                        data_width=data_width,
                        addr_width=addr_width,
                    )
                ),
                "sim-rtl": (
                    lambda output_dir="outputs", open_wave_gui=True, **_:
                    agent.run_sync_fifo_vivado_sim(
                        output_dir=output_dir,
                        open_wave_gui=open_wave_gui,
                    )
                ),
                "analyze-rtl-vcd": (
                    lambda output_dir="outputs",
                    limit=20,
                    waveform_backend="auto",
                    **_: agent.analyze_sync_fifo_vcd(
                        output_dir=output_dir,
                        limit=limit,
                        waveform_backend=waveform_backend,
                    )
                ),
                "check-rtl": (
                    lambda output_dir="outputs", **_:
                    agent.check_sync_fifo_rtl(output_dir=output_dir)
                ),
                "open-wave": (
                    lambda output_dir="outputs", **_:
                    agent.open_sync_fifo_project_gui(
                        Path(output_dir) / "sync-fifo"
                    )
                ),
            },
        ),
        "round-robin-arbiter": TargetHandler(
            "round-robin-arbiter",
            {
                "generate-rtl": (
                    lambda output_dir="outputs", **_:
                    agent.write_round_robin_arbiter_project(output_dir)
                ),
                "sim-rtl": (
                    lambda output_dir="outputs", open_wave_gui=True, **_:
                    agent.run_round_robin_arbiter_vivado_sim(
                        output_dir=output_dir,
                        open_wave_gui=open_wave_gui,
                    )
                ),
                "analyze-rtl-vcd": (
                    lambda output_dir="outputs",
                    limit=20,
                    waveform_backend="auto",
                    **_: agent.analyze_round_robin_arbiter_vcd(
                        output_dir=output_dir,
                        limit=limit,
                        waveform_backend=waveform_backend,
                    )
                ),
                "check-rtl": (
                    lambda output_dir="outputs", **_:
                    agent.check_round_robin_arbiter_rtl(
                        output_dir=output_dir
                    )
                ),
                "open-wave": (
                    lambda output_dir="outputs", **_:
                    agent.open_round_robin_arbiter_project_gui(
                        Path(output_dir) / "round-robin-arbiter"
                    )
                ),
            },
        ),
    }
