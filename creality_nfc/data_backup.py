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


def default_model_library_backup_name() -> str:
    return f"modell_bibliothek_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"


def _model_library_arcname(library_root: Path, file_path: Path) -> str:
    return file_path.relative_to(library_root).as_posix()


def _model_library_target_path(library_root: Path, zip_name: str) -> Path | None:
    name = zip_name.replace("\\", "/").lstrip("/")
    if name.endswith("/"):
        return None
    parts = Path(name).parts
    if parts and parts[0] == "model_library":
        rel = Path(*parts[1:])
    else:
        rel = Path(*parts)
    if not rel.parts or ".." in rel.parts:
        return None
    return library_root / rel


def backup_model_library(library_root: Path, dest_zip: Path) -> int:
    """Komplette Modell-Bibliothek (index.json, files/, folders/) als ZIP."""
    library_root.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in library_root.rglob("*"):
            if path.is_file():
                zf.write(path, _model_library_arcname(library_root, path))
                count += 1
    return count


def restore_model_library(zip_path: Path, library_root: Path) -> int:
    """Bibliothek aus ZIP zurückspielen (überschreibt vorhandene Dateien)."""
    library_root.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            target = _model_library_target_path(library_root, name)
            if not target:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(name))
            count += 1
    return count


_EMPTY_MATERIAL_DB = json.dumps({"result": {"list": [], "count": 0}}, ensure_ascii=False) + "\n"


def _write_fresh_data_files(data_dir: Path) -> None:
    """Leerer Werkzustand — keine Beispiel-Drucker, keine mitgelieferte Material-DB."""
    (data_dir / "printers.json").write_text('{"printers": []}\n', encoding="utf-8")
    for name in ("k2_pro.json", "k2_max.json"):
        (data_dir / name).write_text(_EMPTY_MATERIAL_DB, encoding="utf-8")
    (data_dir / "spools.json").write_text("[]\n", encoding="utf-8")
    (data_dir / "printer_settings.json").write_text("{}\n", encoding="utf-8")


def factory_reset_data_dir(data_dir: Path) -> None:
    """
    Alle App-Daten löschen und Werkseinstellung wiederherstellen (wie frische Installation).
    """
    from creality_nfc.app_settings import AppSettings
    from creality_nfc.model_library import ModelLibrary

    if data_dir.is_dir():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_fresh_data_files(data_dir)
    settings = AppSettings()
    settings.setup_completed = False
    settings.show_setup_on_startup = True
    settings.preferred_reader = ""
    settings.save(data_dir / "app_settings.json")
    ModelLibrary(data_dir / "model_library")
