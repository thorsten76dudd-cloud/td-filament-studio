# Sicherer Stand — TD Filament Studio v1.5.23

**Datum:** 2026-05-18

Dieser Stand umfasst die funktionierenden Features aus der Entwicklungsrunde:

- RFID: Tag lesen/schreiben/leeren, Chip duplizieren, Spule → RFID-Tab
- Tag-Schreiben ohne CFS; Profil aus „Meine Spulen“ / Filament-ID
- Post-Print: Filament-Abzug (Auto + „Verbrauch abziehen…“), Dialog-Buttons fix
- Spulen: mehrere UIDs, Chip entfernen, CFS-Slot-Verknüpfung
- Drucker: Monitor, Kamera, CFS-Dashboard
- Hilfe aktualisiert (`ui/help_content.py`)

## Wiederherstellen

- **Git:** `git checkout` / Tag `v1.5.23-stable` (falls gesetzt)
- **ZIP:** Ordner `snapshots/` auf dem Desktop unter `creality/`

Persönliche Daten liegen in `data/` (nicht im Git) — separat sichern über App: Datei → Daten sichern (ZIP).
