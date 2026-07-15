from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.reference_library import (  # noqa: E402
    ReferenceLibraryError,
    fetch_openhw_repository,
    index_reference_library,
    search_references,
)


class FakeGitRunner:
    def __init__(self, *, fail_first_clone: bool = False) -> None:
        self.commands: list[list[str]] = []
        self.fail_first_clone = fail_first_clone
        self.clone_calls = 0

    def __call__(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.commands.append(command)
        if "clone" in command:
            self.clone_calls += 1
            if self.fail_first_clone and self.clone_calls == 1:
                return subprocess.CompletedProcess(
                    command,
                    128,
                    stdout="",
                    stderr="Could not resolve host: github.com",
                )
            target = Path(command[-1])
            target.mkdir(parents=True)
            (target / "LICENSE").write_text(
                "Apache License\nVersion 2.0, January 2004\n",
                encoding="utf-8",
            )
            (target / "NOTICE").write_text("OpenHW notice\n", encoding="utf-8")
            (target / "core.sv").write_text(
                "module core(input logic clk); endmodule\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        if command[-2:] == ["rev-parse", "HEAD"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="a" * 40 + "\n",
                stderr="",
            )
        if command[-3:] == ["remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="https://github.com/openhwgroup/cv32e40p.git\n",
                stderr="",
            )
        raise AssertionError(command)


def test_openhw_fetch_is_shallow_fixed_origin_and_records_provenance(
    tmp_path: Path,
) -> None:
    runner = FakeGitRunner()

    result = fetch_openhw_repository(
        tmp_path,
        "cv32e40p",
        runner=runner,
    )

    clone = runner.commands[0]
    assert clone[:2] == ["git", "clone"]
    assert clone[2:4] == ["--depth", "1"]
    assert "--single-branch" in clone
    assert "https://github.com/openhwgroup/cv32e40p.git" in clone
    assert result["commit"] == "a" * 40
    assert result["license"] == "Apache-2.0"
    assert result["notice_present"] is True
    assert result["executed_repository_code"] is False
    assert result["cache_path"] == str(
        tmp_path.resolve() / "references" / "cache" / "openhwgroup" / "cv32e40p"
    )
    catalog = json.loads(
        (
            tmp_path
            / "references"
            / "catalog"
            / "openhwgroup-repositories.json"
        ).read_text(encoding="utf-8")
    )
    assert catalog["repositories"][0]["commit"] == "a" * 40

    indexed = index_reference_library(tmp_path)
    searched = search_references(tmp_path, "module core")
    assert indexed["record_count"] >= 1
    core = next(item for item in searched["results"] if item["module"] == "core")
    assert core["source"] == "openhwgroup"
    assert core["repository"] == "https://github.com/openhwgroup/cv32e40p.git"
    assert core["commit_sha"] == "a" * 40


def test_openhw_fetch_retries_connection_failure_with_process_proxy(
    tmp_path: Path,
) -> None:
    runner = FakeGitRunner(fail_first_clone=True)

    result = fetch_openhw_repository(tmp_path, "cv32e40p", runner=runner)

    assert result["proxy_retry"] is True
    retry = runner.commands[1]
    assert retry[:6] == [
        "git",
        "-c",
        "http.proxy=http://127.0.0.1:7897",
        "-c",
        "https.proxy=http://127.0.0.1:7897",
        "clone",
    ]
    assert not any(command[1:2] == ["config"] for command in runner.commands)


@pytest.mark.parametrize(
    "repository",
    [
        "../escape",
        "https://github.com/other/repo",
        "openhwgroup/repo",
        "repo;calc",
        "",
    ],
)
def test_openhw_fetch_rejects_arbitrary_repository_inputs(
    tmp_path: Path,
    repository: str,
) -> None:
    runner = FakeGitRunner()

    with pytest.raises(ReferenceLibraryError) as captured:
        fetch_openhw_repository(tmp_path, repository, runner=runner)

    assert captured.value.code == "OPENHW_REPOSITORY_INVALID"
    assert runner.commands == []
