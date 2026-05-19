"""Optional GitHub release version check."""

from __future__ import annotations

import json
import re
import urllib.request

RELEASE_API = "https://api.github.com/repos/DnG-Crafts/K2-RFID/releases/latest"


def fetch_latest_release_tag() -> str | None:
    try:
        req = urllib.request.Request(
            RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "TD-Filament-Studio"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = str(data.get("tag_name", "")).strip()
        return tag or None
    except Exception:
        return None


def is_newer(remote: str, local: str) -> bool:
    def parts(v: str) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", v)[:3]] or [0]

    return parts(remote) > parts(local)
