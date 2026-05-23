"""CFS-UI-Hilfen (Slot-Listen für Comboboxen)."""

from __future__ import annotations

from typing import Any

from creality_nfc.cfs_layout import cfs_slot_label


def cfs_slot_combobox_values(box_count: int = 1) -> list[str]:
    """Leer + 1A…nD je nach Anzahl CFS-Einheiten am Drucker (1–4)."""
    n = max(1, min(4, int(box_count or 1)))
    return ["", *[cfs_slot_label(b, i) for b in range(1, n + 1) for i in range(4)]]


def cfs_box_count_from_app(app: Any, *, include_preview: bool = False) -> int:
    """Anzahl CFS für Spulen-Dropdown — Demo zählt nicht (nur echter Drucker)."""
    panel = getattr(app, "_device_panel", None) or getattr(app, "_printer_device_panel", None)
    if panel is None:
        return 1
    layout = getattr(panel, "_cfs_layout", None)
    real = max(1, layout.box_count()) if layout is not None else 1
    if include_preview:
        prev = getattr(panel, "_cfs_preview_boxes", None)
        if prev and prev >= 2:
            return int(prev)
    return min(4, real)
