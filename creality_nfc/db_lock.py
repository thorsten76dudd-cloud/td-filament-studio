"""Schutz eigener Profile vor Cloud-/Drucker-Überschreibung."""

from __future__ import annotations

LOCK_KEY = "lockFromSync"


def item_merge_key(item: dict) -> str:
    base = item.get("base", {})
    fid = str(base.get("id", "")).strip()
    brand = str(base.get("brand", "")).strip()
    name = str(base.get("name", "")).strip()
    return f"{fid}\t{brand}\t{name}"


def is_item_locked(item: dict) -> bool:
    if item.get(LOCK_KEY):
        return True
    return bool(item.get("base", {}).get(LOCK_KEY))


def set_item_locked(item: dict, locked: bool) -> None:
    item[LOCK_KEY] = bool(locked)
    item.setdefault("base", {})[LOCK_KEY] = bool(locked)
