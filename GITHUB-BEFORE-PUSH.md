# Vor GitHub-Upload — Checkliste

**Stand:** v1.5.25-stable (`d74e8c9`) · Remote noch **nicht** konfiguriert.

Diese Datei sammelt offene Punkte, bis das Repo öffentlich (oder privat) auf GitHub liegt.

---

## 1. Deine Tests (vor dem Push)

Während du testest, kurz notieren (OK / Fehler):

- [ ] App-Start → Tab **Drucker** → Kamera startet ohne Trennen/Verbinden
- [ ] Tab **Monitor** → „Aktueller Druck“ zeigt Datei/Fortschritt ohne Tab-Wechsel
- [ ] RFID: Tag lesen, schreiben, leeren (Spule → RFID-Tab)
- [ ] Post-Print: **Verbrauch abziehen…** oder Auto-Abzug nach Druck
- [ ] **Datei → Import** / Material-DB (Cloud, SSH, Slicer JSON)
- [ ] **Meine Spulen** speichern, CFS-Slot
- [ ] Statusleiste unten voll sichtbar (alle Tabs)
- [ ] **Datei → Daten sichern (ZIP)** funktioniert

**Gefundene Bugs:** _(hier eintragen)_

---

## 2. Repo vorbereiten (einmalig)

- [ ] GitHub-Repo anlegen (öffentlich oder privat)
- [ ] README prüfen (Version/Hinweise aktuell — ggf. 1.5.25 erwähnen)
- [ ] Sicherstellen: **keine** IPs/Passwörter im Code oder in Commits  
      (`data/printers.json` etc. sind in `.gitignore`)
- [ ] Optional: `git log` durchsehen — keine Secrets in alten Commits
- [ ] Optional: **GitHub Release** mit portable EXE (`dist\` ist nicht im Git — EXE manuell an Release hängen)

---

## 3. Hochladen (wenn Tests OK)

Im Ordner `cfs-rfid-tool` (nach `gh auth login` oder mit HTTPS):

```bat
git remote add origin https://github.com/DEIN_USER/DEIN_REPO.git
git push -u origin master
git push origin v1.5.23-stable v1.5.24-stable v1.5.25-stable
```

**Tags mitpushen**, damit stabile Stände auf GitHub sichtbar sind.

Optional Release auf GitHub:

- Tag `v1.5.25-stable` → Asset: `TD Filament Studio.exe` aus `dist\`
- ZIP-Backup liegt lokal: `..\snapshots\TD-Filament-Studio-v1.5.25-stable.zip` (nicht automatisch auf GitHub)

---

## 4. Nicht ins GitHub-Repo (bewusst lokal)

| Pfad | Grund |
|------|--------|
| `data/printers.json`, `spools.json`, `app_settings.json` | Persönlich / Passwörter |
| `dist/`, `build/`, `installer_output/` | Build-Artefakte |
| `creality/snapshots/*.zip` | Liegt **neben** dem Projektordner |

---

## 5. Optional später (nach erstem Push)

- [ ] GitHub Actions: Tests (`pytest`) bei Push
- [ ] Windows-Installer bauen + Release-Asset
- [ ] Orca-Ordner Auto-Import
- [ ] Issues aus deiner Test-Liste

---

## Aktueller Git-Stand

| Tag | Inhalt |
|-----|--------|
| `v1.5.23-stable` | RFID, Spulen, Post-Print, Hilfe |
| `v1.5.24-stable` | Import-UI, Slicer, G-Code-Gramm, Layout |
| `v1.5.25-stable` | Kamera-Start nach App-Start |

**Letzter Commit:** `d74e8c9` — Release v1.5.25

Wenn nach deinen Tests noch Fixes nötig sind: zuerst committen/taggen (`v1.5.26-stable`), **dann** erst `git push`.
