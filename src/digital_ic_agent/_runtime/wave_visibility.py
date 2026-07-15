import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid {} JSON: {}".format(label, path)) from exc
    if not isinstance(value, dict):
        raise ValueError("{} must be a JSON object: {}".format(label, path))
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported {} schema: {}".format(label, path))
    return value


def _integer(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _number(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _threshold_check(
    check_id: str,
    label: str,
    actual: int | float,
    minimum: int | float,
) -> dict[str, object]:
    return {
        "id": check_id,
        "label": label,
        "actual": actual,
        "minimum": minimum,
        "status": "PASS" if actual >= minimum else "FAIL",
    }


def evaluate_wave_open_check(
    probe_path: Path | str,
    *,
    screenshot_metrics_path: Path | str | None = None,
    min_scope_count: int = 1,
    min_object_count: int = 1,
    min_wave_count: int = 1,
    min_wave_config_count: int = 1,
    min_unique_colors: int = 8,
    min_non_uniform_ratio: float = 0.02,
) -> dict[str, object]:
    probe_file = Path(probe_path)
    probe: dict[str, Any] | None = None
    diagnostics: list[str] = []
    checks: list[dict[str, object]] = []

    if not probe_file.exists():
        runtime_status = "PENDING"
        diagnostics.append("runtime wave probe is missing: {}".format(probe_file))
    else:
        try:
            probe = _load_json_object(probe_file, "wave probe")
        except (OSError, ValueError) as exc:
            runtime_status = "FAIL"
            diagnostics.append(str(exc))
        else:
            wdb_opened = probe.get("wdb_opened") is True
            checks.append(
                {
                    "id": "wdb_opened",
                    "label": "WDB opened",
                    "actual": wdb_opened,
                    "minimum": True,
                    "status": "PASS" if wdb_opened else "FAIL",
                }
            )
            checks.extend(
                [
                    _threshold_check(
                        "scope_count",
                        "Scope count",
                        _integer(probe.get("scope_count")),
                        min_scope_count,
                    ),
                    _threshold_check(
                        "object_count",
                        "Object count",
                        _integer(probe.get("object_count")),
                        min_object_count,
                    ),
                    _threshold_check(
                        "wave_count",
                        "Wave count",
                        _integer(probe.get("wave_count")),
                        min_wave_count,
                    ),
                    _threshold_check(
                        "wave_config_count",
                        "Wave config count",
                        _integer(probe.get("wave_config_count")),
                        min_wave_config_count,
                    ),
                ]
            )
            runtime_status = (
                "PASS"
                if all(item["status"] == "PASS" for item in checks)
                else "FAIL"
            )
            probe_diagnostics = probe.get("diagnostics", [])
            if isinstance(probe_diagnostics, list):
                diagnostics.extend(str(item) for item in probe_diagnostics)

    metrics_file = (
        Path(screenshot_metrics_path)
        if screenshot_metrics_path is not None
        else None
    )
    screenshot_metrics: dict[str, Any] | None = None
    screenshot_checks: list[dict[str, object]] = []
    if metrics_file is None or not metrics_file.exists():
        screenshot_status = "PENDING"
    else:
        try:
            screenshot_metrics = _load_json_object(
                metrics_file,
                "wave screenshot metrics",
            )
        except (OSError, ValueError) as exc:
            screenshot_status = "FAIL"
            diagnostics.append(str(exc))
        else:
            screenshot_checks.extend(
                [
                    _threshold_check(
                        "width",
                        "Screenshot width",
                        _integer(screenshot_metrics.get("width")),
                        1,
                    ),
                    _threshold_check(
                        "height",
                        "Screenshot height",
                        _integer(screenshot_metrics.get("height")),
                        1,
                    ),
                    _threshold_check(
                        "sampled_pixels",
                        "Sampled pixels",
                        _integer(screenshot_metrics.get("sampled_pixels")),
                        1,
                    ),
                    _threshold_check(
                        "unique_colors",
                        "Unique sampled colors",
                        _integer(screenshot_metrics.get("unique_colors")),
                        min_unique_colors,
                    ),
                    _threshold_check(
                        "non_uniform_ratio",
                        "Non-uniform pixel ratio",
                        _number(screenshot_metrics.get("non_uniform_ratio")),
                        min_non_uniform_ratio,
                    ),
                ]
            )
            screenshot_status = (
                "PASS"
                if all(item["status"] == "PASS" for item in screenshot_checks)
                else "FAIL"
            )

    if runtime_status == "FAIL" or screenshot_status == "FAIL":
        status = "FAIL"
    elif runtime_status == "PASS":
        status = "PASS"
    else:
        status = "PENDING"
    visible = runtime_status == "PASS" and screenshot_status != "FAIL"
    return {
        "status": status,
        "runtime_status": runtime_status,
        "screenshot_status": screenshot_status,
        "visible": visible,
        "probe_path": probe_file,
        "screenshot_metrics_path": metrics_file,
        "probe": probe,
        "screenshot_metrics": screenshot_metrics,
        "checks": checks,
        "screenshot_checks": screenshot_checks,
        "diagnostics": diagnostics,
    }


def _tcl_text(value: str) -> str:
    return str(value).replace("\\", "/").replace("{", "\\{").replace("}", "\\}")


def render_wave_open_probe_tcl(
    report_relative_path: str,
    *,
    target_name: str,
    flow_name: str,
) -> str:
    script = r'''
set wave_probe_path [file normalize [file join $script_dir {__REPORT_PATH__}]]
set wave_probe_diagnostics {}
set wave_probe_scope_count 0
set wave_probe_object_count 0
set wave_probe_wave_count 0
set wave_probe_wave_config_count 0
if {[catch {set wave_probe_scope_count [llength [get_scopes -r *]]} wave_probe_error]} {
    lappend wave_probe_diagnostics "get_scopes: $wave_probe_error"
}
if {[catch {set wave_probe_object_count [llength [get_objects -r *]]} wave_probe_error]} {
    lappend wave_probe_diagnostics "get_objects: $wave_probe_error"
}
if {[catch {set wave_probe_wave_count [llength [get_waves -quiet *]]} wave_probe_error]} {
    lappend wave_probe_diagnostics "get_waves: $wave_probe_error"
}
if {[catch {set wave_probe_current_config [current_wave_config]} wave_probe_error]} {
    lappend wave_probe_diagnostics "current_wave_config: $wave_probe_error"
} elseif {$wave_probe_current_config ne ""} {
    set wave_probe_wave_config_count 1
}
file mkdir [file dirname $wave_probe_path]
set wave_probe_fh [open $wave_probe_path w]
puts $wave_probe_fh "{"
puts $wave_probe_fh "  \"schema_version\": 1,"
puts $wave_probe_fh "  \"target_name\": \"__TARGET_NAME__\","
puts $wave_probe_fh "  \"flow_name\": \"__FLOW_NAME__\","
puts $wave_probe_fh "  \"wave_database\": \"$wave_db\","
puts $wave_probe_fh "  \"wdb_opened\": true,"
puts $wave_probe_fh "  \"scope_count\": $wave_probe_scope_count,"
puts $wave_probe_fh "  \"object_count\": $wave_probe_object_count,"
puts $wave_probe_fh "  \"wave_count\": $wave_probe_wave_count,"
puts $wave_probe_fh "  \"wave_config_count\": $wave_probe_wave_config_count,"
puts $wave_probe_fh "  \"diagnostics\": \["
set wave_probe_index 0
set wave_probe_total [llength $wave_probe_diagnostics]
foreach wave_probe_item $wave_probe_diagnostics {
    incr wave_probe_index
    set wave_probe_suffix [expr {$wave_probe_index < $wave_probe_total ? "," : ""}]
    puts $wave_probe_fh "    \"$wave_probe_item\"$wave_probe_suffix"
}
puts $wave_probe_fh "  \]"
puts $wave_probe_fh "}"
close $wave_probe_fh
puts "Wave visibility probe: $wave_probe_path"
'''
    return (
        script.replace("__REPORT_PATH__", _tcl_text(report_relative_path))
        .replace("__TARGET_NAME__", _tcl_text(target_name))
        .replace("__FLOW_NAME__", _tcl_text(flow_name))
    )


def render_window_capture_script(
    *,
    screenshot_name: str,
    metrics_name: str,
) -> str:
    script = r'''# Automated foreground-window waveform capture
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class WaveCaptureNative {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
}
"@

$output = Join-Path $PSScriptRoot "__SCREENSHOT_NAME__"
$metricsOutput = Join-Path $PSScriptRoot "__METRICS_NAME__"
$hwnd = [WaveCaptureNative]::GetForegroundWindow()
if ($hwnd -eq [IntPtr]::Zero) {
    throw "No foreground window is available for capture."
}
$rect = New-Object WaveCaptureNative+RECT
if (-not [WaveCaptureNative]::GetWindowRect($hwnd, [ref]$rect)) {
    throw "Failed to read foreground window bounds."
}
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) {
    throw "Foreground window bounds are empty."
}
$titleBuffer = New-Object System.Text.StringBuilder 1024
[void][WaveCaptureNative]::GetWindowText($hwnd, $titleBuffer, $titleBuffer.Capacity)
$windowTitle = $titleBuffer.ToString()

$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$origin = New-Object System.Drawing.Point $rect.Left, $rect.Top
$graphics.CopyFromScreen(
    $origin,
    [System.Drawing.Point]::Empty,
    (New-Object System.Drawing.Size $width, $height)
)
$bitmap.Save($output, [System.Drawing.Imaging.ImageFormat]::Png)

$stepX = [Math]::Max(1, [int][Math]::Floor($width / 128.0))
$stepY = [Math]::Max(1, [int][Math]::Floor($height / 128.0))
$baseline = $bitmap.GetPixel(0, 0).ToArgb()
$colors = New-Object 'System.Collections.Generic.HashSet[int]'
$sampledPixels = 0
$nonUniformPixels = 0
for ($y = 0; $y -lt $height; $y += $stepY) {
    for ($x = 0; $x -lt $width; $x += $stepX) {
        $argb = $bitmap.GetPixel($x, $y).ToArgb()
        [void]$colors.Add($argb)
        $sampledPixels += 1
        if ($argb -ne $baseline) {
            $nonUniformPixels += 1
        }
    }
}
$nonUniformRatio = if ($sampledPixels -gt 0) {
    $nonUniformPixels / [double]$sampledPixels
} else {
    0.0
}
$metrics = [ordered]@{
    schema_version = 1
    captured_at = [DateTime]::UtcNow.ToString("o")
    window_title = $windowTitle
    width = $width
    height = $height
    sampled_pixels = $sampledPixels
    unique_colors = $colors.Count
    non_uniform_pixels = $nonUniformPixels
    non_uniform_ratio = $nonUniformRatio
}
$metrics | ConvertTo-Json | Set-Content -Encoding UTF8 $metricsOutput
$graphics.Dispose()
$bitmap.Dispose()
Write-Host "Saved waveform screenshot to $output"
Write-Host "Saved screenshot metrics to $metricsOutput"
'''
    return (
        script.replace("__SCREENSHOT_NAME__", str(screenshot_name))
        .replace("__METRICS_NAME__", str(metrics_name))
    )
