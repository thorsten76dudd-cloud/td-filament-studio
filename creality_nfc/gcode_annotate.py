"""Kurz-Erklärungen zu G-Code-Zeilen (Anzeige neben dem Text)."""

from __future__ import annotations

import re
from typing import Callable

_CMD_RE = re.compile(
    r"^\s*(?:N\d+\s+)?([GMT]\d*\.?\d*)\b",
    re.IGNORECASE,
)

_COMMENT_RULES: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [
    (re.compile(r"^layer\s*[:_]?\s*(\d+)", re.I), lambda m: f"Schicht {m.group(1)}"),
    (re.compile(r"^layer_change", re.I), "Schichtwechsel"),
    (re.compile(r"^type\s*:\s*outer\s*wall", re.I), "Außenwand drucken"),
    (re.compile(r"^type\s*:\s*inner\s*wall", re.I), "Innenwand drucken"),
    (re.compile(r"^type\s*:\s*top\s*surface", re.I), "Obere Fläche schließen"),
    (re.compile(r"^type\s*:\s*bottom\s*surface", re.I), "Untere Fläche / erste Schicht"),
    (re.compile(r"^type\s*:\s*infill", re.I), "Infill / Füllung"),
    (re.compile(r"^type\s*:\s*solid\s*infill", re.I), "Volle Füllung"),
    (re.compile(r"^type\s*:\s*sparse\s*infill", re.I), "Leichte Füllung"),
    (re.compile(r"^type\s*:\s*skirt", re.I), "Skirt / Rand"),
    (re.compile(r"^type\s*:\s*brim", re.I), "Brim / Randhaft"),
    (re.compile(r"^type\s*:\s*support", re.I), "Stützstruktur"),
    (re.compile(r"^type\s*:\s*overhang", re.I), "Überhang"),
    (re.compile(r"^type\s*:\s*bridge", re.I), "Brücke"),
    (re.compile(r"^type\s*:\s*gap\s*fill", re.I), "Lücken füllen"),
    (re.compile(r"^type\s*:\s*custom", re.I), "Sonderbereich (Slicer)"),
    (re.compile(r"^type\s*:", re.I), "Druckbereich laut Slicer"),
    (re.compile(r"^z\s*[:=]\s*([\d.]+)", re.I), lambda m: f"Höhe Z = {m.group(1)} mm"),
    (re.compile(r"^height\s*[:=]", re.I), "Schichthöhe / Z-Höhe"),
    (re.compile(r"filament\s+used", re.I), "Filamentverbrauch (Angabe im Kommentar)"),
    (re.compile(r"total\s+filament", re.I), "Gesamt-Filamentverbrauch"),
    (re.compile(r"estimated\s+printing\s+time", re.I), "Geschätzte Druckzeit"),
    (re.compile(r"^time\s*:", re.I), "Zeitangabe vom Slicer"),
    (re.compile(r"^mesh\s*:", re.I), "3D-Mesh / Objektname"),
    (re.compile(r"^object\s*:", re.I), "Druckobjekt"),
    (re.compile(r"exclude\s*object", re.I), "Objekt von Druck ausnehmen"),
    (re.compile(r"^feature\s*:", re.I), "Slicer-Feature"),
    (re.compile(r"^printer\s*:", re.I), "Druckerprofil"),
    (re.compile(r"^filament\s*:", re.I), "Filamentprofil"),
    (re.compile(r"^process\s*:", re.I), "Slicer-Prozess"),
    (re.compile(r"^pause\s", re.I), "Pause angefordert"),
    (re.compile(r"^stop\s", re.I), "Stopp / Ende markiert"),
    (re.compile(r"wipe", re.I), "Düse reinigen / wischbewegung"),
    (re.compile(r"prime", re.I), "Düse vorbereiten / priming"),
    (re.compile(r"flush", re.I), "Filament spülen / wechseln"),
    (re.compile(r"tool_change", re.I), "Werkzeugwechsel (Multimaterial)"),
    (re.compile(r"^color", re.I), "Farbwechsel / AMS"),
    (re.compile(r"^start\s+gcode", re.I), "Start-G-Code des Slicers"),
    (re.compile(r"^end\s+gcode", re.I), "End-G-Code des Slicers"),
    (re.compile(r"^before_layer", re.I), "Vor Schichtbeginn"),
    (re.compile(r"^after_layer", re.I), "Nach Schichtende"),
    (re.compile(r"^machine_", re.I), "Drucker-Makro (Creality/Slicer)"),
    (re.compile(r"^executing", re.I), "Slicer-Schritt läuft"),
    (re.compile(r"^-----", re.I), "Abschnitt im Slicer-Kommentar"),
    (re.compile(r"not\s+displayed", re.I), "Hinweis: Abschnitt in der Vorschau ausgelassen"),
    (re.compile(r"bytes\s+in\s+der\s+mitte", re.I), "Vorschau: Mittelteil der Datei fehlt"),
]


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
    """Slicer-Kommentar → deutsche Bedeutung (nicht den Rohtext wiederholen)."""
    text = body.strip()
    if not text:
        return "Leerzeile / Kommentar"
    for pattern, repl in _COMMENT_RULES:
        m = pattern.search(text)
        if m:
            if callable(repl):
                return str(repl(m))
            return repl
    if len(text) > 80:
        return "Slicer-Kommentar (lange Zeile)"
    return "Slicer-Kommentar"


