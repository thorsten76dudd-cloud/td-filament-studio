"""Temporäre CFS-Vorschau (UI-Test ohne mehrere echte CFS am Drucker)."""

from __future__ import annotations

from typing import Any

SIM_MARKER = "__td_sim_cfs"


def build_simulated_boxs_info(box_count: int = 4) -> dict[str, Any]:
    """Fake boxsInfo mit 1–4 CFS-Boxen × je 4 Slots (nur Anzeige)."""
    n = max(2, min(4, int(box_count or 4)))
    palette = (
        ("Orange", "PETG", "FF8000"),
        ("Blau", "PETG", "0000FF"),
        ("Grün", "PLA", "00AA00"),
        ("Grau", "ASA", "808080"),
    )
    boxes: list[dict[str, Any]] = []
    for bid in range(1, n + 1):
        mats: list[dict[str, Any]] = []
        for sid in range(4):
            name, mtype, color = palette[(bid + sid) % len(palette)]
            mat: dict[str, Any] = {
                "vendor": "Vorschau",
                "name": f"{name}",
                "type": mtype,
                "color": color,
                "state": 0,
                "selected": 0,
            }
            if bid == 1 and sid == 0:
                mat["selected"] = 1
            if bid == 2 and sid == 3:
                mat["state"] = 2
            mats.append(mat)
        boxes.append(
            {
                "type": 0,
                "id": bid,
                "humidity": 14 + bid * 2,
                "temp": 28.0 + bid,
                "materials": mats,
            }
        )
    return {
        "enable": 1,
        SIM_MARKER: True,
        "materialBoxs": boxes,
    }


def merge_cfs_preview_state(
    state: dict[str, Any],
    *,
    preview_boxes: int | None,
) -> dict[str, Any]:
    """Echtes Drucker-State + simulierte CFS-Boxen, oder unverändert."""
    if not preview_boxes or preview_boxes < 2:
        return state
    out = dict(state)
    out["cfsConnect"] = 1
    out["boxsInfo"] = build_simulated_boxs_info(preview_boxes)
    return out


def is_cfs_preview_state(state: dict[str, Any]) -> bool:
    bi = state.get("boxsInfo")
    return isinstance(bi, dict) and bool(bi.get(SIM_MARKER))
