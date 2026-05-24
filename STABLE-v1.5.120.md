# TD Filament Studio — v1.5.120-stable

**Release-Tag:** `v1.5.120-stable`  
**Datum:** 2026-05-24

## Fix: Druck-Historie — richtiger Slot/Spule

- Historie nutzt den **Abzug-Dialog** (G-Code-Slot), nicht die Drucker-Meldung (oft falsch, z. B. 1D statt 1C)
- Anzeige: `1C · Creality — CR-PETG` bei mehreren gleich benannten PETG-Spulen
- **Alte Einträge** werden beim Öffnen der Historie aus der verknüpften Spule korrigiert

## Enthalten

- Monitor 100 % / Filament-Abzug (v1.5.119), Druck-Check überall (v1.5.118)
