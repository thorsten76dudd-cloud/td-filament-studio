"""Merge material_database.json sources (cloud + printer + local)."""

from __future__ import annotations

import copy

from .db_lock import is_item_locked, item_merge_key


def _items_by_key(data: dict) -> dict[str, dict]:
    """Eindeutiger Schlüssel: ID + Marke + Name."""
    out: dict[str, dict] = {}
    for item in data.get("result", {}).get("list", []):
        key = item_merge_key(item)
        if key.strip("\t"):
            out[key] = item
    return out


# Alias für ältere Imports
_items_by_id = _items_by_key


def merge_databases(
    base: dict,
    incoming: dict,
    *,
    prefer: str = "local",
) -> dict:
    """Merge incoming profiles into base. prefer=local keeps existing on conflict."""
    merged = copy.deepcopy(base)
    base_items = _items_by_key(merged)
    incoming_items = _items_by_key(incoming)

    for key, item in incoming_items.items():
        if key not in base_items:
            base_items[key] = copy.deepcopy(item)
        elif prefer == "cloud":
            if is_item_locked(base_items[key]):
                continue
            base_items[key] = copy.deepcopy(item)

    lst = list(base_items.values())
    lst.sort(
        key=lambda x: (
            str(x.get("base", {}).get("brand", "")),
            str(x.get("base", {}).get("name", "")),
        )
    )
    merged.setdefault("result", {})["list"] = lst
    merged["result"]["count"] = len(lst)
    if incoming.get("code") is not None:
        merged["code"] = incoming.get("code", 0)
    if incoming.get("msg"):
        merged["msg"] = incoming["msg"]
    return merged


def merge_stats(base: dict, incoming: dict) -> tuple[int, int, int, int]:
    """Return (added, updated, total, skipped_locked)."""
    base_items = _items_by_key(base)
    incoming_items = _items_by_key(incoming)
    base_keys = set(base_items)
    inc_keys = set(incoming_items)
    added = len(inc_keys - base_keys)
    updated = 0
    skipped = 0
    for key in inc_keys & base_keys:
        if is_item_locked(base_items[key]):
            skipped += 1
        else:
            updated += 1
    return added, updated, len(base_keys | inc_keys), skipped
