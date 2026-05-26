# TD Filament Studio — v1.5.129-stable

**Release-Tag:** `v1.5.129-stable`  
**Datum:** 2026-05-26

## Fix: Doppel-Dialog beim Neu-Verbinden mit fertigem Druck

In v1.5.128 wird beim Initial-Sync nach Reconnect der Filename-Lock entfernt und der Abzug-Dialog gestartet — gut. **Aber:** `_post_print_deduct_offered_for` wurde dabei nicht gesetzt. Beim nächsten Snap (Sekunden später) prüfte `_maybe_catch_up_post_print_deduct`:
- Lock → leer (gerade entfernt) → kein Block
- `_post_print_deduct_offered_for` → leer → kein Block
- `printer_job_looks_finished` → True

→ **Dialog #2 wurde ausgelöst**, obwohl Dialog #1 noch offen war / gerade verarbeitet wurde.

**Fix:** `_post_print_deduct_offered_for = fname` wird jetzt **direkt in `_request_post_print_deduct`** gesetzt, sobald der Lock-Check passiert ist. Damit erkennt jeder nachfolgende Pfad (Initial-Sync, Catch-up, normales `_apply_print_status`), dass für diese Datei bereits ein Dialog ausgelöst wurde — egal welcher Codepfad ihn zuerst angestoßen hat.

## Enthalten

- Filename-Lock-Reset im Initial-Sync (v1.5.128)
- Anzeige bei 0 %-Glitch zeigt Peak (v1.5.127)
- Stuck-at-Zero-Fix beim Druckstart (v1.5.127)
- Filename-Lock-Reset bei neuem Druck (v1.5.126)
- Sync-Pfad mit Catch-up (v1.5.125)
- Kamera-Watchdog (v1.5.124)
- Hintergrund (Tray) optional (v1.5.123)
