# TD Filament Studio — v1.5.139-stable

**Release-Tag:** `v1.5.139-stable`

## Änderungen (In-App-Update)

- Setup immer in `%LOCALAPPDATA%\TD Filament Studio\Updates` (nicht `%TEMP%`).
- Installer-Start über **drei Wege**: direkter Prozess, ShellExecute, verzögerter CMD + Windows-Aufgabe.
- Kein `taskkill` mehr vor Installer-Start (Inno `/FORCECLOSEAPPLICATIONS`).
- Systemdialog „Setup wird jetzt gestartet“ mit Pfad zur Notfall-BAT.
