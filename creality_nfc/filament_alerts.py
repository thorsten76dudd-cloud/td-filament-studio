"""Warnungen bei niedrigem Filament-Rest."""

from __future__ import annotations

from creality_nfc.spool_inventory import Spool, SpoolInventory
from creality_nfc.spool_usage import is_low_filament


def find_low_filament_spools(
    inventory: SpoolInventory,
    threshold_g: int,
    *,
    planned_use_g: int | None = None,
) -> list[tuple[Spool, str]]:
    """Spulen unter Schwelle; optional zusätzlich wenn geplanter Job Rest unterschreitet."""
    out: list[tuple[Spool, str]] = []
    thr = max(0, int(threshold_g))
    for sp in inventory.all():
        rem = sp.remaining_g
        if rem is None:
            continue
        if is_low_filament(sp, thr):
            out.append((sp, f"Rest {rem} g unter {thr} g"))
            continue
        if planned_use_g and planned_use_g > 0:
            after = rem - planned_use_g
            if after < thr:
                out.append(
                    (
                        sp,
                        f"Nach geplantem Job ca. {max(0, after)} g (unter {thr} g)",
                    )
                )
    return out
