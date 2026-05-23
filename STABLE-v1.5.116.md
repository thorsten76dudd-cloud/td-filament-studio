# TD Filament Studio — v1.5.116-stable

**Release-Tag:** `v1.5.116-stable`  
**Datum:** 2026-05-23

## Stabilität

- 148 Unit-Tests (alle grün vor Release)
- Fokus dieser Serie: CFS-Multi-Box-Vorschau, Druck-Historie, Spulen-Standort, Layout

## Neu / verbessert

### Druck-Historie
- **Verbrauch nachträglich…** — vergessenen Abzug aus der Historie nachholen
- Historie speichert Abzug zuverlässig (stabile IDs, kein Überschreiben der Notiz)
- Anzeige: `50 g` = abgezogen, `~46 g` = nur G-Code-Schätzung
- Widersprüchliche Einträge (Gramm + „kein Abzug“) werden korrigiert

### CFS / UI
- **4× CFS Demo** — kompakte 4×4-Übersicht (Zeilen CFS 1–4, Spalten A–D)
- Ein echtes CFS: weiterhin eine Zeile 1A–1D
- Spulen-Dropdown nur echte Slots (1A–1D bei einem CFS)

### Meine Spulen
- **Standort-Übersicht** — Farbfeld pro Spule

### Drucker (bestehend, stabilisiert)
- G-Code-Footer / Mehrfarben-Verbrauch
- Druck-Check mit Farbzuordnung
- Fenstergröße wird gespeichert

## Bekannte Grenzen

- Demo-Modus (4 CFS) nur Anzeige — kein RFID/Zufuhr an den Drucker
- Nachträglicher Abzug nutzt G-Code-Cache (`data/gcode_cache/`) — ohne Datei: manuelle Spule/Gramm wählen

## Build & Release

```bat
build_setup.bat
powershell -File scripts\github_release.ps1
```
