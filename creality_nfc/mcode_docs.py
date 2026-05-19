"""G-Code M-Befehle — Referenz für Marlin-Kompatibilität / Klipper (z. B. Creality K2).

Hinweis: Nicht jeder Befehl ist auf jedem Drucker aktiv. Creality nutzt viele
Funktionen als Klipper-Macros (anderer Name). Bei Unsicherheit: G-Code-Konsole
im Slicer oder Klipper-Log prüfen.
"""

from __future__ import annotations

MCODE_DOCS: dict[str, str] = {
    # ── Programm / Pause ──────────────────────────────────────────────
    "M0": "Unbedingter Halt — Druck stoppt, wartet auf Bestätigung (Display/Host).",
    "M1": "Optionaler Halt — nur wenn der Slicer M1 einfügt (z. B. Hinweis im G-Code).",
    "M2": "Programmende (Ende des G-Code-Jobs; Verhalten firmwareabhängig).",
    "M73": "Fortschritt melden — Klipper/Marlin: z. B. M73 P25 (25 % fertig).",
    "M400": "Warten bis alle Bewegungen im Puffer abgeschlossen sind.",
    "M410": "Sofortiger Bewegungs-Abbruch (Quick-Stop).",
    "M412": "Filament-Runout-Überwachung ein/aus oder Zustand (wenn Sensor verbaut).",
    "M413": "Power-Loss-Recovery (Druck nach Stromausfall fortsetzen) ein/aus.",
    "M112": "Not-Aus — Klipper: sofortiger Shutdown; Drucker neu starten nötig.",
  # ── Schrittmotoren ────────────────────────────────────────────────
    "M17": "Alle Schrittmotoren einschalten (Position halten).",
    "M18": "Motoren deaktivieren (wie M84; optional Achse X Y Z E).",
    "M84": "Motoren deaktivieren — Achsen können handverstellt werden.",
    "M85": "Idle-Timeout bis Motoren ausgeschaltet werden (Sekunden).",
    # ── Temperatur Düse ─────────────────────────────────────────────
    "M104": "Düsentemperatur setzen, ohne zu warten — z. B. M104 S200.",
    "M109": "Düsentemperatur setzen und warten bis Ziel erreicht.",
    "M192": "Düsentemperatur setzen und warten (Klipper-Variante).",
    # ── Temperatur Bett / Kammer ──────────────────────────────────────
    "M140": "Betttemperatur setzen, ohne zu warten — z. B. M140 S60.",
    "M190": "Betttemperatur setzen und warten.",
    "M141": "Kammertemperatur setzen (ohne Warten; geschlossene Drucker).",
    "M191": "Kammertemperatur setzen und warten.",
    "M143": "Maximale Betttemperatur begrenzen (Sicherheitsgrenze).",
    "M302": "Kalt-Extrusion erlauben (unter Mindest-Temperatur drucken).",
    "M303": "PID-Autotune Hotend — z. B. M303 E0 S200 C8.",
    "M304": "PID-Autotune Heizbett.",
    "M301": "PID-Werte Hotend manuell setzen (P I D).",
    "M305": "PID-Werte Bett manuell setzen.",
    # ── Lüfter ────────────────────────────────────────────────────────
    "M106": "Lüfter ein / PWM — M106 S0–255 oder M106 P0 S128 (P = Lüfter-Index).",
    "M107": "Lüfter aus (Standard-Teillüfter oder alle).",
    # ── Extrusion / Flow / Geschwindigkeit ───────────────────────────
    "M82": "Extruder absolut — E-Position ist Gesamtwert seit Reset.",
    "M83": "Extruder relativ — E wird pro Befehl addiert (üblich im Slicer).",
    "M220": "Geschwindigkeitsfaktor in % — M220 S100 = 100 % (Live-Tuning).",
    "M221": "Flow / Extrusionsfaktor in % — M221 S95 = 95 % Materialfluss.",
    "M218": "Hotend-Offset (Multi-Extruder / Tool-Offset).",
    "M600": "Filamentwechsel-Pause — Parken, Piep, manueller Wechsel, Fortsetzen.",
    "M603": "Parameter für Filamentwechsel speichern (Länge, Temp).",
    # ── Position / Status / Anzeige ─────────────────────────────────
    "M114": "Aktuelle Position ausgeben (X Y Z E).",
    "M115": "Firmware-Version und Fähigkeiten ausgeben.",
    "M117": "Text auf dem Display anzeigen — M117 ''Nachricht''.",
    "M118": "Nachricht an Host/Log — M118 A1 Text.",
    "M119": "Endschalter-Zustand auslesen (offen/geschlossen).",
    "M120": "Software-Endstopps aktivieren.",
    "M121": "Software-Endstopps deaktivieren.",
    # ── Homing / Mesh / Offset ────────────────────────────────────────
    "M206": "Achsen-Home-Offset setzen (Marlin).",
    "M207": "Retraction-Parameter (Legacy-Marlin, oft im Slicer).",
    "M208": "Achsen-Min/Max oder Home-Offset.",
    "M211": "Software-Endstopp-Grenzen ein/aus.",
    "M290": "Z-Offset live (Babystepping am Display).",
    "M420": "Bett-Mesh (ABL) ein/aus oder gespeichertes Mesh laden.",
    "M421": "Einzelnen Mesh-Punkt setzen (manuelle Korrektur).",
    "M851": "Z-Probe-Offset — z. B. M851 Z-0.05 (Abstand Düse ↔ Sensor).",
    "M48": "Z-Probe-Wiederholgenauigkeit testen (Statistik).",
    # ── Bewegung / Limits ─────────────────────────────────────────────
    "M92": "Steps/mm setzen — M92 X80 Y80 Z400 E93.",
    "M201": "Maximale Beschleunigung pro Achse (mm/s²).",
    "M203": "Maximale Feedrate pro Achse (mm/s).",
    "M204": "Beschleunigung P/T/R — Druck, Travel, Retract (mm/s²).",
    "M205": "Jerk / minimale Geschwindigkeit (Marlin; Klipper nutzt andere Befehle).",
    # ── EEPROM (Marlin; Klipper: printer.cfg) ─────────────────────────
    "M500": "Aktuelle Einstellungen in EEPROM speichern.",
    "M501": "Einstellungen aus EEPROM laden.",
    "M502": "Werkseinstellungen laden (Vorsicht: überschreibt Werte).",
    "M503": "Alle relevanten Einstellungen als Report ausgeben.",
    # ── LED / Ton / Kamera ────────────────────────────────────────────
    "M150": "RGB-LED (NeoPixel) setzen — Farbe/Wert firmwareabhängig.",
    "M300": "Piepton — M300 S440 P200 (Frequenz Hz, Dauer ms).",
    "M355": "Gehäusebeleuchtung — M355 S1 ein, S0 aus.",
    "M240": "Kamera auslösen / Foto (wenn GPIO-Kamera konfiguriert).",
    # ── TMC / Motortreiber ────────────────────────────────────────────
    "M569": "TMC-Treiber-Modus (Klipper: uart/spi, StealthChop usw.).",
    "M906": "Motorstrom (RMS mA) — M906 X800 Y800 Z800 E900.",
    "M913": "TMC StallGuard-Sensitivität (sensorloses Homing).",
    "M914": "TMC StallGuard-Threshold setzen.",
    "M900": "Linear Advance K-Faktor (Marlin) / oft in Klipper: pressure_advance.",
    # ── Klipper / Host ─────────────────────────────────────────────────
    "M876": "Host-Dialog bestätigen (Filamentwechsel, Prompts).",
    "M808": "G-Code-Schleife / Macro-Wiederholung (Klipper).",
    "M810": "G-Code-Macro aufrufen (Slot 0; Klipper G-Code-Macro).",
    "M811": "G-Code-Macro aufrufen (Slot 1).",
    "M812": "G-Code-Macro aufrufen (Slot 2).",
    "M813": "G-Code-Macro aufrufen (Slot 3).",
    "M814": "G-Code-Macro aufrufen (Slot 4).",
    "M815": "G-Code-Macro aufrufen (Slot 5).",
    "M816": "G-Code-Macro aufrufen (Slot 6).",
    "M817": "G-Code-Macro aufrufen (Slot 7).",
    "M818": "G-Code-Macro aufrufen (Slot 8).",
    "M819": "G-Code-Macro aufrufen (Slot 9).",
    # ── Mehrfarb / Objekt ─────────────────────────────────────────────
    "M486": "Objekt abbrechen (Klipper Cancel-Object) — M486 S-1 aktuelles Objekt.",
    # ── SD-Karte (Legacy / Display) ───────────────────────────────────
    "M20": "SD-Karte: Dateiliste ausgeben.",
    "M23": "SD: Datei auswählen.",
    "M24": "SD-Druck fortsetzen.",
    "M25": "SD-Druck pausieren.",
    "M27": "SD-Druckstatus anzeigen.",
    "M28": "SD: Schreiben starten (Datei anlegen).",
    "M29": "SD: Schreiben beenden.",
    "M30": "SD: Datei löschen.",
    "M32": "SD: Datei drucken (ältere Firmware).",
    # ── Sonstige nützliche ────────────────────────────────────────────
    "M16": "Erwartete Drucker-Fähigkeiten für Slicer-Prüfung.",
    "M42": "GPIO-Pin setzen (Erweiterungsboards).",
    "M80": "Netzteil / PSU ein (wenn PSU_SWITCH konfiguriert).",
    "M81": "Netzteil / PSU aus.",
    "M280": "Servo-Winkel setzen — z. B. Filament-Schneider-Klappe.",
    "M401": "Z-Probe ausfahren (Macro-Name bei Klipper).",
    "M402": "Z-Probe einfahren (Macro-Name bei Klipper).",
    "M404": "Filament-Durchmesser für Flow-Berechnung (mm).",
    "M405": "Filament-Runout-Sensor aktivieren.",
    "M406": "Filament-Runout-Sensor deaktivieren.",
    "M407": "Filament-Runout: Pause auslösen.",
    "M425": "Babystepping / Z-Offset live anpassen.",
    "M428": "Probe-Trigger-Offsets anzeigen.",
    "M566": "Max. Jerk (Klipper: max_extrude_only_velocity / instantaneous).",
    "M584": "Achsen-Zuordnung Stepper (Klipper).",
    "M665": "Delta-Kinematik-Parameter (Delta-Drucker).",
    "M666": "Delta-Endstop-Korrektur.",
    "M999": "Firmware-/MCU-Neustart (Marlin); Vorsicht während des Drucks.",
    # ── Creality K / CFS (Macros — Namen können je Firmware abweichen) ─
    "M1002": "Creality-intern: oft LED, UI oder Systemstatus (Macro).",
    "M1003": "Creality-intern: Buzzer / akustischer Hinweis (Macro).",
    "M701": "Filament laden (Macro; Länge/Geschwindigkeit in printer.cfg).",
    "M702": "Filament entladen (Macro).",
    "M703": "Filament laden — häufig in Creality-Configs für Entladen/AMS.",
    "M704": "Filament schneiden (Cutter-Macro, falls verbaut).",
    "M1040": "Creality CFS: Materialwechsel / Slot-Sequenz (Macro).",
    "M1041": "Creality CFS: Filament zu Extruder führen (Macro).",
    "M1042": "Creality CFS: Filament zurückziehen (Macro).",
    "M1043": "Creality CFS: RFID / Material-Sync (Macro).",
    "M1044": "Creality CFS: Kalibrierung / Durchfluss (Macro).",
    "M1020": "Creality: AI-Kamera / Erkennung (Macro, modellabhängig).",
    "M1060": "Creality: Bett-Mesh / Leveling-Hilfe starten (Macro).",
    "M1070": "Creality: Druck fortsetzen (UI-Macro).",
    "M1080": "Creality: Druck pausieren (UI-Macro).",
    "M1081": "Creality: Druck stoppen (UI-Macro).",
}

