# TD Filament Studio — v1.5.122-stable

**Release-Tag:** `v1.5.122-stable`  
**Datum:** 2026-05-24

## Fix: Filament-Abzug ohne Tab-Wechsel

- Drucker meldet oft weiter **„Druck läuft“** mit **0 %**, obwohl der Job fertig ist
- **Filament-Abzug** startet jetzt auch dann (Peak war z. B. 74 %, jetzt 0 %)
- Kein Zurücksetzen des Abzug-Dialogs bei jedem Poll mehr
- Schnellere Nachfrage beim Drucker (~12 s)

## Enthalten

- Monitor-Stale-Fix (v1.5.121), Historie Slot (v1.5.120)
