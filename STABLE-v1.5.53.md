# Aktueller Stand — TD Filament Studio v1.5.53

**GitHub Release:** [v1.5.53-stable](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/tag/v1.5.53-stable)

## Neu in 1.5.53

- **Mit Creality Print starten:** Wächter erkennt die GUI korrekt (nicht mehr die eigene Hintergrund-EXE).
- **Windows-Autostart:** Helfer läuft nach Anmeldung, wenn die Option aktiv ist — TD muss nicht zuerst geöffnet werden.
- Beim Deaktivieren der Option wird der Wächter beendet.

## Weiterhin aus 1.5.52

- Spulen: Profil aus Material-DB, Farbe per Dialog/Presets, K2 Pro statt F008, CFS 1A–1D oben
- Filament-Profil nur Lesen; Material-DB per SSH vom Drucker
- G-Code-Vorschau schärfer; Dateilisten behalten Scrollposition

## Release

```powershell
.\scripts\github_release.ps1
```

Entfernt automatisch `v1.5.52-stable` und legt `v1.5.53-stable` als Latest an.
