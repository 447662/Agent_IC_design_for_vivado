from typing import Any
import html


REPORT_CARD_CLASSES = {
    "doc": "doc-card",
    "scenario": "scenario-card",
}


REPORT_SHELL_CSS = """
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


def render_report_html_shell(
    title: Any,
    body_html: Any,
    variant: Any = "doc",
    css: Any = REPORT_SHELL_CSS,
) -> Any:
    card_class = REPORT_CARD_CLASSES.get(str(variant), REPORT_CARD_CLASSES["doc"])
    escaped_title = html.escape(str(title))
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
<section class="hero"><h1>{title}</h1><p>鐢?Digital IC Agent 鍩轰簬鐩爣閰嶇疆鍜屽満鏅洰褰曡嚜鍔ㄧ敓鎴愩€?/p></section>
<section class="{card_class}">
{body}
</section>
</main>
</body>
</html>
""".format(
        title=escaped_title,
        css=css,
        card_class=card_class,
        body=body_html,
    )
