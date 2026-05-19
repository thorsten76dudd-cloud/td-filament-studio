"""Mehrere gespeicherte Drucker (SSH)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .printer_ssh import default_password

def _printers_file() -> Path:
    from app.paths import DATA_DIR

    return DATA_DIR / "printers.json"


PRINTERS_FILE = _printers_file()


@dataclass
class PrinterProfile:
    name: str
    host: str
    password: str
    model: str = "K2 Pro"

    @classmethod
    def from_dict(cls, d: dict) -> PrinterProfile:
        return cls(
            name=str(d.get("name", "Drucker")),
            host=str(d.get("host", "")),
            password=str(d.get("password", "")),
            model=str(d.get("model", "K2 Pro")),
        )


def load_printers() -> list[PrinterProfile]:
    if not PRINTERS_FILE.is_file():
        return []
    try:
        raw = json.loads(PRINTERS_FILE.read_text(encoding="utf-8"))
        return [PrinterProfile.from_dict(x) for x in raw.get("printers", [])]
    except Exception:
        return []


def save_printers(profiles: list[PrinterProfile]) -> None:
    PRINTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRINTERS_FILE.write_text(
        json.dumps({"printers": [asdict(p) for p in profiles]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def upsert_printer(profile: PrinterProfile) -> None:
    items = load_printers()
    for i, p in enumerate(items):
        if p.name == profile.name or (p.host and p.host == profile.host):
            items[i] = profile
            save_printers(items)
            return
    items.append(profile)
    save_printers(items)


def migrate_legacy_settings() -> None:
    """Importiert alte printer_settings.json einmalig."""
    legacy = PRINTERS_FILE.parent / "printer_settings.json"
    if not legacy.is_file() or load_printers():
        return
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
        host = str(data.get("host", "")).strip()
        if host:
            upsert_printer(
                PrinterProfile(
                    name="Mein K2",
                    host=host,
                    password=str(data.get("password") or default_password(data.get("printer", "K2"))),
                    model=str(data.get("printer", "K2 Pro")),
                )
            )
    except Exception:
        pass