# Varianten mit Parameter (zusätzliche Suchbegriffe)
MCODE_DOCS.update(
    {
        "M106 P0": "Teillüfter / Modell-Lüfter (am K2 oft P0) — S0–255.",
        "M106 P1": "Gehäuse- oder Kammerlüfter (am K2 oft P1).",
        "M106 P2": "Zusatzlüfter / Hilfslüfter (am K2 oft P2).",
        "G28": "Homing aller Achsen (G-Code, aber häufig gesucht).",
        "G29": "Automatisches Bett-Leveling / Mesh (G-Code).",
    }
)


def describe_mcode(code: str) -> str:
    key = code.strip().upper()
    if not key.startswith("M") and not key.startswith("G"):
        key = "M" + key.lstrip("M")
    return MCODE_DOCS.get(key, "Keine Beschreibung hinterlegt — ggf. Macro oder andere Firmware.")


def mcode_categories() -> list[tuple[str, list[str]]]:
    """Gruppen für sortierte Anzeige."""
    groups: list[tuple[str, list[str]]] = [
        ("Programm / Pause", ["M0", "M1", "M2", "M73", "M112", "M400", "M410", "M412", "M413"]),
        ("Motoren", ["M17", "M18", "M84", "M85"]),
        ("Temperatur", [
            "M104", "M109", "M140", "M190", "M141", "M191", "M192", "M143",
            "M301", "M302", "M303", "M304", "M305",
        ]),
        ("Lüfter", ["M106", "M107", "M106 P0", "M106 P1", "M106 P2"]),
        ("Extrusion / Speed", ["M82", "M83", "M218", "M220", "M221", "M600", "M603"]),
        ("Position / Anzeige", ["M114", "M115", "M117", "M118", "M119", "M120", "M121"]),
        ("Mesh / Offset", ["M48", "M206", "M207", "M208", "M211", "M290", "M420", "M421", "M851"]),
        ("Bewegung / Limits", ["M92", "M201", "M203", "M204", "M205"]),
        ("EEPROM / Config", ["M500", "M501", "M502", "M503"]),
        ("LED / Ton / Kamera", ["M150", "M240", "M300", "M355"]),
        ("TMC / Treiber", ["M569", "M900", "M906", "M913", "M914"]),
        ("Klipper / Macros", [
            "M486", "M808", "M876",
            "M810", "M811", "M812", "M813", "M814", "M815", "M816", "M817", "M818", "M819",
        ]),
        ("SD-Karte", ["M20", "M23", "M24", "M25", "M27", "M28", "M29", "M30", "M32"]),
        ("Sonstige", [
            "M16", "M42", "M80", "M81", "M280", "M401", "M402", "M404", "M405", "M406", "M407",
            "M425", "M428", "M566", "M584", "M665", "M666", "M999", "G28", "G29",
        ]),
        ("Creality / CFS (Macros)", [
            "M1002", "M1003", "M701", "M702", "M703", "M704",
            "M1020", "M1040", "M1041", "M1042", "M1043", "M1044",
            "M1060", "M1070", "M1080", "M1081",
        ]),
    ]
    return groups
