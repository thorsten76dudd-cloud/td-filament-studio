# TD Filament Studio v1.5.63

**Release:** [v1.5.63-stable](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/tag/v1.5.63-stable)

## Fix: In-App-Update (Installer startet wirklich)

- **Ursache:** `taskkill /T` hat den Installer-Helfer (cmd/wscript) mit beendet
- **Lösung:** WScript-Launcher + `taskkill` ohne `/T`; Setup in `%LOCALAPPDATA%\TD Filament Studio\Updates\`
- Installer mit `/FORCECLOSEAPPLICATIONS` (weniger „trotzdem installieren“)
- Log: `data\update_install.log`

## Hinweis SmartScreen

Beim ersten Start kann Windows „Trotzdem ausführen“ verlangen (kein Code-Signing).

## Aus 1.5.62

- Creality-Autostart; 1.5.61 Update-Versuch; 1.5.60 Drucker-Hinweise
