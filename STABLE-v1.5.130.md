# TD Filament Studio — v1.5.130-stable

**Release-Tag:** `v1.5.130-stable`  
**Datum:** 2026-05-26

## Fix: Tippfehler und Release-Workflow

- **Drucker-Dashboard:** Button hieß „DB vergleigen" — jetzt korrekt **„DB vergleichen"**.
- **Release-Skript** (`scripts/github_release.ps1`): Alte `-stable`-Releases bleiben ab sofort **standardmäßig auf GitHub erhalten**. Wer ein bestimmtes älteres Release entfernen will, kann `-RemoveTag <tag>` mitgeben; `-DeleteAllOldReleases` löscht alles außer dem aktuellen.

## Enthalten

- Doppel-Dialog beim Reconnect verhindert (v1.5.129)
- Filename-Lock-Reset im Initial-Sync (v1.5.128)
- Anzeige bei 0 %-Glitch zeigt Peak (v1.5.127)
- Stuck-at-Zero-Fix beim Druckstart (v1.5.127)
- Filename-Lock-Reset bei neuem Druck (v1.5.126)
- Sync-Pfad mit Catch-up (v1.5.125)
- Kamera-Watchdog (v1.5.124)
- Hintergrund (Tray) optional (v1.5.123)
