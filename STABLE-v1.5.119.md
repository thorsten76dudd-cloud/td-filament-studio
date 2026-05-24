# TD Filament Studio — v1.5.119-stable

**Release-Tag:** `v1.5.119-stable`  
**Datum:** 2026-05-20

## Fix: Druckende am Monitor

- **Problem:** Bei 98–99 % blieb die Anzeige stehen; erst Tab-Wechsel zeigte 100 % und Filament-Abzug
- **Ursache:** Heartbeats mit gleichem Fortschritt haben Live-Aktualisierung blockiert
- **Lösung:** Druck-Telemetrie nur bei echter Änderung; ab 95 % automatische Nachfrage beim Drucker

## Enthalten

- Druck-Check überall (v1.5.118), Auto G-Code (v1.5.117)
