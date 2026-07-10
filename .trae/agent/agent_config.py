import json
import shlex
from pathlib import Path
from typing import Any, NoReturn, cast


ALLOWED_ACTIONS = {
    "design-document",
    "rtl-implementation",
    "verification-plan",
}

AGENT_FIELDS = {
    "name",
    "version",
    "description",
    "author",
    "createdDate",
    "skills",
    "mcpServers",
    "cliTools",
    "workflow",
    "requirementAnalysis",
}

SKILL_FIELDS = {
    "name",
    "path",
    "description",
    "action",
    "requiredCapabilities",
    "triggerKeywords",
    "priority",
}

MCP_SERVER_FIELDS = {
    "command",
    "args",
    "description",
    "required",
    "installGuide",
}

CLI_TOOL_FIELDS = {
    "name",
    "description",
    "required",
    "checkCommand",
    "installGuide",
}


def _fail(config_path: Path, field_path: str, message: str) -> NoReturn:
    raise ValueError("{}: {}: {}".format(config_path, field_path, message))


def _require_object(
    config_path: Path,
    value: Any,
    field_path: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(config_path, field_path, "must be an object")
    return cast(dict[str, Any], value)


def _require_list(
    config_path: Path,
    value: Any,
    field_path: str,
) -> list[Any]:
    if not isinstance(value, list):
        _fail(config_path, field_path, "must be a list")
    return value


def _validate_fields(
    config_path: Path,
    value: dict[str, Any],
    field_path: str,
    allowed: set[str],
    required: set[str] | None = None,
) -> None:
    for field in sorted(set(value) - allowed):
        _fail(config_path, "{}.{}".format(field_path, field), "unknown field")
    for field in sorted((required or allowed) - set(value)):
        _fail(config_path, "{}.{}".format(field_path, field), "missing required field")


def _require_string(
    config_path: Path,
    value: Any,
    field_path: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(config_path, field_path, "must be a non-empty string")
    return value.strip()


def _require_bool(
    config_path: Path,
    value: Any,
    field_path: str,
) -> bool:
    if not isinstance(value, bool):
        _fail(config_path, field_path, "must be a boolean")
    return value


def _require_string_list(
    config_path: Path,
    value: Any,
    field_path: str,
    *,
    allow_empty: bool,
) -> list[str]:
    raw_items = _require_list(config_path, value, field_path)
    if not allow_empty and not raw_items:
        _fail(config_path, field_path, "must not be empty")
    items: list[str] = []
    for index, raw_item in enumerate(raw_items):
        items.append(
            _require_string(
                config_path,
                raw_item,
                "{}[{}]".format(field_path, index),
            )
        )
    return items


def _require_command(
    config_path: Path,
    value: Any,
    field_path: str,
) -> None:
    if isinstance(value, str):
        _require_string(config_path, value, field_path)
        return
    _require_string_list(
        config_path,
        value,
        field_path,
        allow_empty=False,
    )


def _validate_skills(
    config_path: Path,
    raw_skills: Any,
) -> tuple[set[str], set[str]]:
    skills = _require_list(config_path, raw_skills, "$.skills")
    if not skills:
        _fail(config_path, "$.skills", "must not be empty")

    skill_names: set[str] = set()
    actions: set[str] = set()
    for index, raw_skill in enumerate(skills):
        field_path = "$.skills[{}]".format(index)
        skill = _require_object(config_path, raw_skill, field_path)
        _validate_fields(config_path, skill, field_path, SKILL_FIELDS)

        name = _require_string(config_path, skill["name"], field_path + ".name")
        if name in skill_names:
            _fail(config_path, field_path + ".name", "duplicate skill name")
        skill_names.add(name)

        _require_string(config_path, skill["path"], field_path + ".path")
        _require_string(
            config_path,
            skill["description"],
            field_path + ".description",
        )
        action = _require_string(
            config_path,
            skill["action"],
            field_path + ".action",
        )
        if action not in ALLOWED_ACTIONS:
            _fail(config_path, field_path + ".action", "unknown action")
        if action in actions:
            _fail(config_path, field_path + ".action", "duplicate action")
        actions.add(action)

        _require_string_list(
            config_path,
            skill["requiredCapabilities"],
            field_path + ".requiredCapabilities",
            allow_empty=True,
        )
        _require_string_list(
            config_path,
            skill["triggerKeywords"],
            field_path + ".triggerKeywords",
            allow_empty=False,
        )

        priority = skill["priority"]
        if isinstance(priority, bool) or not isinstance(priority, int):
            _fail(config_path, field_path + ".priority", "must be an integer")
        if not 1 <= priority <= 100:
            _fail(
                config_path,
                field_path + ".priority",
                "must be between 1 and 100",
            )

    return skill_names, actions


def _validate_mcp_servers(
    config_path: Path,
    raw_servers: Any,
) -> set[str]:
    servers = _require_object(config_path, raw_servers, "$.mcpServers")
    capability_names: set[str] = set()
    for raw_name, raw_server in servers.items():
        name = _require_string(
            config_path,
            raw_name,
            "$.mcpServers.<name>",
        )
        field_path = "$.mcpServers.{}".format(name)
        server = _require_object(config_path, raw_server, field_path)
        _validate_fields(config_path, server, field_path, MCP_SERVER_FIELDS)
        _require_command(config_path, server["command"], field_path + ".command")
        _require_string_list(
            config_path,
            server["args"],
            field_path + ".args",
            allow_empty=True,
        )
        _require_string(
            config_path,
            server["description"],
            field_path + ".description",
        )
        _require_bool(config_path, server["required"], field_path + ".required")
        _require_string(
            config_path,
            server["installGuide"],
            field_path + ".installGuide",
        )
        capability_names.add(name)
    return capability_names


def _validate_cli_tools(
    config_path: Path,
    raw_tools: Any,
) -> set[str]:
    tools = _require_list(config_path, raw_tools, "$.cliTools")
    capability_names: set[str] = set()
    for index, raw_tool in enumerate(tools):
        field_path = "$.cliTools[{}]".format(index)
        tool = _require_object(config_path, raw_tool, field_path)
        _validate_fields(config_path, tool, field_path, CLI_TOOL_FIELDS)
        name = _require_string(config_path, tool["name"], field_path + ".name")
        if name in capability_names:
            _fail(config_path, field_path + ".name", "duplicate tool name")
        capability_names.add(name)
        _require_string(
            config_path,
            tool["description"],
            field_path + ".description",
        )
        _require_bool(config_path, tool["required"], field_path + ".required")
        _require_command(
            config_path,
            tool["checkCommand"],
            field_path + ".checkCommand",
        )
        _require_string(
            config_path,
            tool["installGuide"],
            field_path + ".installGuide",
        )
    return capability_names


def _validate_required_capabilities(
    config_path: Path,
    skills: list[Any],
    capability_names: set[str],
) -> None:
    for skill_index, raw_skill in enumerate(skills):
        skill = cast(dict[str, Any], raw_skill)
        capabilities = cast(list[Any], skill["requiredCapabilities"])
        for capability_index, raw_capability in enumerate(capabilities):
            capability = cast(str, raw_capability).strip()
            if capability not in capability_names:
                _fail(
                    config_path,
                    "$.skills[{}].requiredCapabilities[{}]".format(
                        skill_index,
                        capability_index,
                    ),
                    "unknown capability",
                )


def _validate_workflow(
    config_path: Path,
    raw_workflow: Any,
    skill_names: set[str],
) -> None:
    workflow = _require_object(config_path, raw_workflow, "$.workflow")
    _validate_fields(
        config_path,
        workflow,
        "$.workflow",
        {"steps", "decisionRules"},
    )
    _require_string_list(
        config_path,
        workflow["steps"],
        "$.workflow.steps",
        allow_empty=False,
    )
    rules = _require_object(
        config_path,
        workflow["decisionRules"],
        "$.workflow.decisionRules",
    )
    if not rules:
        _fail(config_path, "$.workflow.decisionRules", "must not be empty")
    for rule_name, raw_rule in rules.items():
        normalized_name = _require_string(
            config_path,
            rule_name,
            "$.workflow.decisionRules.<name>",
        )
        field_path = "$.workflow.decisionRules.{}".format(normalized_name)
        rule = _require_object(config_path, raw_rule, field_path)
        _validate_fields(
            config_path,
            rule,
            field_path,
            {"condition", "skill"},
        )
        _require_string(
            config_path,
            rule["condition"],
            field_path + ".condition",
        )
        skill_name = _require_string(
            config_path,
            rule["skill"],
            field_path + ".skill",
        )
        if skill_name not in skill_names:
            _fail(config_path, field_path + ".skill", "unknown skill")


def _validate_requirement_analysis(
    config_path: Path,
    raw_analysis: Any,
    skill_names: set[str],
) -> None:
    analysis = _require_object(
        config_path,
        raw_analysis,
        "$.requirementAnalysis",
    )
    _validate_fields(
        config_path,
        analysis,
        "$.requirementAnalysis",
        {"questions"},
    )
    questions = _require_list(
        config_path,
        analysis["questions"],
        "$.requirementAnalysis.questions",
    )
    if not questions:
        _fail(config_path, "$.requirementAnalysis.questions", "must not be empty")
    for question_index, raw_question in enumerate(questions):
        field_path = "$.requirementAnalysis.questions[{}]".format(
            question_index
        )
        question = _require_object(config_path, raw_question, field_path)
        _validate_fields(
            config_path,
            question,
            field_path,
            {"question", "options"},
        )
        _require_string(
            config_path,
            question["question"],
            field_path + ".question",
        )
        options = _require_list(
            config_path,
            question["options"],
            field_path + ".options",
        )
        if not options:
            _fail(config_path, field_path + ".options", "must not be empty")
        for option_index, raw_option in enumerate(options):
            option_path = "{}.options[{}]".format(field_path, option_index)
            option = _require_object(config_path, raw_option, option_path)
            _validate_fields(
                config_path,
                option,
                option_path,
                {"label", "skill"},
            )
            _require_string(
                config_path,
                option["label"],
                option_path + ".label",
            )
            skill_name = _require_string(
                config_path,
                option["skill"],
                option_path + ".skill",
            )
            if skill_name != "all" and skill_name not in skill_names:
                _fail(config_path, option_path + ".skill", "unknown skill")


def load_agent_config(config_path: Any) -> dict[str, Any]:
    resolved_path = Path(config_path)
    with resolved_path.open("r", encoding="utf-8") as config_file:
        raw_config = json.load(config_file)
    config = _require_object(resolved_path, raw_config, "$")
    _validate_fields(resolved_path, config, "$", AGENT_FIELDS)

    _require_string(resolved_path, config["name"], "$.name")
    _require_string(resolved_path, config["version"], "$.version")
    _require_string(resolved_path, config["description"], "$.description")
    _require_string(resolved_path, config["author"], "$.author")
    _require_string(resolved_path, config["createdDate"], "$.createdDate")

    skill_names, _ = _validate_skills(resolved_path, config["skills"])
    capability_names = _validate_mcp_servers(
        resolved_path,
        config["mcpServers"],
    )
    capability_names.update(
        _validate_cli_tools(resolved_path, config["cliTools"])
    )
    _validate_required_capabilities(
        resolved_path,
        cast(list[Any], config["skills"]),
        capability_names,
    )
    _validate_workflow(resolved_path, config["workflow"], skill_names)
    _validate_requirement_analysis(
        resolved_path,
        config["requirementAnalysis"],
        skill_names,
    )
    return config


def normalize_configured_command(command: Any) -> list[str]:
    if isinstance(command, list):
        return [str(part) for part in command]
    if isinstance(command, str):
        return shlex.split(command)
    raise ValueError("命令必须是字符串或字符串数组")
