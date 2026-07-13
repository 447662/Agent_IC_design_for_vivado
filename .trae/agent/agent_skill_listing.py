import sys
from typing import Any, TextIO


def resolve_skill_path(agent: Any, skill: Any) -> Any:
    return agent.trae_dir / skill["path"]


def build_skill_listing_lines(agent: Any) -> list[str]:
    lines = [
        "数字IC前端设计Agent - 技能列表",
        "=" * 60,
    ]
    for skill in sorted(agent.agent_config["skills"], key=lambda x: x["priority"]):
        keywords = "、".join(skill.get("triggerKeywords", []))
        lines.extend(
            [
                "{}: {}".format(skill["name"], skill["description"]),
                "  触发关键词: {}".format(keywords),
                "  优先级: {}".format(skill["priority"]),
            ]
        )
    return lines


def build_skill_recommendation_lines(
    agent: Any,
    user_input: Any,
    matched_skills: list[str],
) -> list[str]:
    lines = [
        "\n【需求分析结果】",
        "用户需求: {}".format(user_input),
        "\n推荐技能:",
    ]
    for skill_name in matched_skills:
        skill = agent.skill_mapping.get(skill_name)
        if skill:
            lines.append("  {} {}: {}".format(agent.OK, skill["name"], skill["description"]))
    return lines


def emit_skill_listing_lines(lines: list[str], stream: TextIO | None = None) -> None:
    target_stream = stream or sys.stdout
    for line in lines:
        print(line, file=target_stream)


def list_skills(agent: Any) -> bool:
    emit_skill_listing_lines(build_skill_listing_lines(agent))
    return True


def recommend_skills(agent: Any, user_input: Any) -> Any:
    matched_skills = agent.analyze_requirement(user_input)
    emit_skill_listing_lines(
        build_skill_recommendation_lines(
            agent,
            user_input,
            matched_skills,
        )
    )

    return matched_skills
