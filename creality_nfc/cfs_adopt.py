"""CFS-Slot-Daten aus Drucker-Telemetrie für RFID-Tab übernehmen."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from creality_nfc.color_util import creality_color_to_hex

SLOT_LABELS = ("1A", "1B", "1C", "1D")


@dataclass
class CfsMeta:
    humidity: int | None = None
    box_temp: float | None = None
    external: CfsSlotInfo | None = None
    active_index: int | None = None
    loaded_index: int | None = None  # state==2 — Filament im Extruder
    feeding_index: int | None = None  # selected==1 — Zufuhr / aktiv gewählt


@dataclass
class CfsSlotInfo:
    index: int
    label: str
    vendor: str
    name: str
    material_type: str
    color_raw: str
    color_hex: str
    percent: int | None
    rfid_id: str
    empty: bool
    box_id: int = 1

    @property
    def display(self) -> str:
        if self.empty:
            return "—"
        parts = [p for p in (self.vendor, self.name) if p]
        label = " ".join(parts) if parts else self.material_type or "Material"
        pct = f" ({self.percent}%)" if self.percent is not None else ""
        return f"{label}{pct}"


def _color_hex_for_tag(color: str | int | None) -> str:
    h = creality_color_to_hex(color)
    if not h:
        return "FFFFFF"
    return h.lstrip("#").upper()


def _coerce_dict(val: Any) -> dict[str, Any] | None:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        text = val.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _find_boxs_info(state: dict[str, Any]) -> dict[str, Any] | None:
    for key in (
        "boxsInfo",
        "boxsinfo",
        "BoxsInfo",
        "retBoxsInfo",
        "ret_boxs_info",
        "cfsInfo",
        "cfs_info",
    ):
        if key in state:
            bi = _coerce_dict(state[key])
            if bi is not None:
                return bi
    for key, val in state.items():
        if isinstance(key, str) and "box" in key.lower() and "info" in key.lower():
            bi = _coerce_dict(val)
            if bi is not None:
                return bi
    return None


def _material_boxes(bi: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("materialBoxs", "materialBoxes", "material_box", "boxes", "boxList", "box_list"):
        raw = bi.get(key)
        if isinstance(raw, list):
            return [b for b in raw if isinstance(b, dict)]
        if isinstance(raw, dict):
            return [b for b in raw.values() if isinstance(b, dict)]
    raw = state.get("materialBoxs") or state.get("materialBoxes")
    if isinstance(raw, list):
        return [b for b in raw if isinstance(b, dict)]
    return []


def _slot_id_from_material(mat: dict[str, Any], fallback: int) -> int | None:
    for key in (
        "slot",
        "slotIndex",
        "slot_id",
        "slotId",
        "materialIndex",
        "material_index",
        "pos",
        "position",
        "cfsSlot",
    ):
        v = mat.get(key)
        if v is None:
            continue
        try:
            i = int(v)
            if 0 <= i <= 3:
                return i
        except (TypeError, ValueError):
            continue
    raw_id = mat.get("id")
    if raw_id is not None:
        try:
            i = int(raw_id)
            if 0 <= i <= 3:
                return i
        except (TypeError, ValueError):
            pass
    if 0 <= fallback <= 3:
        return fallback
    return None


def _rfid_from_mat(mat: dict[str, Any]) -> str:
    for key in (
        "rfid",
        "materialId",
        "material_id",
        "filament_id",
        "filamentId",
        "id_str",
    ):
        v = mat.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    raw_id = mat.get("id")
    if raw_id is not None:
        try:
            n = int(raw_id)
            if n > 3:
                return str(raw_id).strip()
        except (TypeError, ValueError):
            s = str(raw_id).strip()
            if s and not s.isdigit():
                return s
    return ""


def _fill_slot(slots: list[CfsSlotInfo], mat: dict[str, Any], sid: int) -> None:
    vendor = (
        mat.get("vendor")
        or mat.get("brand")
        or mat.get("manufacturer")
        or mat.get("materialBrand")
        or ""
    )
    vendor = str(vendor).strip()
    mtype = (
        mat.get("type")
        or mat.get("meterialType")
        or mat.get("materialType")
        or mat.get("material_type")
        or ""
    )
    mtype = str(mtype).strip()
    name = (
        mat.get("name")
        or mat.get("filamentName")
        or mat.get("materialName")
        or mat.get("material_name")
        or ""
    )
    name = str(name).strip()
    if not name and mtype and not str(mtype).isdigit():
        name = mtype
    color_raw = mat.get("color") or mat.get("colour") or mat.get("rgb") or ""
    rfid = _rfid_from_mat(mat)
    pct = mat.get("percent") or mat.get("remain") or mat.get("remaining") or mat.get("left")
    try:
        pct_i = int(float(pct)) if pct is not None else None
    except (TypeError, ValueError):
        pct_i = None
    state_val = mat.get("state")
    try:
        state_i = int(state_val) if state_val is not None else None
    except (TypeError, ValueError):
        state_i = None
    empty = (not vendor and not name and not mtype) or name in ("?", "—", "-", "null", "None")
    if state_i == 0:
        empty = True
    box_id = int(slots[sid].box_id) if sid < len(slots) else 1
    slots[sid] = CfsSlotInfo(
        index=sid,
        label=SLOT_LABELS[sid],
        vendor=vendor,
        name=name,
        material_type=mtype,
        color_raw=str(color_raw).strip(),
        color_hex=_color_hex_for_tag(color_raw),
        percent=pct_i,
        rfid_id=rfid,
        empty=empty,
        box_id=box_id,
    )


def _boxes_for_slots(boxes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wie ha_creality_ws: CFS-Box (type 0) bevorzugen, externes Filament (type 1) überspringen."""
    if not boxes:
        return []
    has_cfs = any(b.get("type") == 0 for b in boxes)
    out: list[dict[str, Any]] = []
    for box in boxes:
        box_type = box.get("type")
        if has_cfs and box_type == 1:
            continue
        out.append(box)
    return out or boxes


