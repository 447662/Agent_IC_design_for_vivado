import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from adapters.vivado import launch_vivado_gui  # noqa: E402
import agent as agent_module  # noqa: E402
from agent import DigitalICAgent  # noqa: E402
from agent_entrypoint import run_cli  # noqa: E402
from agent_runtime import CommandRunner, ManagedProcess  # noqa: E402


class FakeProcess:
    def __init__(
        self,
        *,
        pid: int = 4321,
        poll_result=None,
        timeout_once: bool = False,
    ):
        self.pid = pid
        self.returncode = poll_result
        self.poll_result = poll_result
        self.timeout_once = timeout_once
        self.terminated = False
        self.killed = False
        self.wait_calls = []

    def poll(self):
        return self.poll_result

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        if self.timeout_once:
            self.timeout_once = False
            raise subprocess.TimeoutExpired(["vivado"], timeout)
        if self.returncode is None:
            self.returncode = 0
        self.poll_result = self.returncode
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 143
        self.poll_result = 143

    def kill(self):
        self.killed = True
        self.returncode = 137
        self.poll_result = 137


def test_launch_returns_managed_process_with_metadata(monkeypatch, tmp_path):
    fake_process = FakeProcess()
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **kwargs: fake_process,
    )

    runner = CommandRunner()
    handle = runner.launch(
        ["vivado", "-mode", "gui"],
        cwd=tmp_path,
        mode="interactive",
        preserve=True,
        startup_timeout=0,
    )

    assert isinstance(handle, ManagedProcess)
    assert handle.pid == 4321
    assert handle.command == ("vivado", "-mode", "gui")
    assert handle.cwd == tmp_path
    assert handle.mode == "interactive"
    assert handle.preserve is True
    assert handle.poll() is None
    assert runner.active_processes == (handle,)


def test_launch_rejects_process_that_exits_during_startup(monkeypatch):
    fake_process = FakeProcess(poll_result=1)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **kwargs: fake_process,
    )

    runner = CommandRunner()
    with pytest.raises(RuntimeError, match="exited during startup"):
        runner.launch(["vivado"], startup_timeout=0)

    assert "startup exit code 1" in runner.launched_processes[0].diagnostics


def test_automation_process_is_cleaned_up_on_runner_exit(monkeypatch):
    fake_process = FakeProcess()
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **kwargs: fake_process,
    )

    with CommandRunner() as runner:
        handle = runner.launch(
            ["vivado"],
            mode="automation",
            preserve=False,
            startup_timeout=0,
        )
        assert handle.poll() is None

    assert fake_process.terminated is True
    assert fake_process.wait_calls


def test_interactive_process_is_preserved_on_runner_exit(monkeypatch):
    fake_process = FakeProcess()
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **kwargs: fake_process,
    )

    with CommandRunner() as runner:
        runner.launch(
            ["vivado"],
            mode="interactive",
            preserve=True,
            startup_timeout=0,
        )

    assert fake_process.terminated is False
    assert fake_process.killed is False


def test_wait_timeout_cleans_up_automation_process_and_records_diagnostic(
    monkeypatch,
):
    fake_process = FakeProcess(timeout_once=True)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **kwargs: fake_process,
    )

    runner = CommandRunner()
    handle = runner.launch(
        ["vivado"],
        mode="automation",
        preserve=False,
        startup_timeout=0,
    )

    with pytest.raises(subprocess.TimeoutExpired):
        handle.wait(timeout=0.01)

    assert fake_process.terminated is True
    assert "wait timed out after 0.01 seconds" in handle.diagnostics


def test_vivado_adapter_launches_preserved_interactive_process(tmp_path):
    calls = []

    class FakeRunner:
        def launch(self, command, **kwargs):
            calls.append((command, kwargs))
            return "managed"

    class FakeAgent:
        command_runner = FakeRunner()
        gui_startup_timeout = 1.5

    result = launch_vivado_gui(
        FakeAgent(),
        "vivado",
        "open_wave.tcl",
        tmp_path,
    )

    assert result == "managed"
    assert calls == [
        (
            [
                "vivado",
                "-mode",
                "gui",
                "-source",
                "open_wave.tcl",
            ],
            {
                "cwd": tmp_path,
                "mode": "interactive",
                "preserve": True,
                "startup_timeout": 1.5,
            },
        )
    ]


def test_agent_context_exit_cleans_command_runner():
    calls = []

    class FakeRunner:
        def cleanup(self):
            calls.append("cleanup")

    agent = DigitalICAgent.__new__(DigitalICAgent)
    agent.command_runner = FakeRunner()

    assert agent.__enter__() is agent
    agent.__exit__(None, None, None)

    assert calls == ["cleanup"]


def test_main_uses_agent_context(monkeypatch):
    events = []

    class FakeAgent:
        def __enter__(self):
            events.append("enter")
            return self

        def __exit__(self, exc_type, exc, traceback):
            events.append("exit")

        def print_targets(self):
            events.append("targets")

    fake_agent = FakeAgent()
    monkeypatch.setattr(agent_module, "create_agent", lambda: fake_agent)

    assert agent_module.main(["--list-targets"]) == 0
    assert events == ["enter", "targets", "exit"]


def test_cli_reports_gui_startup_failure_without_traceback(capsys):
    class FailingAgent:
        def open_rtl_wave(self, target, output_dir):
            raise RuntimeError("Process exited during startup with code 1")

    assert run_cli(
        ["--open-wave", "sync-fifo"],
        lambda: FailingAgent(),
    ) == 1
    captured = capsys.readouterr()
    assert "RTL wave open failed" in captured.err
    assert "Process exited during startup" in captured.err
    assert "Traceback" not in captured.err
