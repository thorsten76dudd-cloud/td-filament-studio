"""Vergleich lokale vs. Drucker-Material-Datenbank."""

from __future__ import annotations

from .db_merge import _items_by_id


def _label(item: dict) -> str:
    base = item.get("base", {})
    fid = str(base.get("id", "")).strip()
    brand = str(base.get("brand", "")).strip()
    name = str(base.get("name", "")).strip()
    return f"{fid} — {brand} / {name}"


def compare_databases(local: dict | None, remote: dict | None) -> dict:
    """Ergebnis mit Listen und Zählern für die UI."""
    loc = _items_by_id(local or {})
    rem = _items_by_id(remote or {})
    loc_ids = set(loc)
    rem_ids = set(rem)

    only_local = sorted(loc_ids - rem_ids)
    only_remote = sorted(rem_ids - loc_ids)
    shared = sorted(loc_ids & rem_ids)

    return {
        "local_count": len(loc),
        "remote_count": len(rem),
        "shared_count": len(shared),
        "only_local": only_local,
        "only_remote": only_remote,
        "only_local_labels": [_label(loc[i]) for i in only_local[:80]],
        "only_remote_labels": [_label(rem[i]) for i in only_remote[:80]],
    }


def format_compare_report(result: dict) -> str:
    lines = [
        f"Lokal: {result['local_count']} Profile  |  Drucker: {result['remote_count']} Profile  |  "
        f"Gemeinsam: {result['shared_count']}",
        "",
    ]
    if result["only_local"]:
        lines.append(f"Nur lokal ({len(result['only_local'])}) — würden beim Upload ergänzt:")
        lines.extend(f"  • {x}" for x in result["only_local_labels"][:25])
        if len(result["only_local"]) > 25:
            lines.append(f"  … +{len(result['only_local']) - 25} weitere")
        lines.append("")
    if result["only_remote"]:
        lines.append(f"Nur auf dem Drucker ({len(result['only_remote'])}) — nicht in deiner lokalen DB:")
        lines.extend(f"  • {x}" for x in result["only_remote_labels"][:25])
        if len(result["only_remote"]) > 25:
            lines.append(f"  … +{len(result['only_remote']) - 25} weitere")
        lines.append("")
    if not result["only_local"] and not result["only_remote"] and result["shared_count"]:
        lines.append("Lokal und Drucker haben dieselben Filament-IDs.")
    elif not result["local_count"]:
        lines.append("Keine lokale DB geladen.")
    elif not result["remote_count"]:
        lines.append("Drucker-DB konnte nicht gelesen werden.")
    return "\n".join(lines).strip()
