import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from agent_reports import render_markdown_document_html
from artifact_manifest import utc_timestamp


SCHEMA_VERSION = 1
REPORT_DIRECTORY = "environment-report"
MINIMUM_PYTHON = (3, 11)
STATUS_PRIORITY = {"PASS": 0, "WARN": 1, "FAIL": 2}


def _clean_text(value):
    return " ".join(str(value or "").split())


def _table_text(value):
    return _clean_text(value).replace("|", "\\|")


def _run_version_command(agent, command):
    try:
        result = agent.command_runner.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (
        AttributeError,
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
        ValueError,
    ) as exc:
        return False, _clean_text(exc)

    output = _clean_text(result.stdout) or _clean_text(result.stderr)
    return result.returncode == 0, output


def _check_python(version_info, python_executable):
    version = tuple(int(part) for part in version_info[:3])
    version_text = ".".join(str(part) for part in version)
    if version >= MINIMUM_PYTHON:
        return {
            "name": "Python",
            "status": "PASS",
            "detail": "版本 {}，可执行文件 {}。".format(
                version_text,
                python_executable,
            ),
            "remediation": "无需处理。",
        }
    return {
        "name": "Python",
        "status": "FAIL",
        "detail": "版本 {} 低于最低要求 3.11。".format(version_text),
        "remediation": "安装 Python 3.11 或更高版本，并确认 CLI 使用新的解释器。",
    }


def _check_git(agent, which):
    command = which("git")
    if not command:
        return {
            "name": "Git",
            "status": "FAIL",
            "detail": "未在 PATH 中检测到 Git。",
            "remediation": "安装 Git，并将 git 可执行文件加入 PATH。",
        }

    ok, version_text = _run_version_command(agent, [command, "--version"])
    if ok:
        return {
            "name": "Git",
            "status": "PASS",
            "detail": "{}；命令 {}。".format(
                version_text or "Git 命令可执行",
                command,
            ),
            "remediation": "无需处理。",
        }
    return {
        "name": "Git",
        "status": "FAIL",
        "detail": "Git 命令执行失败：{}。".format(version_text or "无版本输出"),
        "remediation": "检查 Git 安装、PATH 和当前用户的执行权限。",
    }


def _check_vivado(agent):
    try:
        command = agent.resolve_vivado_command()
    except (AttributeError, OSError, ValueError) as exc:
        command = None
        resolution_error = _clean_text(exc)
    else:
        resolution_error = ""

    if not command:
        detail = "未检测到 Vivado 命令。"
        if resolution_error:
            detail = "{} 解析错误：{}。".format(detail, resolution_error)
        return {
            "name": "Vivado",
            "status": "WARN",
            "detail": detail,
            "remediation": (
                "安装 Vivado，或将 vivado 加入 PATH；Windows 也可使用受支持的 "
                "Vivado/bin/vivado.bat 安装路径。"
            ),
        }

    ok, version_text = _run_version_command(agent, [command, "-version"])
    version_banner_found = bool(
        re.search(r"\bVivado\s+v?\d{4}\.\d+\b", version_text, re.IGNORECASE)
    )
    if ok or version_banner_found:
        return {
            "name": "Vivado",
            "status": "PASS",
            "detail": "{}；命令 {}。".format(
                version_text or "Vivado 命令可执行",
                command,
            ),
            "remediation": "无需处理。",
        }
    return {
        "name": "Vivado",
        "status": "WARN",
        "detail": "已解析命令 {}，但版本检查失败：{}。".format(
            command,
            version_text or "无版本输出",
        ),
        "remediation": "检查 Vivado 安装完整性、许可证环境和当前用户的执行权限。",
    }


def _check_waveform(agent):
    try:
        rwave_command = agent.resolve_rwave_command()
    except (AttributeError, OSError, ValueError) as exc:
        rwave_command = None
        resolution_error = _clean_text(exc)
    else:
        resolution_error = ""

    if rwave_command:
        ok, version_text = _run_version_command(
            agent,
            [rwave_command, "--version"],
        )
        if ok:
            return {
                "name": "RWave / VCD_ANALYZER",
                "status": "PASS",
                "detail": "RWave 可用：{}；命令 {}。".format(
                    version_text or "版本命令执行成功",
                    rwave_command,
                ),
                "remediation": "无需处理。",
            }

    try:
        analyzer_path = Path(agent.resolve_vcd_analyzer_path())
    except (AttributeError, OSError, ValueError):
        analyzer_path = Path()
    if analyzer_path.is_file():
        return {
            "name": "RWave / VCD_ANALYZER",
            "status": "PASS",
            "detail": "RWave 不可用，已确认 VCD_ANALYZER fallback：{}。".format(
                analyzer_path,
            ),
            "remediation": "可继续使用 fallback；如需批处理 JSON 性能，可安装 RWave。",
        }

    detail = "未检测到 RWave，且 VCD_ANALYZER fallback 不存在。"
    if resolution_error:
        detail = "{} RWave 解析错误：{}。".format(detail, resolution_error)
    return {
        "name": "RWave / VCD_ANALYZER",
        "status": "WARN",
        "detail": detail,
        "remediation": (
            "设置 RWAVE_BIN、将 rwave 加入 PATH，或恢复 "
            "VCD_ANALYZER-main/VCD_ANALYZER-main/vcd_analyzer.py。"
        ),
    }


def _check_output_directory(report_dir):
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "environment_report.md"
    with report_path.open("a", encoding="utf-8"):
        pass
    return {
        "name": "输出目录权限",
        "status": "PASS",
        "detail": "目录可创建且可写：{}。".format(report_dir),
        "remediation": "无需处理。",
    }


