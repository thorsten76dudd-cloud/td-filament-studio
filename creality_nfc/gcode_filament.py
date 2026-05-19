"""Filament-Farbe und -typ aus G-Code-Metadaten (retGcodeFileInfo2 am K2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from creality_nfc.cfs_adopt import CfsSlotInfo, SLOT_LABELS
from creality_nfc.color_util import creality_color_to_hex

GCODE_DIR = "/usr/data/printer_data/gcodes"

_FILENAME_MATERIAL_HINTS = (
    "PETG",
    "PLA",
    "ABS",
    "ASA",
    "TPU",
    "PA",
    "PC",
    "PVA",
    "HIPS",
    "NYLON",
)


@dataclass
class GcodeFilamentSpec:
    """Ein Extruder / eine Farbe im G-Code (Index 0–3 → 1A–1D)."""

    extruder_index: int
    color_hex: str | None
    material_type: str | None
    weight_g: float | None


@dataclass
class GcodeSlotUsage:
    """Verbrauch laut G-Code, einem CFS-Slot zugeordnet."""

    slot_index: int
    slot_label: str
    spec: GcodeFilamentSpec
    grams: int
    source: str


_MAX_PLAUSIBLE_GRAMS = 500.0
_MIN_PLAUSIBLE_GRAMS = 4.0


def _split_fields(raw: str, sep: str) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in str(raw).split(sep)]


def _parse_float(val: str) -> float | None:
    try:
        return float(val.replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def plausible_filament_grams(val: float | None) -> float | None:
    """Gramm aus filamentWeight; materialUsed > 500 ist oft Länge in mm, nicht g."""
    if val is None or val <= 0.01:
        return None
    if val < _MIN_PLAUSIBLE_GRAMS or val > _MAX_PLAUSIBLE_GRAMS:
        return None
    return val


def parse_filament_specs(info: dict[str, Any]) -> list[GcodeFilamentSpec]:
    """Aus retGcodeFileInfo2-Eintrag (materialColors, material, filamentWeight)."""
    colors = _split_fields(str(info.get("materialColors") or ""), ";")
    materials = _split_fields(str(info.get("material") or ""), ";")
    weights = _split_fields(str(info.get("filamentWeight") or ""), ",")
    used = _split_fields(str(info.get("materialUsed") or ""), ",")

    n = max(len(colors), len(materials), len(weights), len(used), 4)
    specs: list[GcodeFilamentSpec] = []
    for i in range(n):
        color_raw = colors[i] if i < len(colors) else ""
        mat = materials[i] if i < len(materials) else ""
        w: float | None = None
        if i < len(weights):
            w = plausible_filament_grams(_parse_float(weights[i]))
        if w is None and i < len(used):
            w = plausible_filament_grams(_parse_float(used[i]))
        color_hex = creality_color_to_hex(color_raw) if color_raw else None
        mtype = mat.strip() if mat and mat.strip() else None
        specs.append(
            GcodeFilamentSpec(
                extruder_index=i,
                color_hex=color_hex,
                material_type=mtype,
                weight_g=w,
            )
        )
    return specs


def active_filament_specs(specs: list[GcodeFilamentSpec]) -> list[GcodeFilamentSpec]:
    """Extruder, die im Job wirklich genutzt werden."""
    by_weight = [s for s in specs if s.weight_g is not None and s.weight_g > 0.01]
    if by_weight:
        return by_weight
    by_color = [s for s in specs if s.color_hex]
    if by_color:
        return by_color
    by_type = [s for s in specs if s.material_type]
    return by_type[:1] if by_type else specs[:1]


def _color_distance(a: str, b: str) -> float:
    ah = creality_color_to_hex(a) or ""
    bh = creality_color_to_hex(b) or ""
    if not ah or not bh:
        return 1e9
    ar = int(ah[1:3], 16)
    ag = int(ah[3:5], 16)
    ab = int(ah[5:7], 16)
    br = int(bh[1:3], 16)
    bg = int(bh[3:5], 16)
    bb = int(bh[5:7], 16)
    return ((ar - br) ** 2 + (ag - bg) ** 2 + (ab - bb) ** 2) ** 0.5


def material_hint_from_gcode_path(gcode_path: str) -> str | None:
    """z. B. Körper9.stl_PETG_19m54s.gcode → PETG."""
    name = gcode_path.replace("\\", "/").rsplit("/", 1)[-1].upper()
    for hint in _FILENAME_MATERIAL_HINTS:
        if hint in name:
            return hint
    return None


def _slot_matches_material(slot: CfsSlotInfo, material_type: str) -> bool:
    want = material_type.upper()
    mt = (slot.material_type or "").upper()
    label = f"{slot.vendor} {slot.name}".upper()
    if want == "PLA":
        return "PLA" in mt or "PLA" in label
    return want in mt or want in label


def _candidate_slot_indices(
    slots: list[CfsSlotInfo], *, material_type: str | None = None
) -> list[int]:
    out = [i for i, slot in enumerate(slots) if not slot.empty]
    if not material_type:
        return out
    filtered = [i for i in out if _slot_matches_material(slots[i], material_type)]
    return filtered if filtered else out


def match_slot_by_color(
    slots: list[CfsSlotInfo],
    color_hex: str | None,
    *,
    material_type: str | None = None,
    only_indices: list[int] | None = None,
) -> int | None:
    """CFS-Slot mit ähnlichster Farbe (wie Creality Print Farbabgleich)."""
    if not color_hex:
        return None
    indices = only_indices if only_indices is not None else list(range(len(slots)))
    best_i: int | None = None
    best_d = 1e9
    for i in indices:
        if i < 0 or i >= len(slots) or slots[i].empty:
            continue
        slot = slots[i]
        if material_type and not _slot_matches_material(slot, material_type):
            continue
        slot_hex = creality_color_to_hex(slot.color_raw)
        if not slot_hex:
            continue
        d = _color_distance(color_hex, slot_hex)
        if d < best_d:
            best_d = d
            best_i = i
    if best_i is not None and best_d <= 120:
        return best_i
    return None


def resolve_slot_for_spec(
    slots: list[CfsSlotInfo],
    spec: GcodeFilamentSpec,
    *,
    gcode_path: str = "",
    loaded_slot_index: int | None = None,
    single_filament: bool = False,
) -> int | None:
    """Material (Dateiname/G-Code) + Farbe → CFS-Slot; kein blinder Extruder-Index."""
    hint = material_hint_from_gcode_path(gcode_path)
    material = (spec.material_type or "").strip().upper()
    color_hex = spec.color_hex
    if single_filament and hint:
        material = hint
        color_hex = None
    elif hint:
        if not material:
            material = hint
        elif material != hint and not color_hex:
            material = hint
    candidates = _candidate_slot_indices(slots, material_type=material or None)

    if color_hex:
        idx = match_slot_by_color(
            slots,
            color_hex,
            material_type=material or None,
            only_indices=candidates,
        )
        if idx is not None:
            return idx

    if len(candidates) == 1:
        return candidates[0]

    if loaded_slot_index is not None and loaded_slot_index in candidates:
        return loaded_slot_index

    if material and len(candidates) > 1:
        for i in candidates:
            if _slot_matches_material(slots[i], material):
                return i

    return None


def primary_gcode_slot_mapping(
    state: dict[str, Any],
    gcode_path: str,
    slots: list[CfsSlotInfo],
    *,
    file_entry: dict[str, Any] | None = None,
    prefer_slot_index: int | None = None,
) -> tuple[int, GcodeFilamentSpec] | None:
    """Erste G-Code-Farbe → CFS-Slot (für Abzug nach Druck)."""
    mappings = resolve_slots_from_gcode(
        state,
        gcode_path,
        slots,
        file_entry=file_entry,
        loaded_slot_index=prefer_slot_index,
    )
    if mappings:
        return mappings[0]
    return None


def gcode_info_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Metadaten aus gecachter Dateiliste (nach reqGcodeFileInfo2)."""
    if entry.get("materialColors") or entry.get("filamentWeight") or entry.get("material"):
        return entry
    return None


