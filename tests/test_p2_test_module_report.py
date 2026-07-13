import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "generate_test_module_report.py"


def generate_report(
    tmp_path: Path,
    *,
    tests_dir: Path | None = None,
    line_limit: int = 1000,
) -> tuple[dict, str]:
    output_dir = tmp_path / "generated"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--tests-dir",
            str(tests_dir or ROOT / "tests"),
            "--line-limit",
            str(line_limit),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(
        (output_dir / "test_module_report.json").read_text(encoding="utf-8")
    )
    markdown = (output_dir / "test_module_report.md").read_text(encoding="utf-8")
    return report, markdown


def test_p2_test_module_report_lists_over_limit_modules_as_unfinished(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_small.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    (tests_dir / "test_large.py").write_text(
        "\n".join("# line" for _ in range(5)),
        encoding="utf-8",
    )

    report, markdown = generate_report(
        tmp_path,
        tests_dir=tests_dir,
        line_limit=3,
    )

    assert report["status"] == "WARN"
    assert report["line_limit"] == 3
    assert report["module_count"] == 2
    assert report["over_limit_count"] == 1
    assert report["unfinished_items"] == [
        {
            "path": "test_large.py",
            "lines": 5,
            "reason": "test module exceeds P2 line limit",
        }
    ]
    assert "| `test_large.py` | 5 | OVER_LIMIT |" in markdown


def test_p2_test_module_report_current_repo_has_only_domain_modules(tmp_path):
    report, _markdown = generate_report(tmp_path)
    module_paths = {item["path"] for item in report["modules"]}

    assert report["status"] == "PASS"
    assert report["module_count"] == len(list((ROOT / "tests").glob("test_*.py")))
    assert report["over_limit_count"] == 0
    assert all(item["lines"] <= 1000 for item in report["modules"])
    assert "tests/test_agent.py" not in module_paths
    assert "tests/test_architecture_runtime.py" not in module_paths
    assert report["unfinished_items"] == []
    assert report["split_candidates"] == []
    assert report["deletion_verification"] == []
    assert report["unmigrated_tests"] == []


def test_p2_test_module_report_marks_over_limit_tests_as_unmigrated(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_pending.py").write_text(
        "def test_pending():\n"
        "    value = 1\n"
        "    assert value\n"
        "\n"
        "# fifth line\n",
        encoding="utf-8",
    )

    report, _markdown = generate_report(
        tmp_path,
        tests_dir=tests_dir,
        line_limit=3,
    )

    assert report["unmigrated_tests"] == [
        {"source": "test_pending.py", "tests": ["test_pending"]}
    ]


def test_p2_test_module_report_final_markdown_has_no_pending_deletions(tmp_path):
    _report, markdown = generate_report(tmp_path)

    assert "## Unfinished Items\n\n- None." in markdown
    assert "## Unmigrated Tests\n\n- None." in markdown
    assert "## Split Candidates\n\n- None." in markdown
    assert "## Deletion Verification\n\n- None." in markdown
    assert "Status: `PASS`" in markdown
