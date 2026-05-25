# TD Filament Studio — v1.5.124-stable

**Release-Tag:** `v1.5.124-stable`  
**Datum:** 2026-05-25

## Fix: Kamera friert nicht mehr ein

- Live-Kamera (WebRTC) baut sich automatisch neu auf, wenn der Drucker den Video-Stream pausiert
- Watchdog im Kamera-Fenster prüft alle Frames; nach 8 s Stillstand kommt eine Warnung, nach 12 s lädt das Fenster neu
- ICE-Disconnect/Closed löst sauberen Reconnect aus statt dauerhaft „warte auf Video …“
- Kein manueller Klick auf „Verbinden“ mehr nötig, nur weil die Kamera hängt

## Enthalten

- Hintergrund (Tray) optional (v1.5.123)
- Filament-Abzug ohne Tab-Wechsel (v1.5.122)
- Monitor-Stale-Fix (v1.5.121), Historie Slot (v1.5.120)