_HEADER_COLOR_RE = (
    re.compile(
        r"default_filament_colou?r\s*[=:]\s*[\"']?(#[0-9A-Fa-f]{6}|0x[0-9A-Fa-f]{6}|[0-9A-Fa-f]{6})",
        re.I,
    ),
    re.compile(
        r"filament_colou?r(?:\s*\[\s*(\d+)\s*\])?\s*[=:]\s*[\"']?(#[0-9A-Fa-f]{6}|0x[0-9A-Fa-f]{6}|[0-9A-Fa-f]{6})",
        re.I,
    ),
    re.compile(
        r";?\s*filament_colou?r_type\s*[=:]\s*([A-Za-z0-9 _+-]+)",
        re.I,
    ),
    re.compile(r";?\s*material\s*[=:]\s*([A-Za-z0-9 _+-]+)", re.I),
)


def _resolve_local_gcode_path(gcode_path: str) -> Path | None:
    raw = gcode_path.strip().replace("\\", "/")
    if raw.startswith("printprt:"):
        raw = raw[len("printprt:") :]
    candidates: list[Path] = []
    if raw.startswith("/"):
        candidates.append(Path(raw))
    candidates.append(Path(raw.rsplit("/", 1)[-1]))
    for path in candidates:
        if path.is_file():
            return path
    return None


