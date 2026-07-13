from typing import Any


def build_project_slug(agent: Any, user_input: Any) -> Any:
    return agent._default_project_slug_builder(user_input)


def render_design_spec(agent: Any, user_input: Any, matched_skills: Any) -> Any:
    return agent._default_design_spec_renderer(
        user_input,
        matched_skills,
        agent.skill_mapping,
    )


def generate_design_spec(
    agent: Any,
    user_input: Any,
    matched_skills: Any,
    output_dir: Any,
) -> Any:
    return agent._default_design_spec_writer(
        user_input,
        matched_skills,
        output_dir,
        agent.skill_mapping,
    )


def render_markdown_document_html(
    agent: Any,
    title: Any,
    markdown_text: Any,
    variant: Any = "doc",
) -> Any:
    return agent._markdown_document_html_renderer(
        title,
        markdown_text,
        variant=variant,
    )
