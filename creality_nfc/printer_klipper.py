"""Klipper/Moonraker am K2 — Erreichbarkeit prüfen, Web-UI öffnen."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from creality_nfc.printer_camera import normalize_host

MOONRAKER_PORT = 7125
UI_PORTS = (80, 4408, 7125, 8000)


@dataclass
class KlipperProbe:
    moonraker: bool = False
    moonraker_version: str = ""
    klipper_version: str = ""
    webcams: list[dict[str, Any]] = field(default_factory=list)
    ui_links: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        parts: list[str] = []
        if self.moonraker:
            v = self.moonraker_version or "?"
            k = f", Klipper {self.klipper_version}" if self.klipper_version else ""
            parts.append(f"Moonraker {v}{k}")
        else:
            parts.append("Moonraker nicht erreichbar (Port 7125)")
        if self.webcams:
            parts.append(f"{len(self.webcams)} Webcam(s)")
        if self.ui_links:
            parts.append("Web-UI: " + ", ".join(l for l, _ in self.ui_links))
        return " · ".join(parts)


def _http_get_json(url: str, timeout: float = 2.5) -> dict[str, Any] | None:
    try:
        req = Request(url, headers={"User-Agent": "TD-Filament-Studio/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            data = json.loads(raw)
            if isinstance(data, dict) and "result" in data:
                return data["result"] if isinstance(data["result"], dict) else data
            return data if isinstance(data, dict) else None
    except (URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _http_head_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        req = Request(url, method="GET", headers={"User-Agent": "TD-Filament-Studio/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except (URLError, OSError, TimeoutError, ValueError):
        return False


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _moonraker_base(host: str) -> str:
    return f"http://{normalize_host(host)}:{MOONRAKER_PORT}"


def moonraker_webcams(host: str, timeout: float = 2.5) -> list[dict[str, Any]]:
    data = _http_get_json(f"{_moonraker_base(host)}/server/webcams/list", timeout=timeout)
    if not data:
        return []
    cams = data.get("webcams")
    if isinstance(cams, list):
        return [c for c in cams if isinstance(c, dict)]
    return []


def resolve_moonraker_url(host: str, path: str) -> str:
    host = normalize_host(host)
    p = (path or "").strip()
    if p.startswith("http://") or p.startswith("https://"):
        return p
    base = _moonraker_base(host)
    if not p:
        return base
    return f"{base}{p}" if p.startswith("/") else f"{base}/{p}"


def probe_klipper(host: str, timeout: float = 2.5) -> KlipperProbe:
    host = normalize_host(host)
    probe = KlipperProbe(webcams=[], ui_links=[])

    info = _http_get_json(f"{_moonraker_base(host)}/server/info", timeout=timeout)
    if info:
        probe.moonraker = True
        probe.moonraker_version = str(info.get("moonraker_version", "") or "")
        probe.klipper_version = str(info.get("klipper_version", "") or "")
        probe.webcams = moonraker_webcams(host, timeout=timeout)

    for port, label in (
        (80, "Drucker-Web"),
        (4408, "Creality-Web"),
        (7125, "Moonraker"),
        (8000, "Creality-API"),
    ):
        if not _port_open(host, port, timeout=0.8):
            continue
        url = f"http://{host}" if port == 80 else f"http://{host}:{port}/"
        if _http_head_ok(url, timeout=timeout):
            probe.ui_links.append((label, url))

    return probe


def best_ui_url(host: str) -> str | None:
    probe = probe_klipper(host)
    for prefer in ("Drucker-Web", "Creality-Web", "Moonraker", "Creality-API"):
        for label, url in probe.ui_links:
            if label == prefer:
                return url
    if probe.ui_links:
        return probe.ui_links[0][1]
    if probe.moonraker:
        return _moonraker_base(host)
    return None


def creality_web_ui_url(host: str, timeout: float = 2.0) -> str | None:
    """
    Creality-Oberfläche im Browser (K2: oft Port 4408 oder 8000, nicht Port 80 /).
    """
    host = normalize_host(host)
    probe = probe_klipper(host, timeout=timeout)
    for prefer in ("Creality-Web", "Creality-API", "Drucker-Web"):
        for label, url in probe.ui_links:
            if label == prefer:
                return url
    for port in (4408, 8000, 80):
        if not _port_open(host, port, timeout=0.8):
            continue
        url = f"http://{host}" if port == 80 else f"http://{host}:{port}/"
        if _http_head_ok(url, timeout=timeout):
            return url
    if _port_open(host, 4408, timeout=0.8):
        return f"http://{host}:4408/"
    if _port_open(host, 8000, timeout=0.8):
        return f"http://{host}:8000/"
    return None
