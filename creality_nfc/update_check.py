"""GitHub-Releases prüfen (TD Filament Studio)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from creality_nfc.config import GITHUB_RELEASES_REPO

RELEASE_API = f"https://api.github.com/repos/{GITHUB_RELEASES_REPO}/releases/latest"
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


def fetch_latest_release() -> ReleaseInfo | None:
    """Neuestes GitHub-Release (Tag, Seite, optional direkter EXE/Setup-Download)."""
    try:
        req = urllib.request.Request(
            RELEASE_API,
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        return None
    except Exception:
        return None
    return _parse_release_payload(data)


def fetch_latest_release_tag() -> str | None:
    """Nur Tag-Name (Abwärtskompatibilität)."""
    info = fetch_latest_release()
    return info.tag if info else None


def _parse_release_payload(data: dict) -> ReleaseInfo | None:
    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
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
        return [int(x) for x in re.findall(r"\d+", v)[:4]] or [0]

    return parts(remote) > parts(local)
