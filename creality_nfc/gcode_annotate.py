"""Kurz-Erklärungen zu G-Code-Zeilen (Anzeige neben dem Text)."""

from __future__ import annotations

import re
from typing import Callable

from creality_nfc.i18n import t as _t

_CMD_RE = re.compile(
    r"^\s*(?:N\d+\s+)?([GMT]\d*\.?\d*)\b",
    re.IGNORECASE,
)

_COMMENT_RULES: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [
    (re.compile(r"^layer\s*[:_]?\s*(\d+)", re.I), lambda m: _t("gcode_ann.layer", n=m.group(1))),
    (re.compile(r"^layer_change", re.I), "gcode_ann.layer_change"),
    (re.compile(r"^type\s*:\s*outer\s*wall", re.I), "gcode_ann.outer_wall"),
    (re.compile(r"^type\s*:\s*inner\s*wall", re.I), "gcode_ann.inner_wall"),
    (re.compile(r"^type\s*:\s*top\s*surface", re.I), "gcode_ann.top_surface"),
    (re.compile(r"^type\s*:\s*bottom\s*surface", re.I), "gcode_ann.bottom_surface"),
    (re.compile(r"^type\s*:\s*infill", re.I), "gcode_ann.infill"),
    (re.compile(r"^type\s*:\s*solid\s*infill", re.I), "gcode_ann.solid_infill"),
    (re.compile(r"^type\s*:\s*sparse\s*infill", re.I), "gcode_ann.sparse_infill"),
    (re.compile(r"^type\s*:\s*skirt", re.I), "gcode_ann.skirt"),
    (re.compile(r"^type\s*:\s*brim", re.I), "gcode_ann.brim"),
    (re.compile(r"^type\s*:\s*support", re.I), "gcode_ann.support"),
    (re.compile(r"^type\s*:\s*overhang", re.I), "gcode_ann.overhang"),
    (re.compile(r"^type\s*:\s*bridge", re.I), "gcode_ann.bridge"),
    (re.compile(r"^type\s*:\s*gap\s*fill", re.I), "gcode_ann.gap_fill"),
    (re.compile(r"^type\s*:\s*custom", re.I), "gcode_ann.custom"),
    (re.compile(r"^type\s*:", re.I), "gcode_ann.type_generic"),
    (re.compile(r"^z\s*[:=]\s*([\d.]+)", re.I), lambda m: _t("gcode_ann.z_height", z=m.group(1))),
    (re.compile(r"^height\s*[:=]", re.I), "gcode_ann.height"),
    (re.compile(r"filament\s+used", re.I), "gcode_ann.filament_used"),
    (re.compile(r"total\s+filament", re.I), "gcode_ann.total_filament"),
    (re.compile(r"estimated\s+printing\s+time", re.I), "gcode_ann.est_time"),
    (re.compile(r"^time\s*:", re.I), "gcode_ann.time"),
    (re.compile(r"^mesh\s*:", re.I), "gcode_ann.mesh"),
    (re.compile(r"^object\s*:", re.I), "gcode_ann.object"),
    (re.compile(r"exclude\s*object", re.I), "gcode_ann.exclude"),
    (re.compile(r"^feature\s*:", re.I), "gcode_ann.feature"),
    (re.compile(r"^printer\s*:", re.I), "gcode_ann.printer"),
    (re.compile(r"^filament\s*:", re.I), "gcode_ann.filament"),
    (re.compile(r"^process\s*:", re.I), "gcode_ann.process"),
    (re.compile(r"^pause\s", re.I), "gcode_ann.pause"),
    (re.compile(r"^stop\s", re.I), "gcode_ann.stop"),
    (re.compile(r"wipe", re.I), "gcode_ann.wipe"),
    (re.compile(r"prime", re.I), "gcode_ann.prime"),
    (re.compile(r"flush", re.I), "gcode_ann.flush"),
    (re.compile(r"tool_change", re.I), "gcode_ann.tool_change"),
    (re.compile(r"^color", re.I), "gcode_ann.color"),
    (re.compile(r"^start\s+gcode", re.I), "gcode_ann.start_gcode"),
    (re.compile(r"^end\s+gcode", re.I), "gcode_ann.end_gcode"),
    (re.compile(r"^before_layer", re.I), "gcode_ann.before_layer"),
    (re.compile(r"^after_layer", re.I), "gcode_ann.after_layer"),
    (re.compile(r"^machine_", re.I), "gcode_ann.machine"),
    (re.compile(r"^executing", re.I), "gcode_ann.executing"),
    (re.compile(r"^-----", re.I), "gcode_ann.section"),
    (re.compile(r"not\s+displayed", re.I), "gcode_ann.not_displayed"),
    (re.compile(r"bytes\s+in\s+der\s+mitte", re.I), "gcode_ann.bytes_middle"),
]


def _resolve_comment(repl: str | Callable[[re.Match[str]], str], m: re.Match[str] | None) -> str:
    if callable(repl):
        return str(repl(m)) if m else ""
    return _t(repl)


