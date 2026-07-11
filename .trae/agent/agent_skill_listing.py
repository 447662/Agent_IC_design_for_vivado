from typing import Any


def resolve_skill_path(agent: Any, skill: Any) -> Any:
    return agent.trae_dir / skill["path"]


def list_skills(agent: Any) -> bool:
    print("数字IC前端设计Agent - 技能列表")
    print("=" * 60)
    for skill in sorted(agent.agent_config["skills"], key=lambda x: x["priority"]):
        keywords = "、".join(skill.get("triggerKeywords", []))
        print("{}: {}".format(skill["name"], skill["description"]))
        print("  触发关键词: {}".format(keywords))
        print("  优先级: {}".format(skill["priority"]))
    return True


def recommend_skills(agent: Any, user_input: Any) -> Any:
    matched_skills = agent.analyze_requirement(user_input)
    print("\n【需求分析结果】")
    print("用户需求: {}".format(user_input))
    print("\n推荐技能:")
    for skill_name in matched_skills:
        skill = agent.skill_mapping.get(skill_name)
        if skill:
            print("  {} {}: {}".format(agent.OK, skill["name"], skill["description"]))

    return matched_skills
