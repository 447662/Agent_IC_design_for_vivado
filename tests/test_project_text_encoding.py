from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_owned_text_files_are_valid_utf8():
    paths = [ROOT / "README.md"]
    paths.extend((ROOT / ".trae").rglob("*.py"))
    paths.extend((ROOT / ".trae").rglob("*.json"))
    paths.extend((ROOT / ".trae").rglob("*.md"))
    paths.extend(
        path
        for path in (ROOT / "docs").rglob("*.md")
        if "tools_archive" not in path.parts
    )

    for path in paths:
        text = path.read_bytes().decode("utf-8")
        assert "\ufffd" not in text, path