def _explain_motion(cmd: str, stripped: str, n: dict[str, float], has_e: bool) -> str:
    parts = [p for p in ("X", "Y", "Z") if p in n]

    if cmd in ("G0", "G00"):
        if has_e and n.get("E", 0) > 0:
            return "Schnell bewegen und dabei Material extrudieren"
        if parts:
            return f"Schnellfahrt ohne Druck ({', '.join(parts)})"
        return "Schnellfahrt ohne Material"

    if cmd in ("G1", "G01"):
        if has_e:
            e = n.get("E", 0)
            if e < 0:
                return "Lineare Bewegung mit Filament-Rückzug"
            if parts:
                return f"Drucklinie — Material wird extrudiert ({', '.join(parts)})"
            return "Drucklinie — Material extrudieren"
        if parts:
            return f"Lineare Bewegung ({', '.join(parts)})"
        return "Lineare Bewegung"

    if cmd in ("G2", "G02"):
        return "Kreisbogen im Uhrzeigersinn" + (" mit Extrusion" if has_e else "")
    if cmd in ("G3", "G03"):
        return "Kreisbogen gegen den Uhrzeigersinn" + (" mit Extrusion" if has_e else "")

    if cmd == "G28":
        axes = [a for a in "XYZ" if a in stripped.upper()]
        return f"Referenzfahrt — Achsen ausrichten ({', '.join(axes) or 'alle'})"

    if cmd == "G92":
        return "Logische Position setzen (ohne physische Bewegung)"

    if cmd == "G90":
        return "Ab jetzt absolute Positionen (Millimeter vom Nullpunkt)"
    if cmd == "G91":
        return "Ab jetzt relative Positionen (Versatz zur letzten Position)"

    if cmd.startswith("G"):
        return "Bewegungs- oder Geometrie-Befehl"
    return "Steuerbefehl"


def _explain_mcode(cmd: str, n: dict[str, float]) -> str:
    s = n.get("S")
    p = n.get("P")

    if cmd in ("M104",):
        return f"Düsentemperatur auf {s:.0f} °C setzen" if s is not None else "Düsentemperatur vorgeben"
    if cmd in ("M109",):
        return (
            f"Düse auf {s:.0f} °C erhitzen und warten"
            if s is not None
            else "Düse erhitzen und auf Temperatur warten"
        )
    if cmd in ("M140",):
        return f"Bett auf {s:.0f} °C einstellen" if s is not None else "Betttemperatur vorgeben"
    if cmd in ("M190",):
        return (
            f"Bett auf {s:.0f} °C erhitzen und warten"
            if s is not None
            else "Bett erhitzen und auf Temperatur warten"
        )
    if cmd == "M106":
        return f"Lüfter einschalten ({s:.0f}%)" if s is not None else "Lüfter steuern"
    if cmd == "M107":
        return "Lüfter ausschalten"
    if cmd == "M82":
        return "Extrusionsmenge ab jetzt absolut zählen"
    if cmd == "M83":
        return "Extrusionsmenge ab jetzt relativ zur letzten Zeile"
    if cmd == "M400":
        return "Warten, bis alle Bewegungen fertig sind"
    if cmd == "M600":
        return "Filamentwechsel — Druck pausiert"
    if cmd in ("M0", "M1"):
        return "Druck anhalten (Pause)"
    if cmd == "M220":
        return f"Geschwindigkeitsfaktor {s:.0f}%" if s is not None else "Druckgeschwindigkeit anpassen"
    if cmd == "M221":
        return "Fluss / Extrusionsrate anpassen"
    if cmd == "M204":
        return "Beschleunigung begrenzen"
    if cmd == "M205":
        return "Ruck / Jerk begrenzen"
    if cmd == "M900":
        return "Linear Advance / Druckvorschub kalibrieren"
    if cmd.startswith("M4") and cmd not in ("M400",):
        return "Zusatzsteuerung (Slicer oder Firmware)"
    if cmd.startswith("T") and len(cmd) <= 3:
        return f"Filamentkanal / Werkzeug wechseln (Kanal {cmd[1:]})"
    if cmd.startswith("M"):
        return "Steuerbefehl an die Firmware"
    return "Befehl"


def explain_gcode_line(line: str) -> str:
    """Eine Zeile → kurze deutsche Erklärung (ohne den G-Code zu wiederholen)."""
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
        return _explain_comment_body(trailing_comment) if trailing_comment else "Kommentarzeile"

    m = _CMD_RE.match(code_part)
    if not m:
        upper = code_part.upper()
        if upper.startswith("START_PRINT"):
            return "Druckjob starten (Slicer-Makro)"
        if upper.startswith("END_PRINT"):
            return "Druckjob beenden (Slicer-Makro)"
        if upper.startswith("MACHINE_"):
            return "Drucker-Makro aus dem Slicer"
        if upper.startswith("SET_GCODE_VARIABLE"):
            return "Interne Variable setzen (Firmware)"
        if upper.startswith("M117"):
            return "Meldung auf dem Display anzeigen"
        main = "Slicer- oder Drucker-Zeile (kein Standard-Bewegungsbefehl)"
    else:
        cmd = m.group(1).upper()
        n = _nums(code_part)
        has_e = "E" in n
        if cmd.startswith("G"):
            main = _explain_motion(cmd, code_part, n, has_e)
        else:
            main = _explain_mcode(cmd, n)

    if trailing_comment:
        sub = _explain_comment_body(trailing_comment)
        if sub not in ("Slicer-Kommentar", "Slicer-Kommentar (lange Zeile)"):
            return f"{main} — {sub}"
    return main


def annotate_gcode_text(text: str) -> str:
    """Zu jedem Zeilenumbruch eine Erklärungszeile (gleiche Zeilenanzahl)."""
    lines = text.splitlines()
    return "\n".join(explain_gcode_line(ln) for ln in lines)
