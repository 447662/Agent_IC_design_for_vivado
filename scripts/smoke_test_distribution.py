from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ARTIFACT_PATTERNS = {
    "wheel": "*.whl",
    "sdist": "*.tar.gz",
}


def find_distribution(artifact_dir: Path, kind: str) -> Path:
    pattern = ARTIFACT_PATTERNS[kind]
    candidates = sorted(artifact_dir.glob(pattern))
    if len(candidates) != 1:
        raise ValueError(
            "Expected exactly one {} in {}, found {}".format(
                kind,
                artifact_dir,
                len(candidates),
            )
        )
    return candidates[0].resolve()


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def venv_entrypoint(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "digital-ic-agent.exe"
    return venv_dir / "bin" / "digital-ic-agent"


def run_checked(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed ({}):\n{}\n{}".format(
                result.returncode,
                " ".join(command),
                result.stderr.strip() or result.stdout.strip(),
            )
        )
    return result


def smoke_test_distribution(
    artifact: Path,
    work_dir: Path,
    *,
    uv_executable: str,
) -> dict[str, object]:
    if work_dir.exists():
        raise ValueError("Distribution smoke work directory already exists: {}".format(work_dir))
    work_dir.mkdir(parents=True)
    venv_dir = work_dir / "venv"
    outside_source_dir = work_dir / "outside-source"
    outside_source_dir.mkdir()
    cache_dir = work_dir / "uv-cache"

    run_checked(
        [
            uv_executable,
            "--cache-dir",
            str(cache_dir),
            "venv",
            "--python",
            sys.executable,
            str(venv_dir),
        ],
        cwd=outside_source_dir,
    )
    python_executable = venv_python(venv_dir)
    run_checked(
        [
            uv_executable,
            "--cache-dir",
            str(cache_dir),
            "pip",
            "install",
            "--python",
            str(python_executable),
            "--no-deps",
            str(artifact),
        ],
        cwd=outside_source_dir,
    )

    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = (
        "import inspect, json\n"
        "from importlib.resources import files\n"
        "from digital_ic_agent.agent import DigitalICAgent\n"
        "agent = DigitalICAgent()\n"
        "root = files('digital_ic_agent')\n"
        "payload = {\n"
        "  'module': DigitalICAgent.__module__,\n"
        "  'source': inspect.getfile(DigitalICAgent),\n"
        "  'targets': sorted(agent.targets),\n"
        "  'agent_config': root.joinpath('_runtime', 'agent.json').is_file(),\n"
        "  'target_data': all(root.joinpath('_runtime', 'targets', name).is_file() for name in (\n"
        "    'async_fifo.json', 'round_robin_arbiter.json', 'sync_fifo.json')),\n"
        "  'skills': all(root.joinpath('skills', name, 'SKILL.md').is_file() for name in (\n"
        "    'digital-ic-designer', 'digital-ic-rtl-designer', 'digital-ic-verifier')),\n"
        "}\n"
        "agent.close()\n"
        "print(json.dumps(payload))\n"
    )
    probe_result = run_checked(
        [str(python_executable), "-I", "-B", "-c", probe],
        cwd=outside_source_dir,
        environment=environment,
    )
    payload = json.loads(probe_result.stdout.strip().splitlines()[-1])
    expected_targets = ["async-fifo", "round-robin-arbiter", "sync-fifo"]
    if payload["module"] != "digital_ic_agent._runtime.agent":
        raise RuntimeError("Installed public facade resolved to unexpected runtime")
    if payload["targets"] != expected_targets:
        raise RuntimeError("Installed distribution did not discover all built-in targets")
    if not all(payload[key] for key in ("agent_config", "target_data", "skills")):
        raise RuntimeError("Installed distribution is missing required package data")

    cli_result = run_checked(
        [str(venv_entrypoint(venv_dir)), "--list-targets"],
        cwd=outside_source_dir,
        environment=environment,
    )
    if not all(target in cli_result.stdout for target in expected_targets):
        raise RuntimeError("Installed CLI did not list all built-in targets")

    return {
        "artifact": artifact.name,
        "kind": "wheel" if artifact.suffix == ".whl" else "sdist",
        "module": payload["module"],
        "source": payload["source"],
        "targets": payload["targets"],
        "package_data": "PASS",
        "cli": "PASS",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install and smoke test one built distribution outside the source tree."
    )
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--kind", choices=tuple(ARTIFACT_PATTERNS), required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--uv-executable", default=shutil.which("uv") or "uv")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    artifact = find_distribution(args.artifact_dir, args.kind)
    payload = smoke_test_distribution(
        artifact,
        args.work_dir.resolve(),
        uv_executable=args.uv_executable,
    )
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
