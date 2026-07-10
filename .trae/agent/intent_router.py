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
    "禁止",
    "排除",
    "without ",
    "do not ",
    "don't ",
    "no ",
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


def analyze_requirement(
    skills: Iterable[Mapping[str, Any]],
    user_input: str,
    default_skill: str = DEFAULT_SKILL,
) -> list[str]:
    ordered_skills = sorted(skills, key=lambda item: int(item["priority"]))
    clauses = _split_clauses(str(user_input))
    matched_skills = []
    negated_skills = set()

    for skill in ordered_skills:
        skill_name = str(skill["name"])
        positive_match = False
        negative_match = False
        for raw_keyword in skill.get("triggerKeywords", []):
            keyword = str(raw_keyword).casefold()
            if not keyword:
                continue
            for clause in clauses:
                for match in re.finditer(re.escape(keyword), clause):
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
