"""Filament-Passport: Rest, Öffnung, Abgleich Tag ↔ Inventar ↔ CFS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from creality_nfc.cfs_adopt import CfsSlotInfo
from creality_nfc.cfs_layout import cfs_slot_label
from creality_nfc.i18n import t as _t
from creality_nfc.materials import normalize_filament_id

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import Spool


@dataclass
class PassportSyncResult:
    updated_fields: list[str]
    warnings: list[str]
    info: list[str]


def touch_passport_after_print(
    spool: Spool,
    *,
    filename: str,
    deducted_g: int | None,
    ts: str,
) -> None:
    spool.last_print_at = ts
    spool.last_print_filename = (filename or "").strip()
    if deducted_g is not None and deducted_g > 0:
        spool.last_print_deducted_g = int(deducted_g)


def sync_passport_from_cfs_slot(
    spool: Spool,
    slot: CfsSlotInfo,
    *,
    printer_name: str = "",
) -> PassportSyncResult:
    """RFID/Material vom Drucker in Passport-Felder übernehmen."""
    updated: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if not slot.empty:
        spool.cfs_box_id = getattr(slot, "box_id", 1) or 1
        spool.cfs_slot = slot.index
        updated.append(_t("passport.cfs_slot"))

    rfid = (slot.rfid_id or "").strip()
    if rfid:
        want = normalize_filament_id(rfid)
        if spool.filament_id and normalize_filament_id(spool.filament_id) != want:
            warnings.append(
                _t(
                    "passport.rfid_mismatch",
                    want=want,
                    fid=spool.filament_id,
                )
            )
        elif not spool.filament_id:
            spool.filament_id = want
            updated.append(_t("passport.filament_id"))

    if slot.percent is not None and spool.remaining_g is not None:
        info.append(_t("passport.printer_fill", percent=slot.percent))

    if printer_name.strip():
        spool.last_seen_printer = printer_name.strip()
        spool.last_seen_slot_label = cfs_slot_label(
            getattr(slot, "box_id", 1) or 1, slot.index
        )
        from creality_nfc.spool_inventory import _now

        spool.last_seen_at = _now()
        updated.append(_t("passport.last_seen"))

    return PassportSyncResult(updated_fields=updated, warnings=warnings, info=info)


def compare_passport_with_slot(spool: Spool, slot: CfsSlotInfo) -> list[str]:
    """Abweichungen Inventar vs. CFS (für Dialog)."""
    issues: list[str] = []
    if slot.empty:
        issues.append(_t("passport.slot_empty"))
        return issues

    rfid = (slot.rfid_id or "").strip()
    if rfid and spool.filament_id:
        if normalize_filament_id(rfid) != normalize_filament_id(spool.filament_id):
            issues.append(
                _t(
                    "passport.rfid_vs_spool",
                    rfid=rfid,
                    fid=spool.filament_id,
                )
            )

    key = spool.effective_cfs_key()
    if key:
        bid, idx = key
        s_bid = getattr(slot, "box_id", 1) or 1
        if bid != s_bid or idx != slot.index:
            issues.append(
                _t(
                    "passport.slot_mismatch",
                    assigned=cfs_slot_label(bid, idx),
                    reported=cfs_slot_label(s_bid, slot.index),
                )
            )

    if spool.remaining_g is not None and spool.remaining_g < 50:
        issues.append(_t("passport.low_remain", rem=spool.remaining_g))

    return issues
