from __future__ import annotations

import argparse
import subprocess
from collections.abc import Sequence
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_PATHS = ("README.md", "docs/generated/")


def _status_path(entry: str) -> str:
    path = entry[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.replace("\\", "/")


def find_release_violations(
    status_entries: Sequence[str],
    *,
    phase: str,
) -> list[str]:
    if phase not in {"source", "generated"}:
        raise ValueError(f"Unsupported release-tree phase: {phase}")
    entries = [entry for entry in status_entries if entry.strip()]
    violations: list[str] = []
    untracked_tests = sorted(
        _status_path(entry)
        for entry in entries
        if entry.startswith("?? ") and _status_path(entry).startswith("tests/test_")
    )
    if untracked_tests:
        violations.append("untracked test files: {}".format(", ".join(untracked_tests)))
    if phase == "source" and entries:
        violations.append("source tree is not clean before quality generation")
    if phase == "generated":
        stale = sorted(
            _status_path(entry)
            for entry in entries
            if any(
                _status_path(entry) == prefix.rstrip("/")
                or _status_path(entry).startswith(prefix)
                for prefix in GENERATED_PATHS
            )
        )
        if stale:
            violations.append(
                "generated quality files are stale: {}".format(", ".join(stale))
            )
    return violations


def _git_status(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a reproducible release tree.")
    parser.add_argument("--phase", choices=("source", "generated"), required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    violations = find_release_violations(_git_status(args.root), phase=args.phase)
    if violations:
        for violation in violations:
            print(f"RELEASE_TREE_ERROR: {violation}")
        return 1
    print(f"Release tree {args.phase} phase: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
