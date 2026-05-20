"""Drucker erreichbar, Browser öffnen, G-Code-Vorschaubilder laden."""

from __future__ import annotations

import os
import socket
import ssl
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

_moonraker_urls_cache: dict[str, tuple[float, list[str]]] = {}
_MOONRAKER_CACHE_SEC = 600.0


def normalize_host(host: str) -> str:
    h = host.strip()
    for prefix in ("https://", "http://"):
        if h.lower().startswith(prefix):
            h = h[len(prefix) :]
    h = h.split("/")[0].strip()
    if ":" in h and not h.startswith("["):
        h = h.rsplit(":", 1)[0]
    return h


def printer_reachable(host: str, port: int = 22, timeout: float = 2.0) -> bool:
    host = normalize_host(host)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _open_url_windows(url: str) -> bool:
    import ctypes

    try:
        rc = int(ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1))
        if rc > 32:
            return True
    except OSError:
        pass
    try:
        os.startfile(url)  # noqa: S606
        return True
    except OSError:
        pass
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", url],
            close_fds=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except OSError:
        return False


def open_url(url: str) -> bool:
    url = url.strip()
    if not url:
        return False
    if sys.platform == "win32":
        return _open_url_windows(url)
    try:
        import webbrowser

        if webbrowser.open(url, new=2):
            return True
    except Exception:
        pass
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", url], close_fds=True)
        return True
    except OSError:
        return False


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_image_url(url: str, timeout: float = 5.0) -> tuple[bytes, str] | None:
    """Beliebiges Bild per HTTP(S) laden (G-Code-Thumbnails)."""
    headers = {"User-Agent": "TD-Filament-Studio/1.0"}
    ctx = _ssl_context()
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if len(data) < 200:
                return None
            if "image" in ctype or data[:2] == b"\xff\xd8" or data[:8] == b"\x89PNG\r\n\x1a":
                return data, url
    except (URLError, OSError, TimeoutError, ValueError):
        pass
    return None


def _moonraker_snapshot_urls(host: str) -> list[str]:
    now = time.monotonic()
    cached = _moonraker_urls_cache.get(host)
    if cached and now - cached[0] < _MOONRAKER_CACHE_SEC:
        return list(cached[1])
    extra: list[str] = []
    try:
        from creality_nfc.printer_klipper import moonraker_webcams

        for cam in moonraker_webcams(host, timeout=0.8):
            for key in ("snapshot_url", "stream_url", "service"):
                u = (cam.get(key) or "").strip()
                if u.startswith("http"):
                    extra.append(u.replace("?action=stream", "?action=snapshot"))
    except Exception:
        pass
    _moonraker_urls_cache[host] = (now, extra)
    return extra


def camera_snapshot_urls(host: str, *, probe_moonraker: bool = True) -> list[str]:
    """Bekannte Snapshot-URLs (K2 / Klipper / Moonraker)."""
    host = normalize_host(host)
    urls = [
        f"http://{host}:8000/webcam/?action=snapshot",
        f"http://{host}:8000/?action=snapshot",
        f"http://{host}:4408/webcam/?action=snapshot",
        f"http://{host}:4408/?action=snapshot",
        f"http://{host}/webcam/?action=snapshot",
        f"http://{host}:8080/webcam/?action=snapshot",
        f"http://{host}:8080/?action=snapshot",
    ]
    if probe_moonraker:
        urls.extend(_moonraker_snapshot_urls(host))
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def fetch_camera_snapshot(
    host: str,
    timeout: float = 2.5,
    *,
    preferred_url: str = "",
) -> tuple[bytes, str] | None:
    """Schnellster erreichbarer Snapshot (Cache-URL zuerst, sonst parallel)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    host = normalize_host(host)
    pref = (preferred_url or "").strip()
    if pref:
        hit = fetch_image_url(pref, timeout=min(1.2, timeout))
        if hit:
            return hit

    urls = camera_snapshot_urls(host, probe_moonraker=not bool(pref))
    if pref and pref in urls:
        urls = [pref] + [u for u in urls if u != pref]
    if not urls:
        return None
    per_url = max(0.6, timeout / max(1, min(5, len(urls))))
    found: tuple[bytes, str] | None = None
    with ThreadPoolExecutor(max_workers=min(8, len(urls))) as pool:
        futures = {pool.submit(fetch_image_url, u, per_url): u for u in urls[:10]}
        for fut in as_completed(futures, timeout=timeout + 0.35):
            if found:
                break
            try:
                hit = fut.result()
                if hit:
                    found = hit
            except Exception:
                pass
    if found:
        return found
    return fetch_image_urls(urls, timeout=timeout)


def _image_pixel_count(data: bytes) -> int:
    try:
        import io

        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            w, h = im.size
            return max(1, w * h)
    except Exception:
        return len(data)


def fetch_image_urls(urls: list[str], timeout: float = 4.0) -> tuple[bytes, str] | None:
    """Lädt Thumbnails parallel und wählt die größte Auflösung (schärfere Vorschau)."""
    if not urls:
        return None
    if len(urls) == 1:
        return fetch_image_url(urls[0], timeout=timeout)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    per_url = max(0.55, timeout / len(urls))
    best: tuple[bytes, str] | None = None
    best_px = 0
    with ThreadPoolExecutor(max_workers=min(6, len(urls))) as pool:
        futures = {pool.submit(fetch_image_url, u, per_url): u for u in urls}
        for fut in as_completed(futures, timeout=timeout + 0.25):
            try:
                hit = fut.result()
            except Exception:
                continue
            if not hit:
                continue
            px = _image_pixel_count(hit[0])
            if px > best_px:
                best_px = px
                best = hit
    if best:
        return best
    for url in urls:
        shot = fetch_image_url(url, timeout=per_url)
        if shot:
            return shot
    return None
