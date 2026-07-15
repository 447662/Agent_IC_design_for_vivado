from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.reference_library import (  # noqa: E402
    ReferenceLibraryError,
    index_reference_library,
    inspect_zip_archive,
    reference_status,
    search_references,
    show_reference,
)


def test_reference_status_creates_layout_and_reports_empty(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    status = reference_status(workspace)

    assert status["status"] == "REFERENCE_LIBRARY_EMPTY"
    assert status["file_count"] == 0
    assert status["license_missing_count"] == 0
    assert status["index_status"] == "MISSING"
    assert set(status["directories"]) == {
        "rtl",
        "uvm",
        "papers",
        "specs",
        "licenses",
        "cache",
        "index",
        "catalog",
    }
    assert all(Path(path).is_dir() for path in status["directories"].values())


def test_reference_index_search_show_uses_fts5_and_license_guard(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    rtl_dir = workspace / "references" / "inbox" / "rtl"
    rtl_dir.mkdir(parents=True)
    rtl_path = rtl_dir / "pulse_sync.sv"
    rtl_path.write_text(
        "// pulse synchronizer for clock domain crossing\n"
        "module pulse_sync(input logic src_pulse, output logic dst_pulse);\n"
        "endmodule\n",
        encoding="utf-8",
    )

    indexed = index_reference_library(workspace)
    results = search_references(workspace, "pulse synchronizer")

    assert indexed["status"] == "CURRENT"
    assert indexed["record_count"] >= 1
    assert indexed["engine"] == "sqlite-fts5-bm25"
    assert results["index_status"] == "CURRENT"
    assert results["results"]
    record = results["results"][0]
    assert record["module"] == "pulse_sync"
    assert record["license"] == "LICENSE_UNKNOWN"
    assert record["reuse_policy"] == "CONCEPT_ONLY"
    shown = show_reference(workspace, record["record_id"])
    assert shown["record"]["sha256"]
    assert "pulse synchronizer" in shown["record"]["content"]

    rtl_path.write_text(
        rtl_path.read_text(encoding="utf-8") + "// changed\n",
        encoding="utf-8",
    )
    assert reference_status(workspace)["index_status"] == "STALE"


@pytest.mark.parametrize("kind", ["corrupt", "traversal", "absolute"])
def test_reference_index_rejects_unsafe_or_corrupt_zip(
    tmp_path: Path,
    kind: str,
) -> None:
    workspace = tmp_path / "workspace"
    rtl_dir = workspace / "references" / "inbox" / "rtl"
    rtl_dir.mkdir(parents=True)
    archive_path = rtl_dir / "unsafe.zip"
    if kind == "corrupt":
        archive_path.write_bytes(b"not a zip")
    else:
        member = "../escape.sv" if kind == "traversal" else "/absolute.sv"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr(member, "module escape; endmodule\n")

    with pytest.raises(ReferenceLibraryError) as captured:
        index_reference_library(workspace)

    assert captured.value.code in {"ARCHIVE_INVALID", "ARCHIVE_UNSAFE"}
    assert not (tmp_path / "escape.sv").exists()


def test_actual_openrtlset_archive_is_inventory_only_and_has_no_rtl_samples() -> None:
    inventory = inspect_zip_archive(ROOT / "OpenRTLSet-main.zip")

    assert inventory["entry_count"] == 375
    assert inventory["rtl_entry_count"] == 0
    assert inventory["has_repository_license"] is True
    assert inventory["executed"] is False
    assert inventory["extracted"] is False


def test_reference_generated_and_third_party_paths_are_git_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for path in (
        "/references/inbox/",
        "/references/cache/",
        "/references/index/",
        "/references/catalog/",
        "*.pdf",
    ):
        assert path in gitignore
