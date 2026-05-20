# GitHub — Kurz-Checkliste

**Aktuelle Version:** `1.5.52` · Release-Tag: `v1.5.52-stable`  
**Repo:** `thorsten76dudd-cloud/td-filament-studio`

## Vor dem Push

- [ ] Keine Secrets in Commits (`data/printers.json` bleibt lokal, siehe `.gitignore`)
- [ ] `creality_nfc/config.py` → `APP_VERSION` und `GITHUB_RELEASES_REPO` stimmen
- [ ] Tests optional: `python -m unittest discover -s tests -q`

## Release (Installer)

```powershell
build_setup.bat
powershell -File scripts\github_release.ps1
```

Lädt `installer_output\TD-Filament-Studio-Setup.exe` hoch und setzt **Latest**. Altes `-stable`-Release wird entfernt (Standard: vorheriges Tag in `scripts/github_release.ps1`).

## Nicht ins Git

| Pfad | Grund |
|------|--------|
| `data/printers.json`, `spools.json`, … | Persönlich / Passwörter |
| `dist/`, `build/`, `installer_output/` | Build-Artefakte |

Details zum aktuellen Stand: [STABLE-v1.5.52.md](STABLE-v1.5.52.md)
