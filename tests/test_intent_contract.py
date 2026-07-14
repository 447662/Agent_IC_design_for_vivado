from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "intent_contract_cases.json"
SCHEMA_DIR = SRC_DIR / "digital_ic_agent" / "schemas"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from digital_ic_agent._runtime.intent_contract import validate_intents  # noqa: E402


def _base_design() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.design-intent.v1",
        "module": {"name": "stream_counter", "kind": "sequential"},
        "parameters": [
            {"name": "WIDTH", "type": "integer", "default": 8, "minimum": 1}
        ],
        "ports": [
            {"name": "clk", "direction": "input", "width": 1, "semantics": "core clock"},
            {"name": "rst_n", "direction": "input", "width": 1, "semantics": "active-low reset"},
            {"name": "in_data", "direction": "input", "width": "WIDTH", "semantics": "input payload"},
            {"name": "in_valid", "direction": "input", "width": 1, "semantics": "input transfer valid"},
            {"name": "out_data", "direction": "output", "width": "WIDTH", "semantics": "count result"}
        ],
        "clocks": [
            {"name": "core", "signal": "clk", "edge": "rising", "frequency_hz": 100000000}
        ],
        "resets": [
            {"name": "core_reset", "signal": "rst_n", "active_level": "low", "kind": "asynchronous", "clock": "core"}
        ],
        "protocols": [
            {"name": "stream_input", "type": "ready-valid", "role": "sink", "signals": ["in_data", "in_valid"]}
        ],
        "timing": {"latency_cycles": 1, "throughput_per_cycle": 1},
        "exceptional_behavior": ["Ignore in_data when in_valid is low"],
        "implementation_constraints": {"synthesizable": True, "latches_allowed": False},
        "acceptance_criteria": ["Increment once for every asserted in_valid cycle"]
    }


def _base_verification() -> dict[str, Any]:
    return {
        "schema_version": "digital-ic-agent.verification-intent.v1",
        "module": "stream_counter",
        "testbench_top": "tb_stream_counter",
        "source_files": [
            "rtl/stream_counter.sv",
            "uvm/stream_counter_if.sv",
            "uvm/stream_counter_pkg.sv",
            "uvm/tb_stream_counter.sv",
        ],
        "include_dirs": ["uvm"],
        "uvm_enabled": True,
        "timescale": "1ns/1ps",
        "pass_markers": ["STREAM_COUNTER_SCOREBOARD_PASS"],
        "directed_scenarios": [
            {"id": "reset", "description": "Reset clears the counter", "expected": "out_data is zero"}
        ],
        "random_constraints": [
            {"id": "valid_mix", "description": "Randomize in_valid", "signals": ["in_valid"]}
        ],
        "scoreboard": {"enabled": True, "strategy": "cycle-accurate", "compare_signals": ["out_data"]},
        "assertions": [
            {"id": "known_output", "description": "Output remains known", "signals": ["out_data"]}
        ],
        "functional_coverage": [
            {"id": "valid_toggle", "description": "Observe valid high and low", "signals": ["in_valid"]}
        ],
        "code_coverage": {"statement": 90, "branch": 80, "condition": 80, "toggle": 70},
        "coverage_strategy": {
            "code_coverage": True,
            "functional_coverage": True,
            "export_report": True,
            "functional_threshold": 80,
        },
        "iteration_limits": {
            "max_iterations": 3,
            "max_time_seconds": 900,
            "no_progress_limit": 1,
        },
        "exit_criteria": {
            "zero_uvm_errors": True,
            "zero_uvm_fatals": True,
            "scoreboard_pass": True,
            "all_assertions_pass": True,
            "coverage_must_pass": True
        }
    }


@pytest.mark.parametrize(
    ("field", "code"),
    [
        ("testbench_top", "TESTBENCH_TOP_MISSING"),
        ("source_files", "SOURCE_FILES_MISSING"),
        ("pass_markers", "PASS_MARKERS_MISSING"),
        ("coverage_strategy", "COVERAGE_STRATEGY_MISSING"),
        ("iteration_limits", "ITERATION_LIMITS_MISSING"),
    ],
)
def test_verification_execution_policy_must_be_explicit(
    field: str,
    code: str,
) -> None:
    verification = _base_verification()
    del verification[field]

    result = validate_intents(_base_design(), verification)

    assert result.status == "AMBIGUOUS"
    assert code in {issue.code for issue in result.issues}


def test_verification_source_manifest_rejects_workspace_escape() -> None:
    verification = _base_verification()
    verification["source_files"] = ["../outside.sv"]

    result = validate_intents(_base_design(), verification)

    assert result.status == "FAIL"
    assert "SOURCE_PATH_INVALID" in {issue.code for issue in result.issues}


def _resolve(document: dict[str, Any], path: str) -> tuple[Any, str | int]:
    parts = path.split(".")
    current: Any = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    leaf: str | int = int(parts[-1]) if isinstance(current, list) else parts[-1]
    return current, leaf


def _apply(document: dict[str, Any], mutation: dict[str, Any]) -> None:
    parent, leaf = _resolve(document, mutation["path"])
    operation = mutation["op"]
    if operation == "delete":
        del parent[leaf]
    elif operation == "set":
        parent[leaf] = mutation["value"]
    elif operation == "append":
        target = parent[leaf]
        assert isinstance(target, list)
        target.append(mutation["value"])
    else:  # pragma: no cover - fixture contract
        raise AssertionError(operation)


CASES = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_intent_contract_fixtures(case: dict[str, Any]) -> None:
    design = copy.deepcopy(_base_design())
    verification = copy.deepcopy(_base_verification())
    for mutation in case["mutations"]:
        target = design if mutation["document"] == "design" else verification
        _apply(target, mutation)

    result = validate_intents(design, verification)

    assert result.status == case["status"]
    if case["code"] is not None:
        assert case["code"] in {issue.code for issue in result.issues}


def test_intent_json_schemas_are_strict_and_versioned() -> None:
    design_schema = json.loads(
        (SCHEMA_DIR / "design-intent.schema.json").read_text(encoding="utf-8")
    )
    verification_schema = json.loads(
        (SCHEMA_DIR / "verification-intent.schema.json").read_text(encoding="utf-8")
    )

    for schema, version in (
        (design_schema, "digital-ic-agent.design-intent.v1"),
        (verification_schema, "digital-ic-agent.verification-intent.v1"),
    ):
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["additionalProperties"] is False
        assert schema["properties"]["schema_version"]["const"] == version
