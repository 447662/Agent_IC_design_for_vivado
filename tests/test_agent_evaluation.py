import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT_DIR = ROOT / ".trae" / "agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))


from intent_router import analyze_requirement  # noqa: E402


ROUTING_CASES = ROOT / "tests" / "fixtures" / "agent_routing_cases.json"
SKILLS = (
    {
        "name": "digital-ic-designer",
        "action": "design-document",
        "priority": 1,
        "triggerKeywords": ["设计文档", "架构设计", "需求分析", "方案文档", "IEEE标准"],
    },
    {
        "name": "digital-ic-rtl-designer",
        "action": "rtl-implementation",
        "priority": 2,
        "triggerKeywords": ["RTL", "Verilog", "代码实现", "仿真", "波形", "Testbench"],
    },
    {
        "name": "digital-ic-verifier",
        "action": "verification-plan",
        "priority": 3,
        "triggerKeywords": ["UVM", "SystemVerilog", "前仿", "功能验证", "覆盖率"],
    },
)


def _routing_cases():
    cases = json.loads(ROUTING_CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 50
    return cases


def test_p0_1_routing_eval_suite_has_at_least_50_cases():
    cases = _routing_cases()

    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["input"].strip() for case in cases)
    assert all(case["expected_skills"] for case in cases)


def test_p0_1_skill_selection_accuracy_is_at_least_95_percent():
    cases = _routing_cases()
    failures = []
    correct = 0
    for case in cases:
        actual = analyze_requirement(SKILLS, case["input"])
        if actual == case["expected_skills"]:
            correct += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "input": case["input"],
                    "expected": case["expected_skills"],
                    "actual": actual,
                }
            )

    accuracy = correct / len(cases)
    assert accuracy >= 0.95, {
        "accuracy": accuracy,
        "correct": correct,
        "total": len(cases),
        "failures": failures,
    }
