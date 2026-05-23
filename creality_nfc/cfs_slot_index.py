"""Hilfen für Multi-CFS: flache Slot-Liste (Box 1–4 × Slot A–D)."""

from __future__ import annotations

from creality_nfc.cfs_adopt import CfsSlotInfo
from creality_nfc.cfs_layout import cfs_slot_label


def flat_slot_index(
    slots: list[CfsSlotInfo],
    box_id: int,
    slot_index: int,
) -> int | None:
    """Index in einer all_slots()-Liste für (box_id, material_id 0–3)."""
    bid = int(box_id or 1)
    sid = int(slot_index)
    for i, s in enumerate(slots):
        if (getattr(s, "box_id", 1) or 1) == bid and s.index == sid:
            return i
    return None


def slot_ref_at_flat(slots: list[CfsSlotInfo], flat_index: int) -> tuple[int, int] | None:
    """(box_id, material_id) für flachen Index."""
    if not (0 <= flat_index < len(slots)):
        return None
    s = slots[flat_index]
    return (getattr(s, "box_id", 1) or 1, s.index)


def usage_slot_label(slots: list[CfsSlotInfo], flat_index: int) -> str:
    if 0 <= flat_index < len(slots):
        s = slots[flat_index]
        return s.label or cfs_slot_label(getattr(s, "box_id", 1) or 1, s.index)
    return f"Slot {flat_index}"