def _apply_materials(slots: list[CfsSlotInfo], materials: list) -> None:
    for idx, mat in enumerate(materials):
        if not isinstance(mat, dict):
            continue
        sid = _slot_id_from_material(mat, idx)
        if sid is None:
            continue
        _fill_slot(slots, mat, sid)


def parse_cfs_slots(state: dict[str, Any]) -> list[CfsSlotInfo]:
    """Vier CFS-Slots (0–3 → 1A–1D) aus WebSocket boxsInfo (K2 / ha_creality_ws-Format)."""
    slots: list[CfsSlotInfo] = [
        CfsSlotInfo(
            index=i,
            label=SLOT_LABELS[i],
            vendor="",
            name="",
            material_type="",
            color_raw="",
            color_hex="FFFFFF",
            percent=None,
            rfid_id="",
            empty=True,
        )
        for i in range(4)
    ]

    bi = _find_boxs_info(state)
    if bi is None:
        return slots

    if isinstance(bi, list):
        for box_idx, item in enumerate(bi):
            if isinstance(item, dict):
                mats = item.get("materials") or item.get("filaments") or []
                if isinstance(mats, list) and mats:
                    _apply_materials(slots, mats)
                elif box_idx <= 3:
                    _fill_slot(slots, item, box_idx)
        return slots

    flat = bi.get("materials") or bi.get("filaments") or bi.get("list")
    if isinstance(flat, list):
        _apply_materials(slots, flat)

    boxes = _material_boxes(bi, state)
    cfs_boxes = [b for b in _boxes_for_slots(boxes) if b.get("type") == 0]
    if not cfs_boxes:
        cfs_boxes = _boxes_for_slots(boxes)
    # Nur erste CFS-Box in parse_cfs_slots (Multi-Box: parse_cfs_layout).
    target = cfs_boxes[0] if cfs_boxes else None
    if target is not None:
        try:
            bid = int(target.get("id", 1) or 1)
        except (TypeError, ValueError):
            bid = 1
        for s in slots:
            s.box_id = bid
        mats = target.get("materials") or target.get("filaments") or target.get("list") or []
        if isinstance(mats, dict):
            mats = list(mats.values())
        if isinstance(mats, list) and mats:
            _apply_materials(slots, mats)
            for s in slots:
                s.label = SLOT_LABELS[s.index]

    _apply_same_material(slots, bi)
    return slots


def _apply_same_material(slots: list[CfsSlotInfo], bi: dict[str, Any]) -> None:
    """Fallback: Creality same_material (RFID/Farbe/Slot) wenn materials leer sind."""
    sm = bi.get("same_material") or bi.get("color_same_material")
    if not isinstance(sm, list):
        return
    for entry in sm:
        if not isinstance(entry, list) or len(entry) < 3:
            continue
        color_raw = str(entry[1]).strip() if entry[1] is not None else ""
        mapping = entry[2]
        mtype = str(entry[3]).strip() if len(entry) > 3 and entry[3] else ""
        if not isinstance(mapping, list) or not mapping:
            continue
        ref = mapping[0]
        if not isinstance(ref, dict):
            continue
        try:
            sid = int(ref.get("materialId", ref.get("id", -1)))
        except (TypeError, ValueError):
            continue
        if sid < 0 or sid > 3:
            continue
        if not slots[sid].empty and slots[sid].name:
            continue
        rfid = str(entry[0]).strip() if entry[0] is not None else ""
        slots[sid] = CfsSlotInfo(
            index=sid,
            label=SLOT_LABELS[sid],
            vendor="Creality" if rfid else "",
            name=mtype or slots[sid].name or "Filament",
            material_type=mtype,
            color_raw=color_raw,
            color_hex=_color_hex_for_tag(color_raw),
            percent=slots[sid].percent,
            rfid_id=rfid,
            empty=False,
        )


