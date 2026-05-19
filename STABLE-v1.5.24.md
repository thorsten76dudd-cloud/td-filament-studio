# Sicherer Stand — TD Filament Studio v1.5.24

**Datum:** 2026-05-19

Dieser Stand baut auf v1.5.23 auf:

- **Import:** Block „Import — Material-Datenbank“ oben im Tab Material-DB; Menü **Datei → Import**
- **Layout:** Statusleiste unten nicht mehr abgeschnitten (Pack-Reihenfolge)
- **Tag-Schutz:** Einstellung „Tag vor Überschreiben schützen“
- **Slicer:** Orca/Creality JSON importieren (`creality_nfc/slicer_import.py`)
- **G-Code:** Bessere Gramm-Schätzung, Cache unter `data/gcode_cache`
- **Hilfe** aktualisiert

## Wiederherstellen

- **Git:** `git checkout v1.5.24-stable`
- **Portable EXE:** `dist\TD Filament Studio.exe` (nach `build_exe.bat`)
- **ZIP:** `snapshots\TD-Filament-Studio-v1.5.24-stable.zip` (Quellcode-Archiv)

Persönliche Daten in `data/` — separat sichern: **Datei → Daten sichern (ZIP)**.
