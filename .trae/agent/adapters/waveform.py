from typing import Any
import json
import sys
from pathlib import Path


RWAVE_ONLY_FORMATS = {".fst", ".ghw"}


def _waveform_suffix(args: Any) -> Any:
    if len(args) < 2:
        return ""
    return Path(str(args[1])).suffix.lower()


def _raise_rwave_required(waveform_suffix: Any, error: Any) -> Any:
    format_name = waveform_suffix.lstrip(".").upper() or "This"
    message = "{} waveform requires RWaveAnalyzer: {}".format(format_name, error)
    if isinstance(error, FileNotFoundError):
        raise FileNotFoundError(message) from error
    raise RuntimeError(message) from error


def run_rwave_json(self: Any, *args: Any) -> Any:
    rwave_command = self.resolve_rwave_command()
    if not rwave_command:
        raise FileNotFoundError("RWaveAnalyzer rwave binary not found")

    result = self.command_runner.run(
        [rwave_command, "--json", *[str(arg) for arg in args]],
        cwd=self.project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "rwave failed"
        raise RuntimeError(message)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("rwave returned invalid JSON: {}".format(exc)) from exc
    data["_waveform_backend"] = "rwave"
    return data


def run_rwave_batch_json(self: Any, waveform_path: Any, command_lines: Any) -> Any:
    rwave_command = self.resolve_rwave_command()
    if not rwave_command:
        raise FileNotFoundError("RWaveAnalyzer rwave binary not found")

    result = self.command_runner.run(
        [rwave_command, "--batch", "--json", str(waveform_path)],
        input="\n".join(str(line) for line in command_lines) + "\n",
        cwd=self.project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "rwave batch failed"
        )
        raise RuntimeError(message)

    parsed = {}
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("rwave batch returned invalid JSON: {}".format(exc)) from exc

        result_id = row.get("id")
        if not result_id:
            raise RuntimeError("rwave batch result missing id")
        if row.get("ok") is False:
            error = row.get("error") or "rwave batch command failed"
            raise RuntimeError("{}: {}".format(result_id, error))

        item = row.get("result", {})
        if isinstance(item, dict):
            item["_waveform_backend"] = "rwave"
        parsed[result_id] = item

    return parsed


def run_vcd_analyzer_json(self: Any, *args: Any) -> Any:
    analyzer_path = self.resolve_vcd_analyzer_path()
    if not analyzer_path.exists():
        raise FileNotFoundError("VCD analyzer not found: {}".format(analyzer_path))

    result = self.command_runner.run(
        [
            sys.executable,
            str(analyzer_path),
            "--json",
            *[str(arg) for arg in args],
        ],
        cwd=self.project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "vcd_analyzer failed"
        )
        raise RuntimeError(message)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("vcd_analyzer returned invalid JSON: {}".format(exc)) from exc
    data["_waveform_backend"] = "vcd_analyzer"
    return data


def run_waveform_analyzer_json(self: Any, *args: Any, backend: Any="auto") -> Any:
    backend = str(backend or "auto").strip().lower()
    waveform_suffix = _waveform_suffix(args)
    if backend in ("vcd", "vcd_analyzer", "vcd-analyzer"):
        if waveform_suffix in RWAVE_ONLY_FORMATS:
            raise ValueError(
                "VCD_ANALYZER only supports VCD waveforms; {} requires "
                "RWaveAnalyzer".format(waveform_suffix or "this format")
            )
        return self.run_vcd_analyzer_json(*args)
    if backend == "rwave":
        return self.run_rwave_json(*args)
    if backend != "auto":
        raise ValueError("Unsupported waveform backend: {}".format(backend))

    try:
        return self.run_rwave_json(*args)
    except FileNotFoundError as rwave_error:
        if waveform_suffix in RWAVE_ONLY_FORMATS:
            _raise_rwave_required(waveform_suffix, rwave_error)
        return self.run_vcd_analyzer_json(*args)
    except RuntimeError as rwave_error:
        if waveform_suffix in RWAVE_ONLY_FORMATS:
            _raise_rwave_required(waveform_suffix, rwave_error)
        try:
            data = self.run_vcd_analyzer_json(*args)
        except (FileNotFoundError, RuntimeError):
            raise rwave_error from None
        data["_waveform_backend_fallback_reason"] = str(rwave_error)
        return data