def _empty_slot(label: str = "EXT") -> CfsSlotInfo:
    return CfsSlotInfo(
        index=-1,
        label=label,
        vendor="",
        name="",
        material_type="",
        color_raw="",
        color_hex="FFFFFF",
        percent=None,
        rfid_id="",
        empty=True,
    )


def parse_external_slot(state: dict[str, Any]) -> CfsSlotInfo:
    """Spule am externen Halter (materialBox type 1)."""
    bi = _find_boxs_info(state)
    if not isinstance(bi, dict):
        return _empty_slot()
    for box in _material_boxes(bi, state):
        if box.get("type") != 1:
            continue
        mats = box.get("materials") or []
        if isinstance(mats, list) and mats and isinstance(mats[0], dict):
            slots = parse_cfs_slots({"boxsInfo": {"materialBoxs": [box]}})
            if slots:
                s = slots[0]
                return CfsSlotInfo(
                    index=-1,
                    label="EXT",
                    vendor=s.vendor,
                    name=s.name,
                    material_type=s.material_type,
                    color_raw=s.color_raw,
                    color_hex=s.color_hex,
                    percent=s.percent,
                    rfid_id=s.rfid_id,
                    empty=s.empty,
                )
    return _empty_slot()


def parse_cfs_meta(state: dict[str, Any]) -> CfsMeta:
    """Feuchtigkeit, aktiver Slot, externer Halter."""
    slots = parse_cfs_slots(state)
    meta = CfsMeta(external=parse_external_slot(state))
    bi = _find_boxs_info(state)
    if not isinstance(bi, dict):
        return meta
    for box in _material_boxes(bi, state):
        if box.get("type") != 0:
            continue
        hum = box.get("humidity")
        try:
            meta.humidity = int(round(float(hum))) if hum is not None else None
        except (TypeError, ValueError):
            pass
        temp = box.get("temp")
        try:
            meta.box_temp = float(temp) if temp is not None else None
        except (TypeError, ValueError):
            pass
        mats = box.get("materials") or []
        if isinstance(mats, list):
            for idx, mat in enumerate(mats):
                if not isinstance(mat, dict):
                    continue
                sid = _slot_id_from_material(mat, idx)
                if sid is None or sid < 0 or sid >= len(slots):
                    continue
                if slots[sid].empty:
                    continue
                try:
                    if int(mat.get("selected", 0)) == 1:
                        meta.feeding_index = sid
                except (TypeError, ValueError):
                    pass
                try:
                    st = int(mat.get("state", 0))
                    if st == 2:
                        meta.loaded_index = sid
                    elif st == 1 and meta.feeding_index is None:
                        meta.feeding_index = sid
                except (TypeError, ValueError):
                    pass
    if meta.loaded_index is not None:
        meta.active_index = meta.loaded_index
    elif meta.feeding_index is not None:
        meta.active_index = meta.feeding_index
    return meta


def match_profile_id(
    profiles: list,
    *,
    vendor: str,
    name: str,
    rfid_id: str = "",
) -> str | None:
    """Passende filament_id aus lokaler DB finden."""
    from .materials import normalize_filament_id

    v = vendor.strip().lower()
    n = name.strip().lower()

    if rfid_id:
        want = normalize_filament_id(rfid_id)
        id_matches = [
            p
            for p in profiles
            if normalize_filament_id(str(getattr(p, "filament_id", ""))) == want
        ]
        if id_matches:
            if v and n:
                for p in id_matches:
                    pb = str(getattr(p, "brand", "")).strip().lower()
                    pn = str(getattr(p, "name", "")).strip().lower()
                    if pb == v and pn == n:
                        return str(getattr(p, "filament_id", ""))
            if n:
                for p in id_matches:
                    pn = str(getattr(p, "name", "")).strip().lower()
                    if pn == n:
                        return str(getattr(p, "filament_id", ""))
            if len(id_matches) == 1:
                return str(getattr(id_matches[0], "filament_id", ""))

    if not v and not n:
        return None
    for p in profiles:
        pb = str(getattr(p, "brand", "")).strip().lower()
        pn = str(getattr(p, "name", "")).strip().lower()
        if v and n and pb == v and pn == n:
            return str(getattr(p, "filament_id", ""))
    for p in profiles:
        pn = str(getattr(p, "name", "")).strip().lower()
        if n and pn == n:
            return str(getattr(p, "filament_id", ""))
    return None
