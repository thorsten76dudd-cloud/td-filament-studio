# TD Filament Studio — v1.5.118-stable

**Release-Tag:** `v1.5.118-stable`  
**Datum:** 2026-05-20

## Stabilität

- 150 Unit-Tests grün vor Release

## Neu / verbessert

### Druck-Check überall gleich
- **Monitor**, **Dateien** und **RFID-Tab** — alle Druck-Check-Buttons nutzen dieselbe Logik
- Datei: markiert in der Liste → zuletzt gewählt → **laufender Druck** (ohne erneutes Anklicken in Dateien)
- Automatischer G-Code-Download per SSH/Cache wie in v1.5.117

### Enthalten (v1.5.117)
- Creality Print 7.x Footer, große Jobs (>500 g), Slot 1C/1D
- Historie nachträglich, 4× CFS Demo, Standort-Farben

## Build & Release

```bat
build_setup.bat
scripts\github_release.ps1 -Version 1.5.118 -Tag v1.5.118-stable -RemoveTag v1.5.117-stable
```
