import shutil
from pathlib import Path


DEFAULT_VIVADO_CANDIDATES = (
    Path(r"D:\vivado\2025.2\Vivado\bin\vivado.bat"),
    Path(r"D:\vivado\2025.2\Vivado\bin\unwrapped\win64.o\vivado.exe"),
)


def resolve_vivado_command(self):
    vivado_on_path = shutil.which("vivado")
    if vivado_on_path:
        return vivado_on_path

    for candidate in DEFAULT_VIVADO_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None


def run_vivado_batch(
    self,
    vivado_command,
    script_name,
    cwd,
    extra_args=None,
    timeout=None,
    env=None,
):
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


def launch_vivado_gui(self, vivado_command, script_name, cwd, extra_args=None):
    command = [vivado_command, "-mode", "gui"]
    command.extend(extra_args or [])
    command.extend(["-source", str(script_name)])
    return self.command_runner.launch(command, cwd=cwd)
