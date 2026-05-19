"""Lokale Spulen-Verwaltung."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from creality_nfc.cfs_adopt import SLOT_LABELS

try:
    from ui.color_swatch import normalize_hex
except ImportError:
    def normalize_hex(color: str) -> str:  # pragma: no cover
        h = str(color or "").strip().lstrip("#").upper()
        h = "".join(c for c in h if c in "0123456789ABCDEF")
        if len(h) >= 6:
            return h[-6:]
        if len(h) == 3:
            return "".join(c * 2 for c in h)
        if h:
            return h.rjust(6, "0")
        return "FFFFFF"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def usage_entry(*, grams: int, note: str = "", remaining_after: int | None = None) -> dict:
    return {
        "ts": _now(),
        "grams": int(grams),
        "note": note,
        "remaining_after": remaining_after,
    }


@dataclass
class Spool:
    id: str
    label: str
    brand: str = ""
    material_name: str = ""
    filament_id: str = ""
    color_hex: str = "FFFFFF"
    weight: str = "1 KG"
    printer: str = "K2 Pro"
    serial: str = "000001"
    remaining_g: int | None = None
    tag_uid: str = ""
    extra_tag_uids: list[str] = field(default_factory=list)
    notes: str = ""
    cfs_slot: int | None = None
    usage_log: list[dict] = field(default_factory=list)
    updated: str = field(default_factory=_now)

    @staticmethod
    def normalize_uid(uid: str) -> str:
        return (uid or "").replace(" ", "").upper()

    def all_tag_uids(self) -> list[str]:
        out: list[str] = []
        for raw in (self.tag_uid, *self.extra_tag_uids):
            u = self.normalize_uid(raw)
            if u and u not in out:
                out.append(u)
        return out

    def has_tag_uid(self, uid: str) -> bool:
        return self.normalize_uid(uid) in self.all_tag_uids()

    def tag_uids_display(self, *, compact: bool = False) -> str:
        """Alle verknüpften Tag-UIDs für Tabelle / Formular."""
        uids = self.all_tag_uids()
        if not uids:
            return ""
        if len(uids) == 1:
            return uids[0]
        if compact:
            return f"{uids[0]} +{len(uids) - 1}"
        return " · ".join(uids)

    def tag_uids_lines(self) -> str:
        uids = self.all_tag_uids()
        if not uids:
            return "— (kein Tag verknüpft)"
        return "\n".join(f"Chip {i}: {u}" for i, u in enumerate(uids, 1))

    def register_tag_uid(self, uid: str) -> bool:
        """UID dieser Spule zuordnen. True wenn neu hinzugefügt."""
        u = self.normalize_uid(uid)
        if not u:
            return False
        if self.has_tag_uid(u):
            return False
        if not self.normalize_uid(self.tag_uid):
            self.tag_uid = u
            return True
        self.extra_tag_uids.append(u)
        return True

    def remove_tag_uid(self, uid: str) -> bool:
        """Eine Chip-UID von der Spule lösen (Spule bleibt erhalten)."""
        u = self.normalize_uid(uid)
        if not u or not self.has_tag_uid(u):
            return False
        if self.normalize_uid(self.tag_uid) == u:
            self.tag_uid = ""
            if self.extra_tag_uids:
                self.tag_uid = self.normalize_uid(self.extra_tag_uids.pop(0))
            return True
        self.extra_tag_uids = [
            x for x in self.extra_tag_uids if self.normalize_uid(x) != u
        ]
        return True

    def clear_tag_uids(self) -> None:
        self.tag_uid = ""
        self.extra_tag_uids = []

    def display_name(self) -> str:
        parts = [self.label or self.material_name or "Spule"]
        if self.remaining_g is not None:
            parts.append(f"({self.remaining_g}g)")
        if self.cfs_slot is not None and 0 <= self.cfs_slot <= 3:
            parts.append(f"CFS {SLOT_LABELS[self.cfs_slot]}")
        if self.all_tag_uids():
            n = len(self.all_tag_uids())
            parts.append("RFID" if n == 1 else f"RFID×{n}")
        return " ".join(parts)

    def cfs_slot_label(self) -> str:
        if self.cfs_slot is None or not (0 <= self.cfs_slot <= 3):
            return ""
        return SLOT_LABELS[self.cfs_slot]


class SpoolInventory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.spools: list[Spool] = []
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            self.spools = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            known = {f.name for f in Spool.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            rows: list[Spool] = []
            for row in raw.get("spools", []):
                filtered = {k: v for k, v in row.items() if k in known}
                if "usage_log" not in filtered or not isinstance(filtered.get("usage_log"), list):
                    filtered["usage_log"] = []
                extra = filtered.get("extra_tag_uids")
                if not isinstance(extra, list):
                    filtered["extra_tag_uids"] = []
                else:
                    filtered["extra_tag_uids"] = [
                        Spool.normalize_uid(str(x)) for x in extra if str(x).strip()
                    ]
                if filtered.get("color_hex"):
                    filtered["color_hex"] = normalize_hex(str(filtered["color_hex"]))
                rows.append(Spool(**filtered))
            self.spools = rows
        except Exception:
            self.spools = []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": 2, "spools": [asdict(s) for s in self.spools]}
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, spool: Spool) -> Spool:
        self._clear_slot_conflict(spool)
        self.spools.append(spool)
        self.save()
        return spool

    def update(self, spool: Spool) -> None:
        self._clear_slot_conflict(spool)
        for i, s in enumerate(self.spools):
            if s.id == spool.id:
                spool.updated = _now()
                self.spools[i] = spool
                self.save()
                return
        self.add(spool)

    def _clear_slot_conflict(self, spool: Spool) -> None:
        if spool.cfs_slot is None:
            return
        for other in self.spools:
            if other.id != spool.id and other.cfs_slot == spool.cfs_slot:
                other.cfs_slot = None

    def delete(self, spool_id: str) -> None:
        self.spools = [s for s in self.spools if s.id != spool_id]
        self.save()

    def get(self, spool_id: str) -> Spool | None:
        for s in self.spools:
            if s.id == spool_id:
                return s
        return None

    def find_by_uid(self, uid: str) -> Spool | None:
        uid = Spool.normalize_uid(uid)
        if not uid:
            return None
        for s in self.spools:
            if s.has_tag_uid(uid):
                return s
        return None

    def find_by_cfs_slot(self, slot_index: int) -> Spool | None:
        for s in self.spools:
            if s.cfs_slot == slot_index:
                return s
        return None

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]

    def sorted_spools(self) -> list[Spool]:
        return sorted(self.spools, key=lambda s: s.label.lower())
