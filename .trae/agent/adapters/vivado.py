import os
import shutil
from pathlib import Path
from typing import Any


VIVADO_COMMAND_ENV_VARS = (
    "DIGITAL_IC_AGENT_VIVADO",
    "VIVADO_PATH",
)


def normalize_vivado_command(command: Any) -> str | None:
    if command is None:
        return None

    command_text = str(command).strip()
    if not command_text:
        return None

    command_path = Path(command_text)
    if (
        command_path.name.lower() == "vivado.exe"
        and command_path.parent.name.lower() == "win64.o"
        and command_path.parent.parent.name.lower() == "unwrapped"
    ):
        wrapped_command = command_path.parent.parent.parent / "vivado.bat"
        return str(wrapped_command)

    return command_text


def resolve_vivado_command(self: Any) -> Any:
    configured_command = normalize_vivado_command(getattr(self, "vivado_command", None))
    if configured_command:
        return configured_command

    for env_name in VIVADO_COMMAND_ENV_VARS:
        env_command = normalize_vivado_command(os.environ.get(env_name))
        if env_command:
            return env_command

    vivado_on_path = shutil.which("vivado")
    if vivado_on_path:
        return normalize_vivado_command(vivado_on_path)

    return None


def run_vivado_batch(
    self: Any,
    vivado_command: Any,
    script_name: Any,
    cwd: Any,
    extra_args: Any=None,
    timeout: Any=None,
    env: Any=None,
) -> Any:
    command = [vivado_command, "-mode", "batch"]
    command.extend(extra_args or [])
    command.extend(["-source", str(script_name)])
    run_kwargs = {
        "cwd": cwd,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "timeout": timeout if timeout is not None else self.vivado_timeout,
        "check": False,
    }
    if env is not None:
        run_kwargs["env"] = env
    return self.command_runner.run(command, **run_kwargs)


def launch_vivado_gui(self: Any, vivado_command: Any, script_name: Any, cwd: Any, extra_args: Any=None) -> Any:
    command = [vivado_command, "-mode", "gui"]
    command.extend(extra_args or [])
    command.extend(["-source", str(script_name)])
    return self.command_runner.launch(
        command,
        cwd=cwd,
        mode="interactive",
        preserve=True,
        startup_timeout=getattr(self, "gui_startup_timeout", 1.0),
    )
