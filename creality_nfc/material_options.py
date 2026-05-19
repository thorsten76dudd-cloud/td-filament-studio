"""Export K1-style material_options.json from material_database."""

from __future__ import annotations

import json
from pathlib import Path


def build_material_options(db_data: dict) -> dict:
    """Simplified menu structure for K1 printers."""
    brands: dict[str, list[str]] = {}
    for item in db_data.get("result", {}).get("list", []):
        base = item.get("base", {})
        brand = str(base.get("brand", "Generic")).strip() or "Generic"
        name = str(base.get("name", "")).strip()
        mtype = str(base.get("meterialType", base.get("materialType", ""))).strip()
        label = name or mtype
        if not label:
            continue
        brands.setdefault(brand, [])
        if label not in brands[brand]:
            brands[brand].append(label)

    options = []
    for brand in sorted(brands, key=str.lower):
        options.append(
            {
                "brand": brand,
                "materials": sorted(brands[brand], key=str.lower),
            }
        )
    return {"version": 1, "brands": options}


def export_material_options(db_data: dict, path: Path) -> None:
    data = build_material_options(db_data)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