def _nums(line: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for axis in "XYZEFPS":
        m = re.search(rf"{axis}([-\d.]+)", line, re.IGNORECASE)
        if m:
            try:
                out[axis.upper()] = float(m.group(1))
            except ValueError:
                pass
    return out


def _explain_comment_body(body: str) -> str:
    text = body.strip()
    if not text:
        return _t("gcode_ann.empty_comment")
    for pattern, repl in _COMMENT_RULES:
        m = pattern.search(text)
        if m:
            return _resolve_comment(repl, m)
    if len(text) > 80:
        return _t("gcode_ann.long_comment")
    return _t("gcode_ann.slicer_comment")


def _explain_motion(cmd: str, stripped: str, n: dict[str, float], has_e: bool) -> str:
    parts = [p for p in ("X", "Y", "Z") if p in n]
    axes = ", ".join(parts)

    if cmd in ("G0", "G00"):
        if has_e and n.get("E", 0) > 0:
            return _t("gcode_ann.g0_extrude")
        if parts:
            return _t("gcode_ann.g0_rapid_axes", axes=axes)
        return _t("gcode_ann.g0_rapid")

    if cmd in ("G1", "G01"):
        if has_e:
            e = n.get("E", 0)
            if e < 0:
                return _t("gcode_ann.g1_retract")
            if parts:
                return _t("gcode_ann.g1_extrude_axes", axes=axes)
            return _t("gcode_ann.g1_extrude")
        if parts:
            return _t("gcode_ann.g1_move_axes", axes=axes)
        return _t("gcode_ann.g1_move")

    extra = _t("gcode_ann.with_extrusion") if has_e else ""
    if cmd in ("G2", "G02"):
        return _t("gcode_ann.arc_cw") + extra
    if cmd in ("G3", "G03"):
        return _t("gcode_ann.arc_ccw") + extra

    if cmd == "G28":
        ax = [a for a in "XYZ" if a in stripped.upper()]
        return _t("gcode_ann.home", axes=", ".join(ax) or _t("gcode_ann.all_axes"))

    if cmd == "G92":
        return _t("gcode_ann.g92")
    if cmd == "G90":
        return _t("gcode_ann.g90")
    if cmd == "G91":
        return _t("gcode_ann.g91")
    if cmd.startswith("G"):
        return _t("gcode_ann.g_generic")
    return _t("gcode_ann.control")


def _explain_mcode(cmd: str, n: dict[str, float]) -> str:
    s = n.get("S")
    p = n.get("P")

    if cmd in ("M104",):
        return _t("gcode_ann.m104_set", t=s) if s is not None else _t("gcode_ann.m104")
    if cmd in ("M109",):
        return _t("gcode_ann.m109_set", t=s) if s is not None else _t("gcode_ann.m109")
    if cmd in ("M140",):
        return _t("gcode_ann.m140_set", t=s) if s is not None else _t("gcode_ann.m140")
    if cmd in ("M190",):
        return _t("gcode_ann.m190_set", t=s) if s is not None else _t("gcode_ann.m190")
    if cmd == "M106":
        return _t("gcode_ann.m106_set", p=s) if s is not None else _t("gcode_ann.m106")
    if cmd == "M107":
        return _t("gcode_ann.m107")
    if cmd == "M82":
        return _t("gcode_ann.m82")
    if cmd == "M83":
        return _t("gcode_ann.m83")
    if cmd == "M400":
        return _t("gcode_ann.m400")
    if cmd == "M600":
        return _t("gcode_ann.m600")
    if cmd in ("M0", "M1"):
        return _t("gcode_ann.m0")
    if cmd == "M220":
        return _t("gcode_ann.m220_set", p=s) if s is not None else _t("gcode_ann.m220")
    if cmd == "M221":
        return _t("gcode_ann.m221")
    if cmd == "M204":
        return _t("gcode_ann.m204")
    if cmd == "M205":
        return _t("gcode_ann.m205")
    if cmd == "M900":
        return _t("gcode_ann.m900")
    if cmd.startswith("M4") and cmd not in ("M400",):
        return _t("gcode_ann.m4x")
    if cmd.startswith("T") and len(cmd) <= 3:
        return _t("gcode_ann.tool", ch=cmd[1:])
    if cmd.startswith("M"):
        return _t("gcode_ann.m_firmware")
    return _t("gcode_ann.command")


def explain_gcode_line(line: str) -> str:
    raw = line.rstrip("\r\n")
    stripped = raw.strip()
    if not stripped:
        return ""

    if stripped.startswith(";"):
        return _explain_comment_body(stripped[1:])

    code_part = stripped
    trailing_comment = ""
    if ";" in stripped:
        code_part, _, tail = stripped.partition(";")
        code_part = code_part.strip()
        trailing_comment = tail.strip()

    if not code_part:
        return _explain_comment_body(trailing_comment) if trailing_comment else _t("gcode_ann.comment_line")

    m = _CMD_RE.match(code_part)
    if not m:
        upper = code_part.upper()
        if upper.startswith("START_PRINT"):
            main = _t("gcode_ann.start_print")
        elif upper.startswith("END_PRINT"):
            main = _t("gcode_ann.end_print")
        elif upper.startswith("MACHINE_"):
            main = _t("gcode_ann.machine_macro")
        elif upper.startswith("SET_GCODE_VARIABLE"):
            main = _t("gcode_ann.set_var")
        elif upper.startswith("M117"):
            main = _t("gcode_ann.m117")
        else:
            main = _t("gcode_ann.nonstandard")
    else:
        cmd = m.group(1).upper()
        nums = _nums(code_part)
        has_e = "E" in nums
        if cmd.startswith("G"):
            main = _explain_motion(cmd, code_part, nums, has_e)
        else:
            main = _explain_mcode(cmd, nums)

    if trailing_comment:
        sub = _explain_comment_body(trailing_comment)
        generic = (_t("gcode_ann.slicer_comment"), _t("gcode_ann.long_comment"))
        if sub not in generic:
            return main + _t("gcode_ann.trail_sep") + sub
    return main


def annotate_gcode_text(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(explain_gcode_line(ln) for ln in lines)
