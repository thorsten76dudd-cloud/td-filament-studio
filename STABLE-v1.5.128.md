# TD Filament Studio — v1.5.128-stable

**Release-Tag:** `v1.5.128-stable`  
**Datum:** 2026-05-26

## Fix: Abzug-Dialog kommt nach App-Update / -Restart zuverlässig

In v1.5.127 wurde der persistente Filename-Lock (`settings.post_print_deduct_handled`) nur dann aufgelöst, wenn die App einen **echten** Druckstart sah (neuer G-Code oder frisch aus `idle/complete` mit kleinem Fortschritt). Zwei Fälle blieben offen:

1. **App-Update mitten im Druck:** App startet neu, Druck ist beim ersten Snap bereits `complete` → der Code-Pfad mit Lock-Reset wurde nie betreten → Dialog blieb aus.
2. **App verbindet bei einem laufenden Druck mit hohem Fortschritt:** `fresh_print_start` war `False` (Fortschritt > 5 %), der Lock vom Vorgängerdruck wurde nicht entfernt → am Druckende kein Dialog.

**Fix:**

- Beim **Initial-Sync** wird der Filename-Lock fallengelassen, sobald `printer_job_looks_finished` einen Druck als fertig erkennt — der Dialog kommt auch dann, wenn die App in einer früheren Session denselben Filename schon verarbeitet hatte.
- Beim **Übergang in `printing`** (oder neuem Filename) wird der Lock **immer** aufgelöst, unabhängig vom Fortschritt. Das hängt einen laufenden Druck nicht mehr an alten Lock-Einträgen auf.
- Der konservative Session-Reset (`_post_print_deduct_offered_for`, `_peak_print_progress`, `_last_print_progress`) bleibt unverändert — kein Doppel-Trigger bei Phase-Flicker.

## Enthalten

- Anzeige bei 0 %-Glitch zeigt Peak (v1.5.127)
- Doppel-Dialog verhindert (v1.5.127)
- Stuck-at-Zero-Fix beim Druckstart (v1.5.127)
- Filename-Lock-Reset bei neuem Druck (v1.5.126)
- Sync-Pfad mit Catch-up (v1.5.125)
- Kamera-Watchdog (v1.5.124)
- Hintergrund (Tray) optional (v1.5.123)
