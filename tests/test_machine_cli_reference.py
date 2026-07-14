from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


REMINDER = (
    "即将检索本地数字 IC 参考库。后续可将 RTL 或项目压缩包放入 "
    "references/inbox/rtl，将 UVM/SVA/验证代码放入 references/inbox/uvm，"
    "将论文放入 references/inbox/papers，将协议和芯片资料放入 "
    "references/inbox/specs，并将对应 LICENSE/NOTICE 放入 "
    "references/inbox/licenses。"
)


def _main() -> object:
    return importlib.import_module("digital_ic_agent._runtime.agent").main


def _call(
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> tuple[int, dict[str, object]]:
    exit_code = _main()([*argv, "--json"])
    captured = capsys.readouterr()
    assert captured.err == ""
    return exit_code, json.loads(captured.out)


def test_reference_cli_reports_empty_and_reminds_once_per_workspace(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    assert _main()(
        ["workspace", "init", "--workspace", str(workspace), "--json"]
    ) == 0
    capsys.readouterr()

    exit_code, first = _call(
        capsys,
        ["reference", "status", "--workspace", str(workspace)],
    )
    assert exit_code == 1
    assert first["error_code"] == "REFERENCE_LIBRARY_EMPTY"
    assert first["data"]["reference_reminder"] == REMINDER
    assert first["data"]["reminder_required"] is True
    assert first["data"]["file_count"] == 0

    exit_code, second = _call(
        capsys,
        ["reference", "status", "--workspace", str(workspace)],
    )
    assert exit_code == 1
    assert second["data"]["reminder_required"] is False


def test_reference_cli_indexes_searches_and_shows_records(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "workspace"
    _main()(["workspace", "init", "--workspace", str(workspace), "--json"])
    capsys.readouterr()
    rtl_dir = workspace / "references" / "inbox" / "rtl"
    rtl_dir.mkdir(parents=True, exist_ok=True)
    (rtl_dir / "priority_encoder.v").write_text(
        "module priority_encoder(input [7:0] req, output [2:0] index); endmodule\n",
        encoding="utf-8",
    )

    exit_code, indexed = _call(
        capsys,
        ["reference", "index", "--workspace", str(workspace)],
    )
    assert exit_code == 0
    assert indexed["data"]["record_count"] == 1

    exit_code, searched = _call(
        capsys,
        [
            "reference",
            "search",
            "--workspace",
            str(workspace),
            "--query",
            "priority encoder",
        ],
    )
    assert exit_code == 0
    record_id = searched["data"]["results"][0]["record_id"]

    exit_code, shown = _call(
        capsys,
        [
            "reference",
            "show",
            "--workspace",
            str(workspace),
            "--record-id",
            record_id,
        ],
    )
    assert exit_code == 0
    assert shown["data"]["record"]["license"] == "LICENSE_UNKNOWN"
    assert shown["data"]["record"]["reuse_policy"] == "CONCEPT_ONLY"
