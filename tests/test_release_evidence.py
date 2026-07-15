import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "scripts" / "generate_quality_summary.py"
RELEASE_CHECK_PATH = ROOT / "scripts" / "check_release_tree.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "python-quality.yml"
GITATTRIBUTES_PATH = ROOT / ".gitattributes"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_quality_summary_is_deterministic_across_runtime_variation():
    generator = _load_module("quality_summary_determinism", GENERATOR_PATH)
    coverage = {"line_rate": 0.9, "branch_rate": 0.8}
    first = generator.build_quality_summary(
        {"tests": 10, "failures": 0, "errors": 0, "skipped": 0, "time": 1.0},
        coverage,
        60,
        {"failure_handling": 2},
    )
    second = generator.build_quality_summary(
        {"tests": 10, "failures": 0, "errors": 0, "skipped": 0, "time": 9.9},
        coverage,
        60,
        {"failure_handling": 2},
    )

    assert first == second
    assert "Pytest runtime seconds" not in first


def test_quality_generator_defaults_to_canonical_artifacts():
    generator = _load_module("quality_summary_defaults", GENERATOR_PATH)

    parser = generator.build_parser()
    args = parser.parse_args([])

    assert args.junitxml == ROOT / ".tmp" / "pytest-results.xml"
    assert args.coverage_xml == ROOT / "coverage.xml"
    assert args.minimum_line_rate == 0.90
    assert args.minimum_branch_rate == 0.80


def test_release_coverage_gate_checks_line_and_branch_rates_independently():
    generator = _load_module("quality_summary_coverage_gate", GENERATOR_PATH)

    assert generator.coverage_gate_violations(
        {"line_rate": 0.90, "branch_rate": 0.80},
        minimum_line_rate=0.90,
        minimum_branch_rate=0.80,
    ) == []
    violations = generator.coverage_gate_violations(
        {"line_rate": 0.899, "branch_rate": 0.799},
        minimum_line_rate=0.90,
        minimum_branch_rate=0.80,
    )

    assert any("line coverage" in item for item in violations)
    assert any("branch coverage" in item for item in violations)


def test_release_tree_gate_classifies_source_and_generated_changes():
    assert RELEASE_CHECK_PATH.is_file()
    checker = _load_module("release_tree_checker", RELEASE_CHECK_PATH)

    source_violations = checker.find_release_violations(
        [" M .trae/agent/agent.py", "?? tests/test_new_behavior.py"],
        phase="source",
    )
    generated_violations = checker.find_release_violations(
        [" M README.md", " M docs/generated/quality_summary.md"],
        phase="generated",
    )

    assert any("source tree is not clean" in item for item in source_violations)
    assert any("untracked test" in item for item in source_violations)
    assert any("generated quality files are stale" in item for item in generated_violations)


def test_python_quality_workflow_runs_both_release_tree_phases():
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "scripts/check_release_tree.py --phase source" in workflow
    assert "scripts/check_release_tree.py --phase generated" in workflow
    assert workflow.index("--phase source") < workflow.index("Pytest with coverage")
    assert workflow.index("--phase generated") > workflow.index("Generate test module size report")


def test_repository_declares_cross_platform_line_endings():
    attributes = GITATTRIBUTES_PATH.read_text(encoding="utf-8")

    assert "* text=auto" in attributes
    for extension in ("*.py", "*.yml", "*.yaml", "*.toml", "*.json", "*.md"):
        assert f"{extension} text eol=lf" in attributes
    assert "*.bat text eol=crlf" in attributes