def parse_filament_colors_from_gcode_file(
    gcode_path: str | Path, *, max_bytes: int = 120_000
) -> tuple[list[str], list[str]]:
    """
    Farben/Material aus Slicer-Kommentaren am Dateianfang (Creality/Orca/Prusa).
    Rückgabe: (farben als #RRGGBB, materialtypen).
    """
    path = Path(gcode_path) if not isinstance(gcode_path, Path) else gcode_path
    if not path.is_file():
        resolved = _resolve_local_gcode_path(str(gcode_path))
        if resolved is None:
            return [], []
        path = resolved
    try:
        raw = path.read_bytes()[:max_bytes].decode("utf-8", errors="ignore")
    except OSError:
        return [], []
    colors: list[str] = []
    materials: list[str] = []
    for line in raw.splitlines()[:400]:
        if not line.startswith(";"):
            if line.strip().startswith("G"):
                break
            continue
        for pat in _HEADER_COLOR_RE[:2]:
            m = pat.search(line)
            if m:
                hx = None
                for g in m.groups():
                    if not g:
                        continue
                    hx = creality_color_to_hex(g)
                    if hx:
                        break
                if hx:
                    colors.append(hx)
                break
        for pat in _HEADER_COLOR_RE[2:]:
            m_type = pat.search(line)
            if m_type:
                mt = m_type.group(1).strip()
                if mt:
                    materials.append(mt)
                break
    return colors, materials


def _raw_temp_to_celsius(raw: Any) -> int | None:
    """K2 retGcodeFileInfo2: 25500 → 255 °C, 7000 → 70 °C; auch °C direkt."""
    if raw is None or raw == "":
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    if v >= 500:
        v = v / 100.0
    c = int(round(v))
    return c if 20 <= c <= 400 else None


_HEADER_PRINT_TEMP_RE = (
    re.compile(r";?\s*first_layer_bed_temperature\s*[=:]\s*([\d.]+)", re.I),
    re.compile(r";?\s*bed_temperature\s*[=:]\s*([\d.]+)", re.I),
    re.compile(r";?\s*first_layer_temperature\s*[=:]\s*([\d.]+)", re.I),
    re.compile(r";?\s*nozzle_temperature\s*[=:]\s*([\d.]+)", re.I),
    re.compile(r"\bM140\s+S([\d.]+)", re.I),
    re.compile(r"\bM104\s+S([\d.]+)", re.I),
)


def parse_print_temps_from_gcode_file(
    gcode_path: str | Path, *, max_bytes: int = 120_000
) -> tuple[int | None, int | None]:
    """Düse/Bett aus Slicer-Kommentaren oder M104/M140 am Dateianfang."""
    path = Path(gcode_path) if not isinstance(gcode_path, Path) else gcode_path
    if not path.is_file():
        resolved = _resolve_local_gcode_path(str(gcode_path))
        if resolved is None:
            return None, None
        path = resolved
    try:
        raw = path.read_bytes()[:max_bytes].decode("utf-8", errors="ignore")
    except OSError:
        return None, None
    nozzle: int | None = None
    bed: int | None = None
    for line in raw.splitlines()[:500]:
        if not line.startswith(";") and line.strip().startswith("G"):
            break
        for i, pat in enumerate(_HEADER_PRINT_TEMP_RE):
            m = pat.search(line)
            if not m:
                continue
            c = _raw_temp_to_celsius(m.group(1))
            if c is None:
                continue
            if i <= 1:
                bed = c
            elif i <= 3:
                nozzle = c
            elif "M140" in pat.pattern:
                bed = c
            else:
                nozzle = c
            break
    return nozzle, bed


