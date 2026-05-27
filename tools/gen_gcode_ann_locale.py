"""One-off: print gcode_ann locale entries for de.py / en.py."""
from __future__ import annotations

pairs: dict[str, tuple[str, str]] = {
    "gcode_ann.layer": ("Schicht {n}", "Layer {n}"),
    "gcode_ann.layer_change": ("Schichtwechsel", "Layer change"),
    "gcode_ann.outer_wall": ("Außenwand drucken", "Print outer wall"),
    "gcode_ann.inner_wall": ("Innenwand drucken", "Print inner wall"),
    "gcode_ann.top_surface": ("Obere Fläche schließen", "Close top surface"),
    "gcode_ann.bottom_surface": ("Untere Fläche / erste Schicht", "Bottom / first layer"),
    "gcode_ann.infill": ("Infill / Füllung", "Infill"),
    "gcode_ann.solid_infill": ("Volle Füllung", "Solid infill"),
    "gcode_ann.sparse_infill": ("Leichte Füllung", "Sparse infill"),
    "gcode_ann.skirt": ("Skirt / Rand", "Skirt"),
    "gcode_ann.brim": ("Brim / Randhaft", "Brim"),
    "gcode_ann.support": ("Stützstruktur", "Support structure"),
    "gcode_ann.overhang": ("Überhang", "Overhang"),
    "gcode_ann.bridge": ("Brücke", "Bridge"),
    "gcode_ann.gap_fill": ("Lücken füllen", "Gap fill"),
    "gcode_ann.custom": ("Sonderbereich (Slicer)", "Custom region (slicer)"),
    "gcode_ann.type_generic": ("Druckbereich laut Slicer", "Print region (slicer)"),
    "gcode_ann.z_height": ("Höhe Z = {z} mm", "Height Z = {z} mm"),
    "gcode_ann.height": ("Schichthöhe / Z-Höhe", "Layer height / Z"),
    "gcode_ann.filament_used": (
        "Filamentverbrauch (Angabe im Kommentar)",
        "Filament usage (comment)",
    ),
    "gcode_ann.total_filament": ("Gesamt-Filamentverbrauch", "Total filament usage"),
    "gcode_ann.est_time": ("Geschätzte Druckzeit", "Estimated print time"),
    "gcode_ann.time": ("Zeitangabe vom Slicer", "Time from slicer"),
    "gcode_ann.mesh": ("3D-Mesh / Objektname", "3D mesh / object name"),
    "gcode_ann.object": ("Druckobjekt", "Print object"),
    "gcode_ann.exclude": ("Objekt von Druck ausnehmen", "Exclude object from print"),
    "gcode_ann.feature": ("Slicer-Feature", "Slicer feature"),
    "gcode_ann.printer": ("Druckerprofil", "Printer profile"),
    "gcode_ann.filament": ("Filamentprofil", "Filament profile"),
    "gcode_ann.process": ("Slicer-Prozess", "Slicer process"),
    "gcode_ann.pause": ("Pause angefordert", "Pause requested"),
    "gcode_ann.stop": ("Stopp / Ende markiert", "Stop / end marked"),
    "gcode_ann.wipe": ("Düse reinigen / wischbewegung", "Nozzle wipe / cleaning"),
    "gcode_ann.prime": ("Düse vorbereiten / priming", "Nozzle prime"),
    "gcode_ann.flush": ("Filament spülen / wechseln", "Purge / filament change"),
    "gcode_ann.tool_change": ("Werkzeugwechsel (Multimaterial)", "Tool change (multimaterial)"),
    "gcode_ann.color": ("Farbwechsel / AMS", "Color change / AMS"),
    "gcode_ann.start_gcode": ("Start-G-Code des Slicers", "Slicer start G-code"),
    "gcode_ann.end_gcode": ("End-G-Code des Slicers", "Slicer end G-code"),
    "gcode_ann.before_layer": ("Vor Schichtbeginn", "Before layer"),
    "gcode_ann.after_layer": ("Nach Schichtende", "After layer"),
    "gcode_ann.machine": ("Drucker-Makro (Creality/Slicer)", "Printer macro (Creality/slicer)"),
    "gcode_ann.executing": ("Slicer-Schritt läuft", "Slicer step running"),
    "gcode_ann.section": ("Abschnitt im Slicer-Kommentar", "Section in slicer comment"),
    "gcode_ann.not_displayed": (
        "Hinweis: Abschnitt in der Vorschau ausgelassen",
        "Note: section omitted in preview",
    ),
    "gcode_ann.bytes_middle": (
        "Vorschau: Mittelteil der Datei fehlt",
        "Preview: middle of file omitted",
    ),
    "gcode_ann.empty_comment": ("Leerzeile / Kommentar", "Blank / comment"),
    "gcode_ann.long_comment": ("Slicer-Kommentar (lange Zeile)", "Slicer comment (long line)"),
    "gcode_ann.slicer_comment": ("Slicer-Kommentar", "Slicer comment"),
    "gcode_ann.g0_extrude": (
        "Schnell bewegen und dabei Material extrudieren",
        "Rapid move while extruding",
    ),
    "gcode_ann.g0_rapid_axes": ("Schnellfahrt ohne Druck ({axes})", "Rapid move without printing ({axes})"),
    "gcode_ann.g0_rapid": ("Schnellfahrt ohne Material", "Rapid move without material"),
    "gcode_ann.g1_retract": ("Lineare Bewegung mit Filament-Rückzug", "Linear move with filament retract"),
    "gcode_ann.g1_extrude_axes": (
        "Drucklinie — Material wird extrudiert ({axes})",
        "Print line — extruding ({axes})",
    ),
    "gcode_ann.g1_extrude": ("Drucklinie — Material extrudieren", "Print line — extrude"),
    "gcode_ann.g1_move_axes": ("Lineare Bewegung ({axes})", "Linear move ({axes})"),
    "gcode_ann.g1_move": ("Lineare Bewegung", "Linear move"),
    "gcode_ann.arc_cw": ("Kreisbogen im Uhrzeigersinn", "Arc clockwise"),
    "gcode_ann.arc_ccw": ("Kreisbogen gegen den Uhrzeigersinn", "Arc counter-clockwise"),
    "gcode_ann.with_extrusion": (" mit Extrusion", " with extrusion"),
    "gcode_ann.home": ("Referenzfahrt — Achsen ausrichten ({axes})", "Homing — align axes ({axes})"),
    "gcode_ann.all_axes": ("alle", "all"),
    "gcode_ann.g92": (
        "Logische Position setzen (ohne physische Bewegung)",
        "Set logical position (no physical move)",
    ),
    "gcode_ann.g90": (
        "Ab jetzt absolute Positionen (Millimeter vom Nullpunkt)",
        "Absolute coordinates from now on",
    ),
    "gcode_ann.g91": (
        "Ab jetzt relative Positionen (Versatz zur letzten Position)",
        "Relative coordinates from now on",
    ),
    "gcode_ann.g_generic": ("Bewegungs- oder Geometrie-Befehl", "Motion or geometry command"),
    "gcode_ann.control": ("Steuerbefehl", "Control command"),
    "gcode_ann.m104_set": ("Düsentemperatur auf {t:.0f} °C setzen", "Set nozzle temperature to {t:.0f} °C"),
    "gcode_ann.m104": ("Düsentemperatur vorgeben", "Set nozzle temperature"),
    "gcode_ann.m109_set": ("Düse auf {t:.0f} °C erhitzen und warten", "Heat nozzle to {t:.0f} °C and wait"),
    "gcode_ann.m109": ("Düse erhitzen und auf Temperatur warten", "Heat nozzle and wait"),
    "gcode_ann.m140_set": ("Bett auf {t:.0f} °C einstellen", "Set bed to {t:.0f} °C"),
    "gcode_ann.m140": ("Betttemperatur vorgeben", "Set bed temperature"),
    "gcode_ann.m190_set": ("Bett auf {t:.0f} °C erhitzen und warten", "Heat bed to {t:.0f} °C and wait"),
    "gcode_ann.m190": ("Bett erhitzen und auf Temperatur warten", "Heat bed and wait"),
    "gcode_ann.m106_set": ("Lüfter einschalten ({p:.0f}%)", "Fan on ({p:.0f}%)"),
    "gcode_ann.m106": ("Lüfter steuern", "Control fan"),
    "gcode_ann.m107": ("Lüfter ausschalten", "Fan off"),
    "gcode_ann.m82": ("Extrusionsmenge ab jetzt absolut zählen", "Absolute extrusion from now on"),
    "gcode_ann.m83": (
        "Extrusionsmenge ab jetzt relativ zur letzten Zeile",
        "Relative extrusion from now on",
    ),
    "gcode_ann.m400": ("Warten, bis alle Bewegungen fertig sind", "Wait until moves finish"),
    "gcode_ann.m600": ("Filamentwechsel — Druck pausiert", "Filament change — print paused"),
    "gcode_ann.m0": ("Druck anhalten (Pause)", "Pause print"),
    "gcode_ann.m220_set": ("Geschwindigkeitsfaktor {p:.0f}%", "Speed factor {p:.0f}%"),
    "gcode_ann.m220": ("Druckgeschwindigkeit anpassen", "Adjust print speed"),
    "gcode_ann.m221": ("Fluss / Extrusionsrate anpassen", "Adjust flow / extrusion rate"),
    "gcode_ann.m204": ("Beschleunigung begrenzen", "Limit acceleration"),
    "gcode_ann.m205": ("Ruck / Jerk begrenzen", "Limit jerk"),
    "gcode_ann.m900": ("Linear Advance / Druckvorschub kalibrieren", "Linear advance calibration"),
    "gcode_ann.m4x": ("Zusatzsteuerung (Slicer oder Firmware)", "Auxiliary control (slicer/firmware)"),
    "gcode_ann.tool": ("Filamentkanal / Werkzeug wechseln (Kanal {ch})", "Switch tool/filament channel ({ch})"),
    "gcode_ann.m_firmware": ("Steuerbefehl an die Firmware", "Firmware command"),
    "gcode_ann.command": ("Befehl", "Command"),
    "gcode_ann.comment_line": ("Kommentarzeile", "Comment line"),
    "gcode_ann.start_print": ("Druckjob starten (Slicer-Makro)", "Start print job (slicer macro)"),
    "gcode_ann.end_print": ("Druckjob beenden (Slicer-Makro)", "End print job (slicer macro)"),
    "gcode_ann.machine_macro": ("Drucker-Makro aus dem Slicer", "Printer macro from slicer"),
    "gcode_ann.set_var": ("Interne Variable setzen (Firmware)", "Set internal variable (firmware)"),
    "gcode_ann.m117": ("Meldung auf dem Display anzeigen", "Show message on display"),
    "gcode_ann.nonstandard": (
        "Slicer- oder Drucker-Zeile (kein Standard-Bewegungsbefehl)",
        "Slicer/printer line (non-standard motion)",
    ),
    "gcode_ann.trail_sep": (" — ", " — "),
}


def esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("—", "\u2014")
        .replace("\u201e", "\\u201e")
        .replace("\u201c", "\\u201c")
        .replace("\u00b7", "\\u00b7")
    )


if __name__ == "__main__":
    for idx, lang in enumerate(("de", "en")):
        print(f"# {lang}")
        for k, v in pairs.items():
            print(f'    "{k}": "{esc(v[idx])}",')
