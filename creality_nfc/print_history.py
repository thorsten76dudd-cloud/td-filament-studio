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
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else raw.get("jobs", [])
            self._entries = []
            for item in items:
                if isinstance(item, dict):
                    self._entries.append(
                        PrintJobRecord(
                            id=str(item.get("id") or PrintJobRecord.new_id()),
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

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(e) for e in self._entries[: self.max_entries]]
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, record: PrintJobRecord) -> None:
        self._entries.insert(0, record)
        self._entries = self._entries[: self.max_entries]
        self.save()

    def list_entries(self) -> list[PrintJobRecord]:
        return list(self._entries)

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
