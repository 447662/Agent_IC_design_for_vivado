from pathlib import Path
from typing import Any

from digital_ic_agent._runtime.artifact_manifest import utc_timestamp
from digital_ic_agent._runtime.project_overview_core import (
    FAILURE_STATUSES,
    REPORT_SURFACES,
    RESOURCE_SUFFIXES,
    WARNING_STATUSES,
    collect_environment,
    collect_targets,
    project_status,
)
from digital_ic_agent._runtime.project_overview_render import (
    render_project_overview_html,
    render_project_overview_markdown,
)
from digital_ic_agent._runtime.target_dashboard import write_target_dashboard


__all__ = [
    "FAILURE_STATUSES",
    "REPORT_SURFACES",
    "RESOURCE_SUFFIXES",
    "WARNING_STATUSES",
    "collect_environment",
    "collect_targets",
    "project_status",
    "render_project_overview_html",
    "render_project_overview_markdown",
    "write_project_overview",
    "write_target_dashboard",
]


def write_project_overview(self: Any, output_dir: Any="outputs") -> Any:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = collect_targets(self, output_dir)
    environment = collect_environment(output_dir)
    status = project_status(targets, environment)
    generated_at = utc_timestamp()
    markdown_path = output_dir / "index.md"
    html_path = output_dir / "index.html"
    markdown_path.write_text(
        render_project_overview_markdown(
            output_dir,
            targets,
            environment,
            status,
            generated_at,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        render_project_overview_html(
            targets,
            environment,
            status,
            generated_at,
        ),
        encoding="utf-8",
    )
    return {
        "status": status,
        "target_count": len(targets),
        "ready_target_count": sum(
            target["status"] == "PASS"
            for target in targets
        ),
        "failed_target_count": sum(
            target["status"] in FAILURE_STATUSES
            for target in targets
        ),
        "environment_status": environment["status"],
        "targets": targets,
        "environment": environment,
        "markdown_path": markdown_path,
        "html_path": html_path,
    }
