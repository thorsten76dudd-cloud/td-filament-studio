# TD Filament Studio v1.5.61

**Release:** [v1.5.61-stable](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/tag/v1.5.61-stable)

## Fix: In-App-Update Installation

- Nach dem Download startet der **Installer zuverlässig**, auch wenn die App sich beendet
- Ursache: Installer-Prozess wurde mit der App mitbeendet (`os._exit` / Prozess-Job)
- Lösung: verzögerter Start über separates CMD-Skript + Prozess-Trennung
- Prüfung der Setup-EXE vor Installation (Größe + gültige EXE)

## Aus 1.5.60

- Drucker Pause/Fehler-Hinweise; Tag-Halter STLs; Thingiverse/Amazon-Links
