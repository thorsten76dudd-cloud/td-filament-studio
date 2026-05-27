"""G-Code + deutsche Erklärung als HTML exportieren."""

from __future__ import annotations

import html
from pathlib import Path

from creality_nfc.gcode_annotate import annotate_gcode_text, explain_gcode_line
from creality_nfc.i18n import t as _t


def export_gcode_with_hints_html(
    gcode_body: str,
    *,
    title: str | None = None,
    filename: str = "",
) -> str:
    if title is None:
        title = _t("gcode_export.title")
    lines = gcode_body.splitlines()
    rows: list[str] = []
    for i, line in enumerate(lines, start=1):
        hint = explain_gcode_line(line)
        rows.append(
            "<tr>"
            f'<td class="nr">{i}</td>'
            f'<td class="code"><pre>{html.escape(line)}</pre></td>'
            f'<td class="hint">{html.escape(hint)}</td>'
            "</tr>"
        )
    subtitle = html.escape(filename) if filename else ""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Segoe UI, sans-serif; background: #1a1d23; color: #e8eaed; margin: 1rem; }}
h1 {{ font-size: 1.2rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
th, td {{ border: 1px solid #3a4250; vertical-align: top; padding: 4px 6px; }}
th {{ background: #2a3140; position: sticky; top: 0; }}
.nr {{ color: #8b939e; width: 3em; text-align: right; }}
.code pre {{ margin: 0; font-family: Consolas, monospace; white-space: pre-wrap; }}
.hint {{ color: #b8c0cc; max-width: 28em; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p>{subtitle}</p>
<table>
<thead><tr><th>#</th><th>G-Code</th><th>Was der Drucker macht</th></tr></thead>
<tbody>
{"".join(rows)}
</tbody>
</table>
</body>
</html>
"""


def write_gcode_html_export(path: Path, gcode_body: str, *, filename: str = "") -> None:
    doc = export_gcode_with_hints_html(
        gcode_body,
        title=filename or path.name,
        filename=filename,
    )
    path.write_text(doc, encoding="utf-8")
