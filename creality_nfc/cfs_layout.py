"""CFS-Layout: bis zu 4 Boxen × 4 Slots (K2), kompatibel mit einer Box."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from creality_nfc.cfs_adopt import (
    CfsSlotInfo,
    SLOT_LABELS,
    _apply_materials,
    _apply_same_material,
    _boxes_for_slots,
    _fill_slot,
    _find_boxs_info,
    _material_boxes,
    parse_cfs_slots,
    parse_external_slot,
)

SLOT_LETTERS = ("A", "B", "C", "D")
_MAX_BOX_ID = 4


def cfs_slot_label(box_id: int, slot_index: int) -> str:
    """Anzeige wie am Drucker: 1A … 4D."""
    if slot_index < 0 or slot_index > 3:
        return "—"
    bid = max(1, min(_MAX_BOX_ID, int(box_id or 1)))
    return f"{bid}{SLOT_LETTERS[slot_index]}"


def parse_slot_key(text: str) -> tuple[int, int] | None:
    """
    1A, 2B, CFS-S3 (Box 1 Slot 3), Slot 1B → (box_id, slot_index 0–3).
    """
    t = (text or "").strip().upper()
    if not t:
        return None
    m = re.search(r"^([1-4])\s*([ABCD])\b", t)
    if m:
        return int(m.group(1)), SLOT_LETTERS.index(m.group(2))
    m = re.search(r"CFS[-_\s]*S?\s*([1-4])\b", t, re.I)
    if m:
        return 1, int(m.group(1)) - 1
    for i, lab in enumerate(SLOT_LABELS):
        if re.search(rf"\b{re.escape(lab)}\b", t):
            return 1, i
    return None


def _empty_slots_for_box(box_id: int) -> list[CfsSlotInfo]:
    return [
        CfsSlotInfo(
            index=i,
            label=cfs_slot_label(box_id, i),
            vendor="",
            name="",
            material_type="",
            color_raw="",
            color_hex="FFFFFF",
            percent=None,
            rfid_id="",
            empty=True,
            box_id=box_id,
        )
        for i in range(4)
    ]


@dataclass
class CfsBoxLayout:
    box_id: int
    slots: list[CfsSlotInfo] = field(default_factory=list)
    humidity: int | None = None
    box_temp: float | None = None


@dataclass
class CfsLayout:
    """Alle CFS-Einheiten am Drucker (typisch 1, max. 4)."""

    boxes: list[CfsBoxLayout] = field(default_factory=list)
    external: CfsSlotInfo | None = None

    def all_slots(self) -> list[CfsSlotInfo]:
        out: list[CfsSlotInfo] = []
        for box in self.boxes:
            out.extend(box.slots)
        return out

    def primary_slots(self) -> list[CfsSlotInfo]:
        """Vier Slots der ersten/primären CFS-Box (UI-Kompatibilität)."""
        if not self.boxes:
            return parse_cfs_slots({})
        for box in self.boxes:
            if box.box_id == 1:
                return list(box.slots)
        return list(self.boxes[0].slots)

    def slot_count(self) -> int:
        return sum(1 for s in self.all_slots() if not s.empty)

    def box_count(self) -> int:
        return len(self.boxes)


def parse_cfs_layout(state: dict[str, Any]) -> CfsLayout:
    """Alle CFS-Boxen (type 0) getrennt; keine Überschreibung zwischen Boxen."""
    bi = _find_boxs_info(state)
    external = parse_external_slot(state)
    if bi is None:
        return CfsLayout(boxes=[], external=external)

    boxes_raw = _boxes_for_slots(_material_boxes(bi, state))
    cfs_boxes = [b for b in boxes_raw if b.get("type") == 0]
    if not cfs_boxes:
        return CfsLayout(
            boxes=[CfsBoxLayout(box_id=1, slots=parse_cfs_slots(state))],
            external=external,
        )

    layouts: list[CfsBoxLayout] = []
    for box in sorted(cfs_boxes, key=lambda b: int(b.get("id", 99) or 99)):
        try:
            box_id = int(box.get("id", 1) or 1)
        except (TypeError, ValueError):
            box_id = 1
        if box_id < 1 or box_id > _MAX_BOX_ID:
            continue
        slots = _empty_slots_for_box(box_id)
        mats = box.get("materials") or box.get("filaments") or []
        if isinstance(mats, dict):
            mats = list(mats.values())
        if isinstance(mats, list) and mats:
            _apply_materials(slots, mats)
            for s in slots:
                s.box_id = box_id
                s.label = cfs_slot_label(box_id, s.index)
        hum = box.get("humidity")
        try:
            humidity = int(round(float(hum))) if hum is not None else None
        except (TypeError, ValueError):
            humidity = None
        temp = box.get("temp")
        try:
            box_temp = float(temp) if temp is not None else None
        except (TypeError, ValueError):
            box_temp = None
        layouts.append(
            CfsBoxLayout(box_id=box_id, slots=slots, humidity=humidity, box_temp=box_temp)
        )

    if isinstance(bi, dict):
        flat = bi.get("materials") or bi.get("filaments")
        if layouts and isinstance(flat, list):
            _apply_same_material(layouts[0].slots, bi)

    if not layouts:
        layouts = [CfsBoxLayout(box_id=1, slots=parse_cfs_slots(state))]

    return CfsLayout(boxes=layouts, external=external)


def layout_from_slot_list(slots: list[CfsSlotInfo]) -> CfsLayout:
    """Aus flacher Slot-Liste (legacy) ein Layout mit einer Box bauen."""
    if not slots:
        return CfsLayout(boxes=[CfsBoxLayout(box_id=1, slots=parse_cfs_slots({}))])
    by_box: dict[int, list[CfsSlotInfo]] = {}
    for s in slots:
        bid = getattr(s, "box_id", 1) or 1
        by_box.setdefault(bid, []).extend([s])
    boxes = [
        CfsBoxLayout(box_id=bid, slots=sorted(sl, key=lambda x: x.index))
        for bid, sl in sorted(by_box.items())
    ]
    return CfsLayout(boxes=boxes or [CfsBoxLayout(box_id=1, slots=slots[:4])])
