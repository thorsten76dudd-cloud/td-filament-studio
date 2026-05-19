"""Backup, Restore, CFS-RFID ZIP Import."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


def backup_data_dir(data_dir: Path, dest_zip: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in data_dir.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(data_dir.parent).as_posix())


def restore_data_dir(zip_path: Path, data_dir: Path) -> int:
    data_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            parts = Path(name).parts
            if parts[0] == "data" and len(parts) > 1:
                rel = Path(*parts[1:])
            else:
                rel = Path(name)
            if ".." in rel.parts:
                continue
            target = data_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            count += 1
    return count


def find_material_json_in_zip(zf: zipfile.ZipFile) -> str | None:
    for name in zf.namelist():
        low = name.lower().replace("\\", "/")
        if low.endswith("material_database.json"):
            return name
        if "/material_database/" in low and low.endswith(".json"):
            return name
    return None


def import_cfs_rfid_zip(zip_path: Path, data_dir: Path, printer_label: str) -> Path:
    """Extrahiert material_database.json aus CFS-RFID.zip nach data/."""
    from .db_store import db_path_for_printer, save_database

    data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        member = find_material_json_in_zip(zf)
        if not member:
            raise ValueError("Keine material_database.json in der ZIP gefunden.")
        raw = zf.read(member)
        data = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(data.get("result"), dict):
        raise ValueError("Ungültige material_database.json in der ZIP.")
    out = db_path_for_printer(data_dir, printer_label)
    save_database(out, data)
    return out


def default_backup_name() -> str:
    return f"spooltag_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"


_TEMPLATE_FILES = ("k2_pro.json", "k2_max.json", "printers.example.json")


def _read_install_templates(data_dir: Path) -> dict[str, bytes]:
    """Standard-JSON aus Bundle oder data/ vor dem Löschen sichern."""
    import sys

    out: dict[str, bytes] = {}
    sources: list[Path] = []
    if data_dir.is_dir():
        sources.append(data_dir)
    if getattr(sys, "frozen", False):
        bundle = Path(sys._MEIPASS) / "data"
        if bundle.is_dir():
            sources.append(bundle)
    else:
        from app.paths import APP_DIR

        dev_data = APP_DIR / "data"
        if dev_data.is_dir():
            sources.append(dev_data)
    for folder in sources:
        for name in _TEMPLATE_FILES:
            if name in out:
                continue
            path = folder / name
            if path.is_file():
                out[name] = path.read_bytes()
    return out


def _write_install_templates(data_dir: Path, templates: dict[str, bytes]) -> None:
    for name, raw in templates.items():
        dest_name = "printers.json" if name == "printers.example.json" else name
        (data_dir / dest_name).write_bytes(raw)


def factory_reset_data_dir(data_dir: Path) -> None:
    """
    Alle App-Daten löschen und Werkseinstellung wiederherstellen (wie frische Installation).
    """
    from creality_nfc.app_settings import AppSettings
    from creality_nfc.model_library import ModelLibrary

    templates = _read_install_templates(data_dir)
    if data_dir.is_dir():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    if templates:
        _write_install_templates(data_dir, templates)
    AppSettings().save(data_dir / "app_settings.json")
    ModelLibrary(data_dir / "model_library")
    (data_dir / "spools.json").write_text("[]\n", encoding="utf-8")
    (data_dir / "printer_settings.json").write_text("{}\n", encoding="utf-8")
