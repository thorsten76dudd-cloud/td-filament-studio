"""GitHub-Releases prüfen (TD Filament Studio)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from creality_nfc.config import GITHUB_RELEASES_REPO

RELEASE_API = f"https://api.github.com/repos/{GITHUB_RELEASES_REPO}/releases/latest"
RELEASES_LIST_API = f"https://api.github.com/repos/{GITHUB_RELEASES_REPO}/releases?per_page=8"
_USER_AGENT = "TD-Filament-Studio"


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    version: str
    name: str
    html_url: str
    download_url: str | None = None
    download_label: str | None = None
    setup_download_count: int | None = None


def format_setup_downloads(count: int | None, *, label: str | None = None) -> str:
    """Anzeige-Text für Setup-Downloads vom GitHub-Release."""
    name = label or "Setup.exe"
    if count is None:
        return f"{name}: keine Zahl von GitHub"
    if count == 0:
        return (
            f"{name}: 0 Downloads (GitHub — kann Minuten verzögert sein, "
            "auch nach eigenem Download)"
        )
    return f"{name}: {count} Download{'s' if count != 1 else ''}"


def release_stats_lines(info: ReleaseInfo) -> list[str]:
    """Zusatzzeilen für Update-Dialog / Einstellungen."""
    lines = [format_setup_downloads(info.setup_download_count, label=info.download_label)]
    lines.append(f"Release: {info.tag}")
    return lines


def _github_get_json(url: str, *, timeout: int = 12) -> object | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_latest_release() -> ReleaseInfo | None:
    """Neuestes GitHub-Release (Tag, Seite, optional direkter EXE/Setup-Download)."""
    data = _github_get_json(RELEASE_API)
    if isinstance(data, dict):
        parsed = _parse_release_payload(data)
        if parsed:
            return parsed
    items = _github_get_json(RELEASES_LIST_API)
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("draft") or item.get("prerelease"):
            continue
        parsed = _parse_release_payload(item)
        if parsed:
            return parsed
    return None


def fetch_latest_release_tag() -> str | None:
    """Nur Tag-Name (Abwärtskompatibilität)."""
    info = fetch_latest_release()
    return info.tag if info else None


def normalize_release_version(tag_or_version: str) -> str:
    """z. B. v1.5.58-stable → 1.5.58 (für Vergleich mit APP_VERSION)."""
    v = str(tag_or_version or "").strip().lstrip("vV")
    return re.sub(r"-.*$", "", v).strip() or v


def _parse_release_payload(data: dict) -> ReleaseInfo | None:
    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        return None
    version = normalize_release_version(tag)
    html_url = str(data.get("html_url", "")).strip()
    if not html_url and GITHUB_RELEASES_REPO:
        html_url = f"https://github.com/{GITHUB_RELEASES_REPO}/releases/latest"
    name = str(data.get("name", "") or tag).strip()
    download_url, download_label, setup_download_count = _pick_release_asset(data.get("assets") or [])
    return ReleaseInfo(
        tag=tag,
        version=version,
        name=name,
        html_url=html_url,
        download_url=download_url,
        download_label=download_label,
        setup_download_count=setup_download_count,
    )


def _pick_release_asset(assets: list) -> tuple[str | None, str | None, int | None]:
    """Bevorzugt Setup-EXE, dann portable EXE; inkl. download_count von GitHub."""
    candidates: list[tuple[int, str, str, int]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        url = str(asset.get("browser_download_url", "")).strip()
        label = str(asset.get("name", "")).strip()
        if not url or not label.lower().endswith(".exe"):
            continue
        low = label.lower()
        score = 0
        if "setup" in low or "installer" in low:
            score += 20
        if "td-filament" in low or "td filament" in low:
            score += 10
        if "filament" in low and "studio" in low:
            score += 5
        try:
            dl = int(asset.get("download_count", 0))
        except (TypeError, ValueError):
            dl = 0
        candidates.append((score, url, label, dl))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: (-x[0], x[2]))
    _, url, label, dl = candidates[0]
    return url, label, dl


def is_newer(remote: str, local: str) -> bool:
    def parts(v: str) -> list[int]:
        return [int(x) for x in re.findall(r"\d+", normalize_release_version(v))[:4]] or [0]

    return parts(remote) > parts(local)
