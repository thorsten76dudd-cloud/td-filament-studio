# TD Filament Studio — v1.5.126-stable

**Release-Tag:** `v1.5.126-stable`  
**Datum:** 2026-05-25

## Fix: Druck mit gleichem Dateinamen zweimal

- Wenn derselbe G-Code (z. B. `Koerper1.gcode`) mehrfach gedruckt wird, wurde der zweite Druck **nicht** in die Druck-Historie eingetragen, weil der Filename-Lock (`post_print_deduct_handled`) den Auto-Dialog blockiert hat
- Lock wird jetzt automatisch entfernt, sobald ein neuer Druck startet (Phase `idle/complete` → `printing`) — der Auto-Dialog erscheint dann am Druckende erneut
- Auch wenn der Auto-Vorschlag scheitert (kein verknüpfter Slot, kein Filament-Gewicht), wird der Druck ab sofort in die Druck-Historie geschrieben — manueller Abzug per **„Verbrauch nachträglich…“** möglich

## Enthalten

- Sync-Pfad mit Catch-up (v1.5.125)
- Kamera-Watchdog (v1.5.124)
- Hintergrund (Tray) optional (v1.5.123)
- Filament-Abzug ohne Tab-Wechsel (v1.5.122)
