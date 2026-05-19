"""G-Code-Dateien vom K2 (WebSocket-Antworten) parsen."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote, unquote

from creality_nfc.printer_camera import normalize_host

GCODE_DIR = "/usr/data/printer_data/gcodes"


def entry_remote_path(entry: dict[str, Any]) -> str:
    """Vollständiger Drucker-Pfad zu einer G-Code-Datei (Liste / WS)."""
    path = str(entry.get("path") or "").strip().replace("\\", "/")
    if path:
        if path.startswith("printprt:"):
            path = path[len("printprt:") :]
        if path.startswith("deleteprt:"):
            path = path[len("deleteprt:") :]
        return path
    name = str(entry.get("name") or "").strip()
    if not name:
        raise ValueError("Kein Dateiname.")
    return f"{GCODE_DIR}/{name.lstrip('/')}"


def _decode_name(name: str) -> str:
    if not name:
        return ""
    try:
        return unquote(name)
    except Exception:
        return name


def _parse_mtime(value: Any) -> float | None:
    """Unix-Zeit in Sekunden (Creality: create_time, oft als name:size:timestamp)."""
    if value is None or value == "":
        return None
    try:
        t = float(value)
    except (TypeError, ValueError):
        return None
    if t > 1e12:
        t /= 1000.0
    if t < 1e6:
        return None
    return t


def _mtime_from_item(item: dict[str, Any]) -> float | None:
    for key in (
        "create_time",
        "file_create_time",
        "mtime",
        "modify_time",
        "modified",
        "upload_time",
        "time",
        "timestamp",
    ):
        t = _parse_mtime(item.get(key))
        if t is not None:
            return t
    return None


def format_gcode_mtime(ts: float | None) -> str:
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")
    except (OSError, ValueError, OverflowError):
        return ""


def _append_file(
    files: list[dict[str, Any]],
    name: str,
    path: str,
    size: Any = None,
    *,
    raw: str = "",
    thumbnail: str = "",
    mtime: float | None = None,
) -> None:
    name = _decode_name(name.strip())
    path = path.strip()
    if not name:
        return
    if not path:
        path = f"{GCODE_DIR}/{name}"
    for existing in files:
        if existing.get("path") == path or existing.get("name") == name:
            if mtime is not None:
                prev = existing.get("mtime")
                if prev is None or mtime > prev:
                    existing["mtime"] = mtime
            if size is not None and existing.get("size") is None:
                existing["size"] = size
            if thumbnail and not existing.get("thumbnail"):
                existing["thumbnail"] = thumbnail
            if raw and not existing.get("raw"):
                existing["raw"] = raw
            return
    entry: dict[str, Any] = {
        "name": name,
        "path": path,
        "size": size,
        "raw": raw,
        "thumbnail": thumbnail,
    }
    if mtime is not None:
        entry["mtime"] = mtime
    files.append(entry)


def _thumb_from_raw(raw: str) -> str:
    for marker in ("humbnail/", "thumbnail/"):
        if marker in raw:
            return raw.split(marker, 1)[1].split(":")[0].split(";")[0].strip()
    return ""


def _parse_file_info_string(file_info: str, files: list[dict[str, Any]]) -> None:
    for entry in file_info.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) < 2:
            continue
        mtime: float | None = None
        # Creality Print (Gerät): name:size:create_time
        if not parts[0].startswith("/") and len(parts) >= 3:
            name = parts[0]
            size = parts[1]
            mtime = _parse_mtime(parts[2])
            path = f"{GCODE_DIR}/{name}"
        elif parts[0].startswith("/"):
            path = parts[0]
            if len(parts) > 1 and "/" not in parts[1]:
                name = parts[1]
                size = parts[2] if len(parts) > 2 else None
                if len(parts) > 3:
                    mtime = _parse_mtime(parts[3])
            else:
                name = parts[-1] if parts[-1].endswith(".gcode") else parts[1]
                size = parts[2] if len(parts) > 2 else None
                if len(parts) > 3:
                    mtime = _parse_mtime(parts[3])
        else:
            name = parts[1] if len(parts) > 1 else parts[0]
            size = parts[2] if len(parts) > 2 else None
            path = f"{GCODE_DIR}/{name}"
            if len(parts) > 3:
                mtime = _parse_mtime(parts[3])
        thumb = _thumb_from_raw(entry)
        _append_file(files, name, path, size, raw=entry, thumbnail=thumb, mtime=mtime)


def _parse_info2_item(item: dict[str, Any], files: list[dict[str, Any]]) -> None:
    if not isinstance(item, dict):
        return
    if item.get("custom_types") == 3:
        for sub in item.get("file") or []:
            if isinstance(sub, dict):
                _parse_info2_item(sub, files)
        return
    name = item.get("name") or ""
    path = item.get("path") or ""
    size = item.get("file_size", item.get("size"))
    thumb = item.get("thumbnail") or item.get("thumb") or item.get("img") or ""
    mtime = _mtime_from_item(item)
    _append_file(files, str(name), str(path), size, thumbnail=str(thumb), mtime=mtime)
    for existing in files:
        if existing.get("path") == str(path).strip() or existing.get("name") == str(name).strip():
            for meta_key, val in item.items():
                if val in (None, ""):
                    continue
                kl = str(meta_key).lower()
                if meta_key in (
                    "materialColors",
                    "material",
                    "filamentWeight",
                    "materialUsed",
                    "materialIds",
                    "matchId",
                    "filamentId",
                ) or "filament" in kl or kl in ("materialused", "materialweight"):
                    existing[meta_key] = val
            break


def _deep_scan_gcode(node: Any, files: list[dict[str, Any]], depth: int = 0) -> None:
    if depth > 10:
        return
    if isinstance(node, dict):
        for key, val in node.items():
            kl = str(key).lower()
            if kl in ("fileinfo", "file_info") and isinstance(val, str) and val.strip():
                _parse_file_info_string(val, files)
            elif kl.startswith("retgcode") and isinstance(val, (dict, list)):
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            _parse_info2_item(item, files)
                elif isinstance(val, dict):
                    fi = val.get("fileInfo")
                    if isinstance(fi, str) and fi.strip():
                        _parse_file_info_string(fi, files)
            elif isinstance(val, (dict, list)):
                _deep_scan_gcode(val, files, depth + 1)
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, dict):
                _parse_info2_item(item, files)
            elif isinstance(item, str) and ".gcode" in item.lower():
                _append_file(files, item.split("/")[-1], item, mtime=None)


def parse_gcode_files(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Aus WS-Telemetrie eine flache Dateiliste erzeugen."""
    files: list[dict[str, Any]] = []

    info2 = state.get("retGcodeFileInfo2")
    if isinstance(info2, list):
        for item in info2:
            if isinstance(item, dict):
                _parse_info2_item(item, files)

    info = state.get("retGcodeFileInfo")
    if isinstance(info, dict):
        fi = info.get("fileInfo")
        if isinstance(fi, str) and fi.strip():
            _parse_file_info_string(fi, files)

    info3 = state.get("retGcodeFileInfo3")
    if isinstance(info3, dict):
        fi = info3.get("fileInfo")
        if isinstance(fi, str) and fi.strip():
            _parse_file_info_string(fi, files)
    elif isinstance(info3, list):
        for block in info3:
            if isinstance(block, dict):
                fi = block.get("fileInfo")
                if isinstance(fi, str) and fi.strip():
                    _parse_file_info_string(fi, files)

    if not files:
        _deep_scan_gcode(state, files)

    if not files:
        fname = (state.get("printFileName") or state.get("print_file_name") or "").strip()
        if fname and ".gcode" in fname.lower():
            name = fname.replace("\\", "/").split("/")[-1]
            path = fname if fname.startswith("/") else f"{GCODE_DIR}/{name}"
            _append_file(files, name, path, mtime=None)

    # Neueste zuerst (wie Creality Print); ohne Datum alphabetisch unten
    files.sort(
        key=lambda f: (-(f.get("mtime") or 0.0), f.get("name", "").lower()),
    )
    return files


def thumbnail_urls_for_file(host: str, entry: dict[str, Any]) -> list[str]:
    """Mögliche Thumbnail-URLs (Creality: /downloads/humbnail/…)."""
    host = normalize_host(host)
    urls: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        url = url.strip()
        if url and url not in seen:
            seen.add(url)
            urls.append(url)

    thumb = (entry.get("thumbnail") or "").strip()
    if thumb:
        if thumb.startswith("http"):
            add(thumb)
        elif thumb.startswith("/"):
            add(f"http://{host}:80{thumb}")
        else:
            add(f"http://{host}:80/downloads/humbnail/{quote(thumb, safe='')}")

    raw = entry.get("raw") or ""
    part = _thumb_from_raw(raw)
    if part:
        add(f"http://{host}:80/downloads/humbnail/{quote(part, safe='')}")

    name = entry.get("name") or ""
    if name:
        add(f"http://{host}:80/downloads/humbnail/{quote(name, safe='')}")
        if name.lower().endswith(".gcode"):
            base = name[:-6]
            add(f"http://{host}:80/downloads/humbnail/{quote(base, safe='')}.png")
            add(f"http://{host}:80/downloads/thumbnail/{quote(name, safe='')}")

    return urls
