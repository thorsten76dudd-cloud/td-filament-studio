"""Kurz-Erklärungen zu G-Code-Zeilen (Anzeige neben dem Text)."""

from __future__ import annotations

import re

_CMD_RE = re.compile(
    r"^\s*(?:N\d+\s+)?([GMT]\d*\.?\d*)\b",
    re.IGNORECASE,
)


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


def explain_gcode_line(line: str) -> str:
    """Eine Zeile → kurze deutsche Erklärung für die rechte Spalte."""
    raw = line.rstrip("\r\n")
    stripped = raw.strip()
    if not stripped:
        return ""
    if stripped.startswith(";"):
        return stripped[1:].strip()[:120] or "Kommentar"

    m = _CMD_RE.match(stripped)
    if not m:
        if stripped.startswith("START_PRINT"):
            return "Druckjob starten (Slicer)"
        if stripped.startswith("END_PRINT"):
            return "Druckjob beendet (Slicer)"
        if stripped.upper().startswith("MACHINE_"):
            return "Drucker-/Slicer-Makro"
        return "Slicer-/Drucker-Zeile"

    cmd = m.group(1).upper()
    n = _nums(stripped)
    has_e = "E" in n

    if cmd in ("G0", "G00"):
        if has_e and n.get("E", 0) > 0:
            return "Bewegen + extrudieren (G0 mit E)"
        parts = [p for p in ("X", "Y", "Z") if p in n]
        if parts:
            return f"Schnellfahrt ({', '.join(parts)}) — ohne Druck"
        return "Schnellfahrt (ohne Material)"

    if cmd in ("G1", "G01"):
        parts = [p for p in ("X", "Y", "Z") if p in n]
        if has_e:
            e = n.get("E", 0)
            if e < 0:
                return "Bewegen + Retract (E<0)"
            if parts:
                return f"Drucklinie / Schicht ({', '.join(parts)})"
            return "Drucklinie — Material extrudieren"
        if parts:
            return f"Lineare Fahrt ({', '.join(parts)})"
        return "Lineare Bewegung"

    if cmd in ("G2", "G02"):
        return "Kreisbogen (im Uhrzeigersinn)" + (" + extrudieren" if has_e else "")
    if cmd in ("G3", "G03"):
        return "Kreisbogen (gegen Uhrzeigersinn)" + (" + extrudieren" if has_e else "")

    if cmd == "G28":
        axes = [a for a in "XYZ" if a in stripped.upper()]
        return f"Referenzfahrt / Home ({', '.join(axes) or 'alle Achsen'})"

    if cmd == "G92":
        return "Position/Zähler setzen (logisch, ohne Fahrt)"

    if cmd == "G90":
        return "Absolute Koordinaten (G90)"
    if cmd == "G91":
        return "Relative Koordinaten (G91)"

    if cmd in ("M104",):
        s = n.get("S")
        return f"Düsentemperatur setzen ({s}°C)" if s is not None else "Düsentemperatur setzen"
    if cmd in ("M109",):
        s = n.get("S")
        return f"Auf Düsentemperatur warten ({s}°C)" if s is not None else "Düse aufheizen & warten"
    if cmd in ("M140",):
        s = n.get("S")
        return f"Bett-Temperatur setzen ({s}°C)" if s is not None else "Bett-Temperatur setzen"
    if cmd in ("M190",):
        s = n.get("S")
        return f"Auf Bett-Temperatur warten ({s}°C)" if s is not None else "Bett aufheizen & warten"

    if cmd == "M106":
        s = n.get("S")
        return f"Lüfter an ({s}%)" if s is not None else "Lüfter steuern"
    if cmd == "M107":
        return "Lüfter aus"

    if cmd == "M82":
        return "Extrusion absolut (M82)"
    if cmd == "M83":
        return "Extrusion relativ (M83)"

    if cmd.startswith("M4") and cmd not in ("M400",):
        return "M-Code (Steuerung / Slicer)"

    if cmd == "M400":
        return "Warten bis Bewegungen fertig"

    if cmd == "M600":
        return "Filamentwechsel — pausiert"
    if cmd == "M0" or cmd == "M1":
        return "Pause / optionaler Stopp"

    if cmd.startswith("T") and len(cmd) <= 3:
        return f"Werkzeug / Filament-Kanal wechseln ({cmd})"

    if cmd.startswith("G"):
        return f"G-Code {cmd}"
    if cmd.startswith("M"):
        return f"M-Code {cmd}"

    return cmd


def annotate_gcode_text(text: str) -> str:
    """Zu jedem Zeilenumbruch eine Erklärungszeile (gleiche Zeilenanzahl)."""
    lines = text.splitlines()
    return "\n".join(explain_gcode_line(ln) for ln in lines)
