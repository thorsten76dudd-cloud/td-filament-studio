# TD Filament Studio

**[Deutsch](README.md)** · English

**Windows software for Creality K2 + CFS (Creality Filament System):** write RFID/NFC tags, manage spools, track remaining filament, control the printer live.

| | |
|---|---|
| **Download** | [Releases → TD-Filament-Studio-Setup.exe](https://github.com/thorsten76dudd-cloud/td-filament-studio/releases/latest) |
| **Version** | 1.5.130 (`v1.5.130-stable`) |
| **Platform** | Windows 10/11 |
| **Printers** | K2 Pro, K2 Plus, K2, K2 Max, K2 SE + **CFS** (not K1 / Hi) |

Programs **MIFARE Classic 1K** tags in Creality format (CFS-compatible). Based on [DnG-Crafts/K2-RFID](https://github.com/DnG-Crafts/K2-RFID).

> **Search keywords:** Creality K2 RFID, K2 Pro CFS NFC, filament spool manager Windows, MIFARE Classic Creality tag writer, CFS slot 1A–4D, spool inventory, post-print filament deduct, G-code print check.

> **UI language:** The application interface is currently **German only**. This README is for developers and international visitors.

## Features

- **RFID:** Read/write tags, batch mode, verification, tag export (JSON), color from photo
- **Material DB:** Creality Cloud, import from printer (SSH), profile editor, overwrite protection
- **My spools:** Inventory, CFS slot mapping, remaining weight & usage history
- **Printer tab:** Live CFS with spool links, G-code, print control (WebSocket port 9999)
- **Model library:** Folders, search, open in Creality / 3D viewer
- **Help:** Hardware list, smart card service, tag holder links (Printables)

## Hardware (quick reference)

| Item | Recommendation |
|------|----------------|
| Tags | MIFARE Classic **1K**, **25 mm** round (e.g. MF1 S50) |
| Reader | **ACS ACR122U** (or any PC/SC-compatible reader) |
| PC | Windows 10/11, **Smart Card** service (SCardSvr) running |

More detail in the app: **Help** tab → program guide.

## Quick start (development)

```bat
cd cfs-rfid-tool
python -m pip install -r requirements.txt
copy data\printers.example.json data\printers.json
REM Edit printers.json (IP, password)
python main.py
```

## Build portable EXE

```bat
build_exe.bat
```

Output: `dist\TD Filament Studio.exe` — on first run, `data\` is copied next to the EXE if it does not exist yet.

## Windows installer

1. Run `build_exe.bat`
2. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php)
3. Run `build_setup.bat`

Output: `installer_output\TD-Filament-Studio-Setup.exe`

## Data & privacy

Runtime data lives in `data\` (next to the EXE or in the project folder):

| File | Contents |
|------|----------|
| `printers.json` | **IP, SSH password** — do not publish! |
| `k2_pro.json` | Material database |
| `spools.json` | Spool inventory |
| `app_settings.json` | App settings |
| `app.log` | Error log (on crash) |

Before committing to Git: `printers.json` stays local via `.gitignore`. Template: `data/printers.example.json`.

## License

MIT — see [LICENSE](LICENSE). Creality tag format: community reverse engineering (K2-RFID).