def _check_gui(env, system_name):
    if system_name == "Windows":
        session_name = env.get("SESSIONNAME") or env.get("WT_SESSION")
        available = bool(session_name and str(session_name).lower() != "services")
        detail = (
            "检测到交互式 Windows 会话：{}。".format(session_name)
            if available
            else "未检测到交互式 Windows 会话标记。"
        )
    else:
        display = env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")
        available = bool(display)
        detail = (
            "检测到图形显示环境：{}。".format(display)
            if available
            else "未检测到 DISPLAY 或 WAYLAND_DISPLAY。"
        )

    return {
        "name": "GUI 前置条件",
        "status": "PASS" if available else "WARN",
        "detail": detail,
        "remediation": (
            "无需处理。"
            if available
            else "在交互式桌面会话中运行 GUI flow，或使用 --no-wave-gui。"
        ),
    }


def collect_environment_checks(
    agent,
    report_dir,
    env=None,
    which=None,
    platform_system=None,
    version_info=None,
    python_executable=None,
):
    env = os.environ if env is None else env
    which = shutil.which if which is None else which
    platform_system = platform.system if platform_system is None else platform_system
    version_info = sys.version_info[:3] if version_info is None else version_info
    python_executable = sys.executable if python_executable is None else python_executable
    output_check = _check_output_directory(report_dir)

    return [
        _check_python(version_info, python_executable),
        _check_git(agent, which),
        _check_vivado(agent),
        _check_waveform(agent),
        output_check,
        _check_gui(env, platform_system()),
    ]


def overall_status(checks):
    return max(
        (check["status"] for check in checks),
        key=lambda status: STATUS_PRIORITY[status],
    )


def render_environment_markdown(checks, status, generated_at):
    if status == "PASS":
        summary = "全部环境前置条件均已满足。"
    elif status == "WARN":
        summary = "基础环境可用，但部分 Vivado、波形或 GUI 能力需要补齐。"
    else:
        summary = "存在阻断项，请先修复 FAIL 检查项。"

    lines = [
        "# 数字 IC Agent 环境预检报告",
        "",
        "- 总体状态：{}".format(status),
        "- 生成时间（UTC）：{}".format(generated_at),
        "- 结论：{}".format(summary),
        "",
        "## 检查结果",
        "",
        "| 检查项 | 状态 | 详情 | 修复建议 |",
        "| --- | --- | --- | --- |",
    ]
    for check in checks:
        lines.append(
            "| {name} | {status} | {detail} | {remediation} |".format(
                name=_table_text(check["name"]),
                status=check["status"],
                detail=_table_text(check["detail"]),
                remediation=_table_text(check["remediation"]),
            )
        )
    lines.extend(
        [
            "",
            "## 状态说明",
            "",
            "- PASS：当前条件已满足。",
            "- WARN：报告可生成，但相关 flow 可能需要降级或人工补齐环境。",
            "- FAIL：基础条件不满足，建议修复后重新运行预检。",
            "",
        ]
    )
    return "\n".join(lines)


def load_environment_manifest(manifest_path):
    if not manifest_path.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "scope": "environment",
            "updated_at": None,
            "runs": [],
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("environment artifact manifest must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported environment artifact manifest schema")
    if manifest.get("scope") != "environment":
        raise ValueError("environment artifact manifest scope mismatch")
    if not isinstance(manifest.get("runs"), list):
        raise ValueError("environment artifact manifest runs must be a list")
    return manifest


def write_environment_manifest(
    manifest_path,
    output_dir,
    status,
    generated_at,
    checks,
    report_paths,
):
    manifest = load_environment_manifest(manifest_path)
    artifacts = []
    for path in report_paths:
        artifacts.append(
            {
                "id": path.stem,
                "path": path.name,
                "status": "PASS",
                "exists": path.is_file(),
                "size_bytes": path.stat().st_size,
            }
        )

    manifest["runs"].append(
        {
            "run_id": uuid.uuid4().hex,
            "flow": "environment-report",
            "status": status,
            "recorded_at": generated_at,
            "command": [
                sys.executable,
                ".trae/agent/agent.py",
                "--environment-report",
                "--output-dir",
                str(output_dir),
            ],
            "checks": checks,
            "artifacts": artifacts,
            "error": None,
        }
    )
    manifest["updated_at"] = generated_at
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def write_environment_report(
    self,
    output_dir="outputs",
    env=None,
    which=None,
    platform_system=None,
    version_info=None,
    python_executable=None,
):
    output_dir = Path(output_dir)
    report_dir = output_dir / REPORT_DIRECTORY
    checks = collect_environment_checks(
        self,
        report_dir,
        env=env,
        which=which,
        platform_system=platform_system,
        version_info=version_info,
        python_executable=python_executable,
    )
    status = overall_status(checks)
    generated_at = utc_timestamp()
    markdown = render_environment_markdown(checks, status, generated_at)

    markdown_path = report_dir / "environment_report.md"
    html_path = report_dir / "environment_report.html"
    manifest_path = report_dir / "artifacts.json"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(
        render_markdown_document_html(
            "数字 IC Agent 环境预检报告",
            markdown,
        ),
        encoding="utf-8",
    )
    write_environment_manifest(
        manifest_path,
        output_dir,
        status,
        generated_at,
        checks,
        [markdown_path, html_path],
    )
    return {
        "status": status,
        "checks": checks,
        "markdown_path": markdown_path,
        "html_path": html_path,
        "manifest_path": manifest_path,
    }