def parse_gcode_print_temps(info: dict[str, Any] | None) -> tuple[int | None, int | None]:
    """Drucktemperaturen aus retGcodeFileInfo2 / Dateiliste."""
    if not info:
        return None, None
    nozzle = _raw_temp_to_celsius(info.get("extruder_temp_from_file"))
    bed = _raw_temp_to_celsius(info.get("bed_temp_from_file"))
    if nozzle is None:
        nozzle = _raw_temp_to_celsius(info.get("nozzleTemp") or info.get("nozzle_temp"))
    if bed is None:
        bed = _raw_temp_to_celsius(info.get("bedTemp") or info.get("bed_temp"))
    return nozzle, bed


def build_preheat_params(
    info: dict[str, Any] | None, *, gcode_path: str | None = None
) -> list[dict[str, Any]]:
    """WebSocket-set Schritte zum Vorheizen vor CFS-Zufuhr / Druck."""
    nozzle, bed = parse_gcode_print_temps(info)
    if gcode_path and (nozzle is None or bed is None):
        fn, fb = parse_print_temps_from_gcode_file(gcode_path)
        if nozzle is None:
            nozzle = fn
        if bed is None:
            bed = fb
    steps: list[dict[str, Any]] = []
    if nozzle and nozzle > 0:
        steps.append({"nozzleTempControl": nozzle})
    if bed and bed > 0:
        steps.append({"bedTempControl": {"num": 0, "val": bed}})
    return steps


