import re
from collections.abc import Iterable, Mapping
from typing import Any


DEFAULT_SKILL = "digital-ic-rtl-designer"
CLAUSE_SPLIT_PATTERN = re.compile(
    r"(?:[，,。；;！!？?\n]+|但是|但|不过|而是|\bbut\b)",
    re.IGNORECASE,
)
NEGATION_MARKERS = (
    "不需要",
    "无需",
    "不要",
    "不用",
    "不使用",
    "不做",
    "不进行",
    "不写",
    "先别",
    "禁止",
    "排除",
    "without ",
    "do not ",
    "don't ",
    "no ",
)
RESTRICTIVE_MARKERS = ("只", "仅", "only ")
CONTRAST_PATTERN = re.compile(r"(?:但是|不过|\bbut\b)", re.IGNORECASE)
FULL_FLOW_KEYWORDS = (
    "完整设计流程",
    "完整流程",
    "全流程",
    "端到端",
    "从规格到实现再到验证",
    "complete design flow",
    "whole flow",
    "end-to-end",
    "from requirements to rtl and verification",
)
SKILL_KEYWORD_ALIASES = {
    "digital-ic-designer": (
        "设计说明",
        "设计文档",
        "架构设计",
        "需求分析",
        "方案文档",
        "ieee标准",
        "接口与时序",
        "接口、时序",
        "怎么设计",
        "设计一个",
        "模块设计",
        "architecture design",
        "architecture document",
        "requirements",
        "interfaces",
        "design document",
    ),
    "digital-ic-rtl-designer": (
        "rtl",
        "verilog",
        "代码实现",
        "实现代码",
        "写rtl",
        "实现rtl",
        "verilog代码",
        "仿真",
        "普通仿真",
        "基础仿真",
        "波形",
        "testbench",
        "实现一个",
        "写一下",
        "implementation",
        "write rtl",
        "generate verilog",
        "create a testbench",
    ),
    "digital-ic-verifier": (
        "uvm",
        "systemverilog",
        "前仿",
        "前仿真",
        "功能验证",
        "覆盖率",
        "验证计划",
        "断言",
        "scoreboard",
        "验证方案",
        "覆盖率验证",
        "assertion",
        "assertions",
        "functional verification",
        "coverage",
        "pre-simulation",
        "verification plan",
    ),
}
FULL_FLOW_SKILLS = (
    "digital-ic-designer",
    "digital-ic-rtl-designer",
    "digital-ic-verifier",
)


def _split_clauses(user_input: str) -> list[str]:
    return [
        clause.strip()
        for clause in CLAUSE_SPLIT_PATTERN.split(user_input.casefold())
        if clause.strip()
    ]


def _is_negated(clause: str, keyword_start: int) -> bool:
    prefix = clause[:keyword_start]
    return any(marker in prefix for marker in NEGATION_MARKERS)


def _routing_text(user_input: str) -> str:
    text = user_input.casefold()
    parts = [part.strip() for part in CONTRAST_PATTERN.split(text) if part.strip()]
    if len(parts) > 1 and any(marker in parts[-1] for marker in RESTRICTIVE_MARKERS):
        return parts[-1]
    return text


def _is_shadowed_keyword(clause: str, keyword: str, keyword_start: int) -> bool:
    if keyword == "verilog":
        return clause[max(0, keyword_start - len("system")) : keyword_start] == "system"
    if keyword == "仿真":
        return keyword_start > 0 and clause[keyword_start - 1] == "前"
    return False


def _keywords_for_skill(skill: Mapping[str, Any]) -> list[str]:
    skill_name = str(skill["name"])
    keywords = [str(keyword).casefold() for keyword in skill.get("triggerKeywords", [])]
    keywords.extend(SKILL_KEYWORD_ALIASES.get(skill_name, ()))
    return sorted({keyword for keyword in keywords if keyword}, key=len, reverse=True)


def analyze_requirement(
    skills: Iterable[Mapping[str, Any]],
    user_input: str,
    default_skill: str = DEFAULT_SKILL,
) -> list[str]:
    ordered_skills = sorted(skills, key=lambda item: int(item["priority"]))
    routing_text = _routing_text(str(user_input))
    clauses = _split_clauses(routing_text)
    matched_skills = []
    negated_skills = set()

    if any(keyword in routing_text for keyword in FULL_FLOW_KEYWORDS):
        available_skills = {str(skill["name"]) for skill in ordered_skills}
        return [skill for skill in FULL_FLOW_SKILLS if skill in available_skills]

    for skill in ordered_skills:
        skill_name = str(skill["name"])
        positive_match = False
        negative_match = False
        for keyword in _keywords_for_skill(skill):
            for clause in clauses:
                for match in re.finditer(re.escape(keyword), clause):
                    if _is_shadowed_keyword(clause, keyword, match.start()):
                        continue
                    if _is_negated(clause, match.start()):
                        negative_match = True
                    else:
                        positive_match = True

        if positive_match:
            matched_skills.append(skill_name)
        elif negative_match:
            negated_skills.add(skill_name)

    if matched_skills:
        return matched_skills
    if default_skill not in negated_skills:
        return [default_skill]
    return []
