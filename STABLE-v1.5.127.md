# TD Filament Studio — v1.5.127-stable

**Release-Tag:** `v1.5.127-stable`  
**Datum:** 2026-05-26

## Fix: Doppel-Dialog & falscher Abzug beim Druckstart

- **Doppel-Trigger beendet:** Der Reset von `_post_print_deduct_offered_for` und der Filename-Lock werden jetzt nur noch beim echten Druckstart ausgeführt (neuer G-Code **oder** Phase frisch aus `idle/complete` mit kleinem Fortschritt). Phase-Flicker mitten im Druck (z. B. kurzes `idle` durch Firmware-Anomalie) löst keinen erneuten Dialog mehr aus.
- **Kein falscher Dialog beim Start:** Beim Beginn eines neuen Drucks wird `_last_print_progress` zusätzlich auf `0` zurückgesetzt. Damit kann die „stuck at zero"-Heuristik nicht mehr durch den Fortschrittswert des vorherigen Drucks (z. B. `100`) fälschlich feuern.

## Fix: Anzeige bei „0 % obwohl fast fertig"

- Wenn der Drucker am Ende eines Jobs `progress=0` meldet (Firmware-Glitch), zeigt der Drucker-Tab jetzt den letzten Peak-Wert mit Hinweis `~99 % (Drucker meldet 0 %)` — kein Verwechseln mit einem Neustart mehr.

## Enthalten

- Filename-Lock-Reset bei neuem Druck (v1.5.126)
- Sync-Pfad mit Catch-up (v1.5.125)
- Kamera-Watchdog (v1.5.124)
- Hintergrund (Tray) optional (v1.5.123)