def merge_gcode_filament_info(
    state: dict[str, Any],
    gcode_path: str,
    file_entry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Drucker-Metadaten + Dateiliste + Slicer-Kommentare im G-Code zusammenführen."""
    merged: dict[str, Any] = {}
    if file_entry:
        for key in (
            "name",
            "path",
            "materialColors",
            "material",
            "filamentWeight",
            "materialUsed",
            "nozzleTemp",
            "bedTemp",
            "bed_temp_from_file",
            "extruder_temp_from_file",
            "enableCfs",
        ):
            val = file_entry.get(key)
            if val not in (None, ""):
                merged[key] = val
    found = find_gcode_file_info(state, gcode_path)
    if found:
        for key, val in found.items():
            if val not in (None, "") and key not in merged:
                merged[key] = val
    if gcode_path:
        fn, fb = parse_print_temps_from_gcode_file(gcode_path)
        if fn is not None and "nozzleTemp" not in merged and "extruder_temp_from_file" not in merged:
            merged.setdefault("extruder_temp_from_file", fn)
        if fb is not None and "bedTemp" not in merged and "bed_temp_from_file" not in merged:
            merged.setdefault("bed_temp_from_file", fb)
    paths: list[str] = []
    if merged.get("path"):
        paths.append(str(merged["path"]))
    paths.append(gcode_path)
    for p in paths:
        colors, materials = parse_filament_colors_from_gcode_file(p)
        if colors and not merged.get("materialColors"):
            merged["materialColors"] = ";".join(colors)
        if materials and not merged.get("material"):
            merged["material"] = ";".join(materials)
        if colors or materials:
            break
    hint = material_hint_from_gcode_path(gcode_path)
    if hint:
        specs = active_filament_specs(parse_filament_specs(merged))
        single = len(specs) <= 1
        if single:
            merged["material"] = hint
        file_colors: list[str] = []
        for p in paths:
            fc, _fm = parse_filament_colors_from_gcode_file(p)
            if fc:
                file_colors = fc
                break
        if file_colors and single:
            merged["materialColors"] = (
                file_colors[0] if len(file_colors) == 1 else ";".join(file_colors)
            )
    return merged


def find_gcode_file_info(state: dict[str, Any], gcode_path: str) -> dict[str, Any] | None:
    """retGcodeFileInfo2-Eintrag zu Pfad oder Dateiname."""
    path = gcode_path.strip().replace("\\", "/")
    name = path.rsplit("/", 1)[-1].lower()
    if path.startswith("printprt:"):
        path = path[len("printprt:") :]
    candidates: list[Any] = []
    for key in ("retGcodeFileInfo2", "retGcodeFileInfo3", "retGcodeFileInfo"):
        raw = state.get(key)
        if isinstance(raw, list):
            candidates.extend(raw)
        elif isinstance(raw, dict):
            candidates.append(raw)

    best: dict[str, Any] | None = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        iname = str(item.get("name") or "").lower()
        ipath = str(item.get("path") or "").replace("\\", "/").lower()
        if iname == name or ipath.endswith(name) or name in ipath:
            return item
        if path and (ipath == path.lower() or ipath.endswith(path.lower())):
            best = item
    return best


_HEADER_CFS_DISABLED_RE = (
    re.compile(r";?\s*enable_cfs\s*[=:]\s*0", re.I),
    re.compile(r";?\s*use_cfs\s*[=:]\s*0", re.I),
    re.compile(r";?\s*cfs_enable\s*[=:]\s*0", re.I),
    re.compile(r";?\s*print_source\s*[=:]\s*external", re.I),
    re.compile(r";?\s*filament_source\s*[=:]\s*external", re.I),
)

_CFS_FLAG_KEYS = (
    "enableCfs",
    "enable_cfs",
    "openCfs",
    "open_cfs",
    "cfsEnable",
    "cfs_enable",
    "useCfs",
    "use_cfs",
)


def gcode_uses_external_spool(
    info: dict[str, Any] | None,
    gcode_path: str | None = None,
    *,
    max_header_bytes: int = 64_000,
) -> bool:
    """
    True wenn der Job für den externen Spulenhalter gesliced wurde (nicht CFS).
    Sonst droht FR0121, wenn CFS-Filament noch im Extruder steckt.
    """
    if info:
        for key in _CFS_FLAG_KEYS:
            if key not in info:
                continue
            try:
                if int(info[key]) == 0:
                    return True
            except (TypeError, ValueError):
                continue
        box_raw = (
            info.get("materialBoxId")
            or info.get("materialBox")
            or info.get("boxId")
        )
        if box_raw is not None:
            try:
                if int(box_raw) <= 0:
                    return True
            except (TypeError, ValueError):
                pass
        ids_raw = str(
            info.get("materialIds") or info.get("matchId") or info.get("filamentId") or ""
        ).upper()
        if "EXT" in ids_raw and "T1" not in ids_raw:
            return True

    if not gcode_path:
        return False
    path = Path(gcode_path.replace("\\", "/"))
    if not path.is_file():
        for prefix in ("/mnt/UDISK/printer_data/gcodes/", "/usr/data/printer_data/gcodes/"):
            if gcode_path.replace("\\", "/").startswith(prefix):
                local = Path(gcode_path.split("/")[-1])
                if local.is_file():
                    path = local
                break
    if not path.is_file():
        return False
    try:
        raw = path.read_bytes()[:max_header_bytes].decode("utf-8", errors="ignore")
    except OSError:
        return False
    for pat in _HEADER_CFS_DISABLED_RE:
        if pat.search(raw):
            return True
    return False


_HEADER_FILAMENT_RE = (
    re.compile(r"filament used \[g\]\s*=\s*([\d.]+)", re.I),
    re.compile(r"total filament used \[g\]\s*=\s*([\d.]+)", re.I),
    re.compile(r"total filament weight \[g\]\s*=\s*([\d.]+)", re.I),
    re.compile(r"filament used:\s*([\d.]+)\s*g", re.I),
    re.compile(r"total filament\s*:\s*([\d.]+)\s*g", re.I),
    re.compile(r"; filament_weight\s*[=:]\s*([\d.]+)", re.I),
    re.compile(r"; total filament weight \[g\]\s*:\s*([\d.]+)", re.I),
    re.compile(r"; filament used \[mm\]\s*=\s*([\d.]+)", re.I),
    re.compile(r"; total filament used \[mm\]\s*=\s*([\d.]+)", re.I),
    re.compile(r"; used filament\s*=\s*([\d.]+)\s*g", re.I),
    re.compile(r"; total used filament\s*\[g\]\s*=\s*([\d.]+)", re.I),
    re.compile(r"; filament cost\s*\[g\]\s*:\s*([\d.]+)", re.I),
)


def parse_filament_grams_from_text(raw: str) -> float | None:
    """Slicer-Kommentare (Prusa/Orca/Creality) — bevorzugt Gramm-Zeilen."""
    best: float | None = None
    for pat in _HEADER_FILAMENT_RE:
        for m in pat.finditer(raw):
            try:
                v = float(m.group(1))
            except ValueError:
                continue
            if "[mm]" in pat.pattern.lower():
                v = v * 0.33
            g = plausible_filament_grams(v)
            if g is None:
                continue
            if best is None or g > best:
                best = g
    return best


def parse_filament_grams_from_file(path: Path, *, max_bytes: int = 120_000) -> float | None:
    """Slicer-Kommentare am Dateianfang (Prusa/Orca/Creality)."""
    try:
        with path.open("rb") as f:
            raw = f.read(max_bytes).decode("utf-8", errors="ignore")
    except OSError:
        return None
    return parse_filament_grams_from_text(raw)


def resolve_local_gcode_path(
    gcode_name: str,
    *,
    extra_dirs: list[Path] | None = None,
) -> Path | None:
    """Lokale G-Code-Datei für Verbrauchsschätzung (Cache, Downloads)."""
    bare = Path(str(gcode_name or "").replace("\\", "/").split("/")[-1])
    if not bare.name:
        return None
    dirs: list[Path] = []
    if extra_dirs:
        dirs.extend(extra_dirs)
    try:
        from app.paths import DATA_DIR

        dirs.append(DATA_DIR / "gcode_cache")
    except ImportError:
        pass
    home = Path.home()
    dirs.extend([home / "Downloads", home / "Desktop"])
    seen: set[Path] = set()
    for d in dirs:
        if not d or d in seen:
            continue
        seen.add(d)
        if not d.is_dir():
            continue
        for candidate in (d / bare.name, d / bare):
            if candidate.is_file():
                return candidate
    return None


def total_job_filament_grams(
    state: dict[str, Any],
    gcode_name: str,
    *,
    file_entry: dict[str, Any] | None = None,
    local_path: Path | None = None,
) -> tuple[int, str] | None:
    """
    Beste Schätzung Gesamtverbrauch (g) — Drucker-Metadaten, sonst Slicer-Kommentar.
    Ignoriert unrealistische Werte (<5 g) aus retGcodeFileInfo2.
    """
    if local_path is None:
        local_path = resolve_local_gcode_path(gcode_name)
    if local_path and local_path.is_file():
        g = parse_filament_grams_from_file(local_path)
        if g is not None:
            return int(round(g)), "G-Code-Datei (Slicer-Kommentar)"

    info = file_entry
    if info is None and gcode_name:
        info = find_gcode_file_info(state, gcode_name)
    if info:
        specs = active_filament_specs(parse_filament_specs(info))
        weights = [
            plausible_filament_grams(s.weight_g)
            for s in specs
            if s.weight_g is not None
        ]
        weights = [w for w in weights if w is not None]
        if weights:
            total = sum(weights)
            if total >= _MIN_PLAUSIBLE_GRAMS:
                label = "G-Code Metadaten (Summe)" if len(weights) > 1 else "G-Code Metadaten"
                return int(round(total)), label

    return None


def estimate_grams_for_slot(
    state: dict[str, Any],
    gcode_name: str,
    slot_index: int | None,
    slots: list[CfsSlotInfo] | None = None,
    *,
    file_entry: dict[str, Any] | None = None,
    local_path: Path | None = None,
) -> tuple[int, str] | None:
    """
    Geschätzter Verbrauch in Gramm für einen CFS-Slot.
    Rückgabe: (gramm, Quelle) z. B. (42, "G-Code Metadaten").
    """
    info = gcode_info_from_entry(file_entry) if file_entry else None
    if info is None and gcode_name:
        info = find_gcode_file_info(state, gcode_name)
    if not info:
        return None

    specs = parse_filament_specs(info)
    active = active_filament_specs(specs)
    if not active:
        return None

    if slot_index is not None and 0 <= slot_index <= 3:
        for spec in specs:
            if spec.extruder_index == slot_index and spec.weight_g and spec.weight_g > 0.01:
                return int(round(spec.weight_g)), "G-Code (Extruder/Slot)"

        if slots:
            for idx, spec in resolve_slots_from_gcode(
                state,
                gcode_name,
                slots,
                file_entry=file_entry,
                loaded_slot_index=slot_index,
            ):
                if idx == slot_index and spec.weight_g and spec.weight_g > 0.01:
                    return int(round(spec.weight_g)), "G-Code (Farbe → Slot)"

        if len(active) == 1 and active[0].weight_g and active[0].weight_g > 0.01:
            if slots:
                resolved = resolve_slot_for_spec(
                    slots,
                    active[0],
                    gcode_path=gcode_name,
                    loaded_slot_index=slot_index,
                    single_filament=True,
                )
                if resolved is None or (
                    slot_index is not None and resolved != slot_index
                ):
                    return None
            return int(round(active[0].weight_g)), "G-Code (eine Farbe)"

    total = sum(
        g
        for s in active
        if (g := plausible_filament_grams(s.weight_g)) is not None
    )
    if total >= _MIN_PLAUSIBLE_GRAMS:
        return int(round(total)), "G-Code (Summe)"

    return total_job_filament_grams(
        state,
        gcode_name,
        file_entry=file_entry,
        local_path=local_path,
    )


def build_slot_usage_plan(
    state: dict[str, Any],
    gcode_path: str,
    slots: list[CfsSlotInfo],
    *,
    file_entry: dict[str, Any] | None = None,
    loaded_slot_index: int | None = None,
) -> list[GcodeSlotUsage]:
    """
    Alle im G-Code genutzten Farben → CFS-Slot + Gramm (aus Slicer-Metadaten).
  """
    mappings = resolve_slots_from_gcode(
        state,
        gcode_path,
        slots,
        file_entry=file_entry,
        loaded_slot_index=loaded_slot_index,
    )
    out: list[GcodeSlotUsage] = []
    seen: set[int] = set()
    for slot_idx, spec in mappings:
        if slot_idx in seen:
            continue
        seen.add(slot_idx)
        g = plausible_filament_grams(spec.weight_g)
        if g is None:
            continue
        out.append(
            GcodeSlotUsage(
                slot_index=slot_idx,
                slot_label=SLOT_LABELS[slot_idx],
                spec=spec,
                grams=int(round(g)),
                source=_usage_source_label(gcode_path, spec),
            )
        )

    if not out:
        job = total_job_filament_grams(state, gcode_path, file_entry=file_entry)
        if job:
            grams_total, src = job
            targets = mappings or []
            if not targets and loaded_slot_index is not None:
                targets = [
                    (
                        loaded_slot_index,
                        GcodeFilamentSpec(
                            loaded_slot_index,
                            None,
                            material_hint_from_gcode_path(gcode_path),
                            float(grams_total),
                        ),
                    )
                ]
            if len(targets) == 1:
                idx, spec = targets[0]
                out.append(
                    GcodeSlotUsage(
                        slot_index=idx,
                        slot_label=SLOT_LABELS[idx],
                        spec=spec,
                        grams=grams_total,
                        source=src,
                    )
                )
            elif len(targets) > 1:
                share = max(_MIN_PLAUSIBLE_GRAMS, grams_total / len(targets))
                for idx, spec in targets:
                    out.append(
                        GcodeSlotUsage(
                            slot_index=idx,
                            slot_label=SLOT_LABELS[idx],
                            spec=spec,
                            grams=int(round(share)),
                            source=f"{src} (Anteil {len(targets)} Farben)",
                        )
                    )
    return out


def _usage_source_label(gcode_path: str, spec: GcodeFilamentSpec) -> str:
    parts = ["G-Code filamentWeight"]
    hint = material_hint_from_gcode_path(gcode_path)
    if hint and (spec.material_type or "").upper() != hint:
        parts.append(f"Material aus Dateiname: {hint}")
    elif spec.material_type:
        parts.append(spec.material_type)
    return " · ".join(parts)


def resolve_slots_from_gcode(
    state: dict[str, Any],
    gcode_path: str,
    slots: list[CfsSlotInfo],
    *,
    file_entry: dict[str, Any] | None = None,
    loaded_slot_index: int | None = None,
) -> list[tuple[int, GcodeFilamentSpec]]:
    """
    G-Code-Farben → CFS-Slot-Indizes.
    Rückgabe: [(slot_index, spec), …] für alle aktiven Extruder im G-Code.
    """
    info = merge_gcode_filament_info(state, gcode_path, file_entry)
    if not info:
        return []
    specs = active_filament_specs(parse_filament_specs(info))
    single_filament = len(specs) <= 1
    out: list[tuple[int, GcodeFilamentSpec]] = []
    for spec in specs:
        idx = resolve_slot_for_spec(
            slots,
            spec,
            gcode_path=gcode_path,
            loaded_slot_index=loaded_slot_index,
            single_filament=single_filament,
        )
        if idx is not None:
            out.append((idx, spec))
    return out
