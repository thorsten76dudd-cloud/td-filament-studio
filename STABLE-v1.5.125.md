# TD Filament Studio — v1.5.125-stable

**Release-Tag:** `v1.5.125-stable`  
**Datum:** 2026-05-25

## Fix: Filament-Abzug nach App-Neustart

- Wenn der Druck **bei geschlossener App** fertig wird, kommt der Abzug-Dialog jetzt **direkt beim nächsten Start** statt erst nach mehreren Reconnects
- Sync-Pfad wartet auf einen aussagekräftigen Snapshot (Job-Daten oder Phase ≠ idle), maximal 25 s
- Catch-up nach Sync: erkennt einen abgeschlossenen Druck auch dann, wenn der erste Snapshot leer war
- Kein Doppel-Trigger pro Datei (`post_print_deduct_handled` greift)

## Enthalten

- Kamera-Watchdog (v1.5.124)
- Hintergrund (Tray) optional (v1.5.123)
- Filament-Abzug ohne Tab-Wechsel (v1.5.122)
