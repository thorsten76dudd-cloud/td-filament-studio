# TD Filament Studio — v1.5.121-stable

**Release-Tag:** `v1.5.121-stable`  
**Datum:** 2026-05-24

## Fix: Monitor bleibt bei 74 % / 98 % stehen

- **Ursache:** Restzeit in Heartbeats lief weiter, obwohl Fortschritt/Layer stehen blieben — kein frischer Abruf
- **Lösung:** Stale-Erkennung ohne Restzeit; bei hängendem Fortschritt (~20 s) automatisch beim Drucker nachfragen
- Gilt für **jeden** Fortschritt (nicht nur ab 95 %)

## Enthalten

- Historie Slot/Spule (v1.5.120), Druck-Check, Auto G-Code
