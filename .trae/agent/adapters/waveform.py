import json
import sys


def run_rwave_json(self, *args):
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
        raise RuntimeError("rwave returned invalid JSON: {}".format(exc))
    data["_waveform_backend"] = "rwave"
    return data


def run_rwave_batch_json(self, waveform_path, command_lines):
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
            raise RuntimeError("rwave batch returned invalid JSON: {}".format(exc))

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


def run_vcd_analyzer_json(self, *args):
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
        raise RuntimeError("vcd_analyzer returned invalid JSON: {}".format(exc))
    data["_waveform_backend"] = "vcd_analyzer"
    return data


def run_waveform_analyzer_json(self, *args, backend="auto"):
    backend = str(backend or "auto").strip().lower()
    if backend in ("vcd", "vcd_analyzer", "vcd-analyzer"):
        return self.run_vcd_analyzer_json(*args)
    if backend == "rwave":
        return self.run_rwave_json(*args)
    if backend != "auto":
        raise ValueError("Unsupported waveform backend: {}".format(backend))

    try:
        return self.run_rwave_json(*args)
    except FileNotFoundError:
        return self.run_vcd_analyzer_json(*args)
    except RuntimeError as rwave_error:
        try:
            data = self.run_vcd_analyzer_json(*args)
        except (FileNotFoundError, RuntimeError):
            raise rwave_error
        data["_waveform_backend_fallback_reason"] = str(rwave_error)
        return data
