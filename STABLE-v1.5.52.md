# Aktueller Stand — TD Filament Studio v1.5.52

**GitHub Release:** [v1.5.52-stable](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/tag/v1.5.52-stable)

## Highlights

- **Material-DB:** nur vom Drucker (SSH), kein Cloud/Datei/Merge
- **Filament-Profil:** nur Lesen (Druckparameter in Creality Print ändern)
- **Meine Spulen:** Profil aus Material-DB, Farbe (Dialog/Presets), Bezeichnung „Marke — Material“, K2 Pro statt F008
- **Liste:** CFS 1A–1D oben (auch aus Bemerkung `CFS-S1` …), Rest alphabetisch
- **UI:** schärfere G-Code-Vorschau, Scrollposition in Dateilisten bleibt erhalten

## Build

```bat
build_setup.bat
```

- Installer: `installer_output\TD-Filament-Studio-Setup.exe`
- Portable: `dist\TD Filament Studio.exe`

## Release veröffentlichen

```powershell
powershell -File scripts\github_release.ps1
```

Entfernt automatisch das vorherige `-stable`-Release und legt `v1.5.52-stable` als Latest an.
