# TD Filament Studio — v1.5.117-stable

**Release-Tag:** `v1.5.117-stable`  
**Datum:** 2026-05-20

## Stabilität

- Unit-Tests (G-Code, Druck-Check, Historie) grün vor Release
- Fokus: automatischer Druck-Check mit vollem G-Code vom Drucker

## Neu / verbessert

### Druck-Check (automatisch)
- **G-Code vom Drucker per SSH** — wenn keine lokale Datei oder nur Vorschau-Kopf: Download in `data/gcode_cache/` vor dem Check
- **Creality Print 7.x Footer** — große Jobs (>500 g) und einzelnes Filament in Slot 1C/1D (z. B. `T2`) werden korrekt zugeordnet
- Weiterhin automatische Suche in **Downloads**, **Desktop** und Cache

### Enthalten (v1.5.116)
- Druck-Historie: Verbrauch nachträglich abziehen
- 4× CFS Demo, Standort-Farbfeld, G-Code Mehrfarben/Footer

## Bekannte Grenzen

- SSH/Root-Passwort wie beim „Herunterladen…“ nötig für Auto-Download
- Demo-Modus (4 CFS) nur Anzeige

## Build & Release

```bat
build_setup.bat
scripts\github_release.ps1 -Version 1.5.117 -Tag v1.5.117-stable -RemoveTag v1.5.116-stable
```
