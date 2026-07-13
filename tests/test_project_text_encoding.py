from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOJIBAKE_TOKENS = (
    "鐢" + "?Digital",
    "鍩" + "轰簬",
    "鐩" + "爣",
    "娴" + "犺法婀",
    "閹" + "芥",
)


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


def test_runtime_python_text_has_no_question_mark_replacement_runs():
    failures = []
    for source_root in (ROOT / "src" / "digital_ic_agent" / "_runtime", ROOT / "src" / "digital_ic_agent"):
        for path in source_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "???" in text:
                failures.append(str(path.relative_to(ROOT)))

    assert not failures, "Question-mark replacement runs found:\n{}".format(
        "\n".join(failures)
    )


def test_user_visible_project_text_has_no_known_mojibake_sequences():
    paths = [ROOT / "README.md"]
    for source_root in (
        ROOT / "src" / "digital_ic_agent" / "_runtime",
        ROOT / "src" / "digital_ic_agent",
        ROOT / "docs" / "generated",
    ):
        for suffix in ("*.py", "*.json", "*.md", "*.html"):
            paths.extend(source_root.rglob(suffix))

    failures = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        matches = [token for token in MOJIBAKE_TOKENS if token in text]
        if matches:
            failures.append("{}: {}".format(path.relative_to(ROOT), matches))

    assert not failures, "Known mojibake sequences found:\n{}".format("\n".join(failures))
