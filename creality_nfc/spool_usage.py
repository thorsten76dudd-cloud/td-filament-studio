"""Restgewicht, Verbrauchshistorie, Warnungen."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import Spool

_WEIGHT_MAP = {
    "250 G": 250,
    "500 G": 500,
    "750 G": 750,
    "1 KG": 1000,
    "2.5 KG": 2500,
    "3 KG": 3000,
    "5 KG": 5000,
}


def weight_class_to_grams(weight: str) -> int:
    key = (weight or "1 KG").strip().upper()
    if key in _WEIGHT_MAP:
        return _WEIGHT_MAP[key]
    m = re.search(r"([\d.]+)\s*(G|KG)", key)
    if not m:
        return 1000
    val = float(m.group(1))
    return int(round(val * 1000 if m.group(2) == "KG" else val))


def is_low_filament(sp: Spool, threshold_g: int) -> bool:
    if sp.remaining_g is None:
        return False
    return sp.remaining_g <= max(0, threshold_g)


def record_usage(sp: Spool, grams: int, *, note: str = "") -> None:
    from creality_nfc.spool_inventory import usage_entry

    if grams <= 0:
        return
    if sp.remaining_g is None:
        sp.remaining_g = weight_class_to_grams(sp.weight)
    sp.remaining_g = max(0, sp.remaining_g - grams)
    sp.usage_log.append(
        usage_entry(grams=grams, note=note, remaining_after=sp.remaining_g)
    )


def deduct_grams(sp: Spool, grams: int, *, note: str = "Abzug") -> int:
    record_usage(sp, grams, note=note)
    return sp.remaining_g or 0
