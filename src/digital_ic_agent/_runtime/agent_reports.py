from typing import Any
import html

from digital_ic_agent._runtime.report_templates import render_report_html_shell


def render_markdown_body_html(markdown_text: Any) -> Any:
    body = []
    in_table = False
    table_rows = 0

    def close_table() -> Any:
        nonlocal in_table, table_rows
        if in_table:
            body.append("</tbody></table>")
            in_table = False
            table_rows = 0

    for raw_line in str(markdown_text).splitlines():
        line = raw_line.rstrip()
        if not line:
            close_table()
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [
                html.escape(cell.strip())
                for cell in line.strip("|").split("|")
            ]
            if all(set(cell.replace(" ", "")) <= set("-:") for cell in cells):
                continue
            if not in_table:
                body.append("<table><tbody>")
                in_table = True
                table_rows = 0
            tag = "th" if table_rows == 0 else "td"
            body.append(
                "<tr>{}</tr>".format(
                    "".join(
                        "<{}>{}</{}>".format(tag, cell, tag)
                        for cell in cells
                    )
                )
            )
            table_rows += 1
            continue

        close_table()
        if line.startswith("# "):
            body.append("<h1>{}</h1>".format(html.escape(line[2:].strip())))
        elif line.startswith("## "):
            body.append("<h2>{}</h2>".format(html.escape(line[3:].strip())))
        elif line.startswith("### "):
            body.append("<h3>{}</h3>".format(html.escape(line[4:].strip())))
        elif line.startswith("- "):
            body.append(
                '<p class="bullet">{}</p>'.format(
                    html.escape(line[2:].strip())
                )
            )
        else:
            body.append("<p>{}</p>".format(html.escape(line)))
    close_table()
    return "\n".join(body)


def render_markdown_document_html(
    title: Any,
    markdown_text: Any,
    variant: Any = "doc",
) -> Any:
    return render_report_html_shell(
        title,
        render_markdown_body_html(markdown_text),
        variant=variant,
    )
