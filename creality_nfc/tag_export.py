"""Tag-Lesedaten als JSON exportieren."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def build_tag_export(
    *,
    uid: str,
    parsed: dict[str, str],
    color_hex: str = "",
    weight_label: str = "",
    serial: str = "",
    printer_model: str = "",
    material_brand: str = "",
    material_name: str = "",
    filament_id: str = "",
) -> dict:
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "format": "td-filament-studio-tag-v1",
        "uid": uid,
        "parsed_tag": dict(parsed),
        "app_fields": {
            "filament_id": filament_id or parsed.get("material_id", ""),
            "color_hex": color_hex.lstrip("#").upper()[:6],
            "weight_label": weight_label,
            "serial": serial or parsed.get("serial", ""),
            "printer_model": printer_model or parsed.get("printer", ""),
            "material_brand": material_brand,
            "material_name": material_name,
        },
    }


def save_tag_export(data: dict, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
