# TD Filament Studio

Deutsch · **[English](README.en.md)**

**Windows-Software für Creality K2 + CFS (Creality Filament System):** RFID/NFC-Tags beschreiben, Spulen verwalten, Filament-Rest tracken, Drucker live steuern.

| | |
|---|---|
| **Download** | [Releases → TD-Filament-Studio-Setup.exe](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/latest) |
| **Version** | 1.5.119 (`v1.5.119-stable`) |
| **Plattform** | Windows 10/11 |
| **Drucker** | K2 Pro, K2 Plus, K2, K2 Max, K2 SE + **CFS** (kein K1 / Hi) |

Programmiert **MIFARE Classic 1K**-Tags im Creality-Format (kompatibel mit CFS-Erkennung am Drucker). Basiert auf Community-Reverse-Engineering: [DnG-Crafts/K2-RFID](https://github.com/DnG-Crafts/K2-RFID).

> **Suchbegriffe / Keywords:** Creality K2 RFID, K2 Pro CFS NFC, Filament Spulenverwaltung Windows, MIFARE Classic 1K Creality Tag schreiben, CFS Slot 1A–1D, Spool manager, filament inventory, post-print usage deduct, G-Code filament check.

## Funktionen (Überblick)

- **RFID**: Tags lesen/schreiben, Stapelmodus, Verifikation, Tag-Export (JSON), Farbe aus Foto
- **Material-DB**: Import vom Drucker (SSH), Profil-Anzeige; Spulen mit Material-DB verknüpfen
- **Meine Spulen**: Inventar, CFS-Slot-Zuordnung, Restgewicht & Verbrauchshistorie
- **Drucker-Tab**: Live-CFS mit Spulen-Link, G-Code, Druck steuern (WebSocket :9999)
- **Modell-Bibliothek**: Ordner, Suche, Creality/3D-Viewer öffnen
- **Hilfe**: Hardware-Liste, Smartcard-Dienst, Tag-Halter-Links (Printables)

## Hardware (kurz)

| Was | Empfehlung |
|-----|------------|
| Tags | MIFARE Classic **1K**, **25 mm** rund (z. B. MF1 S50) |
| Reader | **ACS ACR122U** (oder PC/SC-kompatibel) |
| PC | Windows 10/11, Dienst **Smartcard** (SCardSvr) aktiv |

Details in der App: Tab **Hilfe** → Programm-Anleitung.

## Schnellstart (Entwicklung)

```bat
cd cfs-rfid-tool
python -m pip install -r requirements.txt
copy data\printers.example.json data\printers.json
REM printers.json bearbeiten (IP, Passwort)
python main.py
```

## Portable EXE bauen

```bat
build_exe.bat
```

Ergebnis: `dist\TD Filament Studio\TD Filament Studio.exe` — beim ersten Start wird `data\` neben die EXE kopiert (falls noch nicht vorhanden).

## Windows-Installer

1. `build_exe.bat`
2. [Inno Setup 6](https://jrsoftware.org/isinfo.php) installieren
3. `build_setup.bat`

Ergebnis: `installer_output\TD-Filament-Studio-Setup.exe`

## Daten & Privatsphäre

Laufzeitdaten liegen in `data\` (neben der EXE oder im Projektordner):

| Datei | Inhalt |
|-------|--------|
| `printers.json` | **IP, SSH-Passwort** — nicht veröffentlichen! |
| `k2_pro.json` | Material-Datenbank |
| `spools.json` | Meine Spulen |
| `app_settings.json` | Einstellungen |
| `app.log` | Fehlerprotokoll (bei Absturz) |

Vor Git-Commit: `printers.json` bleibt per `.gitignore` lokal. Vorlage: `data/printers.example.json`.

## Lizenz

MIT — siehe [LICENSE](LICENSE). Creality-Tag-Format: Community-Reverse-Engineering (K2-RFID).
