"""Druck-Historie (Jobs mit Verbrauch, Datei, Slot)."""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PrintJobRecord:
    id: str
    ts: str
    filename: str = ""
    duration_sec: int | None = None
    progress_pct: int | None = None
    estimated_total_g: int | None = None
    deducted_g: int | None = None
    cfs_slot: int | None = None
    cfs_slot_label: str = ""
    spool_label: str = ""
    spool_id: str = ""
    note: str = ""

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]


class PrintHistoryStore:
    def __init__(self, path: Path, *, max_entries: int = 400) -> None:
        self.path = path
        self.max_entries = max_entries
        self._entries: list[PrintJobRecord] = []
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            self._entries = []
            return
        needs_save = False
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else raw.get("jobs", [])
            self._entries = []
            for item in items:
                if isinstance(item, dict):
                    raw_id = str(item.get("id") or "").strip()
                    if not raw_id:
                        needs_save = True
                    self._entries.append(
                        PrintJobRecord(
                            id=raw_id or PrintJobRecord.new_id(),
                            ts=str(item.get("ts") or _now()),
                            filename=str(item.get("filename") or ""),
                            duration_sec=_opt_int(item.get("duration_sec")),
                            progress_pct=_opt_int(item.get("progress_pct")),
                            estimated_total_g=_opt_int(item.get("estimated_total_g")),
                            deducted_g=_opt_int(item.get("deducted_g")),
                            cfs_slot=_opt_int(item.get("cfs_slot")),
                            cfs_slot_label=str(item.get("cfs_slot_label") or ""),
                            spool_label=str(item.get("spool_label") or ""),
                            spool_id=str(item.get("spool_id") or ""),
                            note=str(item.get("note") or ""),
                        )
                    )
        except Exception:
            self._entries = []
        for e in self._entries:
            if repair_history_entry(e):
                needs_save = True
        if needs_save and self._entries:
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self._entries[: self.max_entries]]
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, record: PrintJobRecord) -> None:
        """Neuester Eintrag oben; gleiche Datei kurz nacheinander wird aktualisiert."""
        if self._entries and (record.filename or "").strip():
            prev = self._entries[0]
            if (prev.filename or "").strip() == (record.filename or "").strip():
                if record.deducted_g is not None and record.deducted_g > 0:
                    prev.deducted_g = record.deducted_g
                if record.note:
                    prev_has_deduct = (prev.deducted_g or 0) > 0
                    new_is_no_deduct = "kein abzug" in record.note.lower()
                    if prev_has_deduct and new_is_no_deduct:
                        pass
                    elif "nachträg" in (prev.note or "").lower() and new_is_no_deduct:
                        pass
                    else:
                        prev.note = record.note
                if record.duration_sec is not None:
                    prev.duration_sec = record.duration_sec
                if record.spool_label:
                    prev.spool_label = record.spool_label
                if record.spool_id:
                    prev.spool_id = record.spool_id
                self.save()
                return
        self._entries.insert(0, record)
        self._entries = self._entries[: self.max_entries]
        self.save()

    def list_entries(self) -> list[PrintJobRecord]:
        return list(self._entries)

    @staticmethod
    def tree_iid(record: PrintJobRecord) -> str:
        rid = (record.id or "").strip()
        if rid:
            return rid
        short = (record.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        return f"job-{record.ts}-{short}"

    def get(self, entry_id: str) -> PrintJobRecord | None:
        iid = (entry_id or "").strip()
        if not iid:
            return None
        for e in self._entries:
            if e.id == iid:
                return e
        for e in self._entries:
            if self.tree_iid(e) == iid:
                return e
        return None

    def _match_record(
        self,
        record: PrintJobRecord,
        *,
        entry_id: str = "",
    ) -> PrintJobRecord | None:
        rid = (entry_id or record.id or "").strip()
        for e in self._entries:
            if e is record:
                return e
            if rid and e.id == rid:
                return e
        fn = (record.filename or "").strip()
        ts = (record.ts or "").strip()
        if fn and ts:
            for e in self._entries:
                if (e.filename or "").strip() == fn and (e.ts or "").strip() == ts:
                    return e
        return None

    def update_entry(self, entry_id: str, **fields: Any) -> bool:
        """Felder eines Eintrags per id aktualisieren."""
        for e in self._entries:
            if e.id != entry_id:
                continue
            for key, val in fields.items():
                if hasattr(e, key):
                    setattr(e, key, val)
            self.save()
            return True
        return False

    def update_record(self, record: PrintJobRecord, **fields: Any) -> bool:
        """Felder aktualisieren (id, Objekt-Referenz oder Datei+Zeitstempel)."""
        target = self._match_record(record)
        if target is None:
            return False
        for key, val in fields.items():
            if hasattr(target, key):
                setattr(target, key, val)
        if target is not record:
            for key, val in fields.items():
                if hasattr(record, key):
                    setattr(record, key, val)
        self.save()
        return True

    def export_csv(self, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "ts",
            "filename",
            "duration_sec",
            "progress_pct",
            "estimated_total_g",
            "deducted_g",
            "cfs_slot_label",
            "spool_label",
            "note",
        ]
        with dest.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for e in self._entries:
                row = {k: getattr(e, k, "") for k in fields}
                w.writerow(row)


def _opt_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def normalize_history_note(record: PrintJobRecord) -> str:
    """Anzeige-Notiz — korrigiert widersprüchliche alte Einträge."""
    note = (record.note or "").strip()
    dg = record.deducted_g
    if dg is not None and dg > 0:
        if "nachträg" in note.lower():
            return note or "Nachträglich abgezogen"
        if not note or "kein abzug" in note.lower():
            return "Abzug bestätigt"
    if not note:
        return "—"
    return note


def repair_history_entry(record: PrintJobRecord) -> bool:
    """Speichert korrigierte Notiz, wenn Abzug und Notiz widersprechen."""
    note = (record.note or "").strip()
    dg = record.deducted_g
    if dg is None or dg <= 0:
        return False
    if note and "kein abzug" not in note.lower():
        return False
    record.note = (
        "Nachträglich abgezogen"
        if "nachträg" in note.lower()
        else "Abzug bestätigt"
    )
    return True
