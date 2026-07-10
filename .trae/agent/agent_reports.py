import html


def render_markdown_document_html(title, markdown_text, variant="doc"):
    body = []
    in_table = False
    table_rows = 0

    def close_table():
        nonlocal in_table, table_rows
        if in_table:
            body.append("</tbody></table>")
            in_table = False
            table_rows = 0

    for raw_line in markdown_text.splitlines():
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

    css = """
        :root { --bg:#f4f7fb; --panel:#ffffff; --ink:#1b2430; --muted:#5d6b7a; --line:#d9e1ec; --accent:#1f6feb; --accent2:#0f766e; }
        * { box-sizing:border-box; }
        body { margin:0; background:var(--bg); color:var(--ink); font-family:"Microsoft YaHei", "Segoe UI", Arial, sans-serif; line-height:1.65; }
        .page { max-width:1100px; margin:0 auto; padding:36px 20px 56px; }
        .hero { padding:28px 30px; border-radius:8px; background:linear-gradient(135deg,#172033,#244a72); color:white; box-shadow:0 18px 45px rgba(23,32,51,.18); }
        .hero h1 { margin:0 0 8px; font-size:32px; letter-spacing:0; }
        .hero p { margin:0; color:#dce9ff; }
        .doc-card, .scenario-card { margin-top:18px; padding:26px; border:1px solid var(--line); border-radius:8px; background:var(--panel); box-shadow:0 10px 30px rgba(20,31,48,.08); }
        h1 { margin:0 0 16px; font-size:28px; }
        h2 { margin:28px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--line); font-size:22px; }
        h3 { margin:20px 0 8px; font-size:17px; color:var(--accent2); }
        p { margin:8px 0; color:var(--muted); }
        .bullet { padding-left:18px; position:relative; }
        .bullet:before { content:""; width:6px; height:6px; border-radius:50%; background:var(--accent); position:absolute; left:0; top:.75em; }
        table { width:100%; border-collapse:collapse; margin:12px 0 18px; overflow:hidden; border:1px solid var(--line); border-radius:8px; }
        th, td { padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
        th { background:#eef4fb; color:#1b2430; font-weight:700; }
        code { padding:2px 5px; border-radius:5px; background:#edf2f7; color:#0f3d66; }
        @media (max-width: 700px) { .page { padding:20px 12px 36px; } .hero, .doc-card, .scenario-card { padding:20px; } .hero h1 { font-size:25px; } table { display:block; overflow-x:auto; } }
        """
    card_class = "scenario-card" if variant == "scenario" else "doc-card"
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<main class="page">
<section class="hero"><h1>{title}</h1><p>由 Digital IC Agent 基于目标配置和场景目录自动生成。</p></section>
<section class="{card_class}">
{body}
</section>
</main>
</body>
</html>
""".format(
        title=html.escape(title),
        css=css,
        card_class=card_class,
        body="\n".join(body),
    )
