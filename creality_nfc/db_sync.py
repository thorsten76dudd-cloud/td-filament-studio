"""Material-Datenbank von Creality Cloud laden (wie CFS-RFID Original)."""

from __future__ import annotations

import io
import json
import time
import uuid
import zipfile
from urllib.request import Request, urlopen

PRINTER_LIST_URL = (
    "https://api.crealitycloud.com/api/cxy/v2/slice/profile/official/printerList"
)
MATERIAL_LIST_URL = (
    "https://api.crealitycloud.com/api/cxy/v2/slice/profile/official/materialList"
)

# Gleiche Header wie DnG-Crafts / Creality Print (POST, nicht GET).
API_USER_AGENT = (
    "BBL-Slicer/v01.09.03.50 (dark) Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 "
    "Edg/107.0.1418.52"
)


def _creality_headers() -> dict[str, str]:
    return {
        "User-Agent": API_USER_AGENT,
        "Content-Type": "application/json",
        "__CXY_BRAND_": "creality",
        "__CXY_UID_": "",
        "__CXY_OS_LANG_": "0",
        "__CXY_DUID_": str(uuid.uuid4()),
        "__CXY_APP_VER_": "1.0",
        "__CXY_APP_CH_": "CP_Beta",
        "__CXY_OS_VER_": API_USER_AGENT,
        "__CXY_TIMEZONE_": "28800",
        "__CXY_APP_ID_": "creality_model",
        "__CXY_REQUESTID_": str(uuid.uuid4()),
        "__CXY_PLATFORM_": "11",
    }


def _fetch_creality_api(url: str) -> dict:
    body: dict = {"engineVersion": "3.0.0"}
    if "materialList" in url:
        body["pageSize"] = 500
    payload = json.dumps(body).encode("utf-8")
    req = Request(url, data=payload, method="POST", headers=_creality_headers())
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        raise RuntimeError(
            f"Creality Cloud Fehler ({url}): {exc}\n"
            "Alternativ: „DB Datei…“ und material_database aus CFS-RFID.zip wählen."
        ) from exc


def _fetch_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": API_USER_AGENT})
    with urlopen(req, timeout=180) as resp:
        return resp.read()


def find_printer_zip_url(printer_label: str, nozzle: str = "0.4") -> tuple[str, str]:
    """Sucht zipUrl und offiziellen Druckernamen in der Creality-API."""
    root = _fetch_creality_api(PRINTER_LIST_URL)
    needle = printer_label.lower().replace(" ", "")

    for printer in root.get("result", {}).get("printerList", []):
        name = str(printer.get("name", ""))
        norm = name.lower().replace(" ", "")
        nozzles = [str(n) for n in printer.get("nozzleDiameter", [])]
        if nozzle not in nozzles:
            continue
        if needle in norm or norm in needle or _printer_match(needle, norm):
            url = printer.get("zipUrl") or ""
            if url:
                return url, name

    raise RuntimeError(
        f"Kein Creality-Profil für „{printer_label}“ (Düse {nozzle} mm) gefunden."
    )


def _printer_match(needle: str, norm: str) -> bool:
    aliases = {
        "k2pro": ("k2pro", "k2"),
        "k2plus": ("k2plus", "k2"),
        "k2max": ("k2max", "k2"),
        "k2se": ("k2se", "k2"),
        "k2": ("k2",),
        "k1max": ("k1max", "k1"),
        "k1c": ("k1c", "k1"),
        "k1se": ("k1se", "k1"),
        "k1": ("k1",),
        "crealityhi": ("hi", "crealityhi"),
        "hi": ("hi",),
    }
    for key, parts in aliases.items():
        if key in needle or needle in key:
            return any(p in norm for p in parts)
    return False


def process_materials(
    material_list_json: str, filament_json_list: list[str], zip_version: str | None
) -> dict:
    list_root = json.loads(material_list_json)
    all_base = list_root.get("result", {}).get("list", [])
    by_name = {b.get("name"): b for b in all_base if b.get("name")}

    final_list = []
    for raw in filament_json_list:
        source = json.loads(raw)
        target_name = (source.get("metadata") or {}).get("name")
        raw_base = by_name.get(target_name)
        if not raw_base:
            continue
        clean_base = {
            k: v
            for k, v in raw_base.items()
            if k not in ("createTime", "status", "userInfo")
        }
        final_list.append(
            {
                "engineVersion": source.get("engine_version"),
                "printerIntName": "F008",
                "nozzleDiameter": ["0.4"],
                "kvParam": source.get("engine_data") or {},
                "base": clean_base,
            }
        )

    version = zip_version or str(int(time.time()))
    return {
        "code": 0,
        "msg": "ok",
        "reqId": "0",
        "result": {"list": final_list, "count": len(final_list), "version": version},
    }


def download_material_database(printer_label: str, nozzle: str = "0.4") -> dict:
    zip_url, _official_name = find_printer_zip_url(printer_label, nozzle)
    material_list = _fetch_creality_api(MATERIAL_LIST_URL)
    material_list_str = json.dumps(material_list)
    zip_bytes = _fetch_bytes(zip_url)

    filament_files: list[str] = []
    zip_version: str | None = None

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".json"):
                continue
            content = zf.read(name).decode("utf-8", errors="replace")
            if "/" not in name and "\\" not in name:
                try:
                    zip_version = json.loads(content).get("version")
                except json.JSONDecodeError:
                    pass
            elif name.lower().startswith("materials/"):
                filament_files.append(content)

    if not filament_files:
        raise RuntimeError("ZIP enthält keine materials/*.json Dateien.")

    return process_materials(material_list_str, filament_files, zip_version)
