"""Filament-Farbe und -typ aus G-Code-Metadaten (retGcodeFileInfo2 am K2)."""

from __future__ import annotations

import math
import re
import time
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


def _split_numeric_fields(raw: str) -> list[str]:
    """Komma oder Semikolon (Drucker/Orca mischen beides)."""
    if not raw:
        return []
    return [p.strip() for p in re.split(r"[,;]", str(raw)) if p.strip()]


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


def mm_filament_to_grams(
    length_mm: float,
    *,
    diameter_mm: float = 1.75,
    density_g_cm3: float = 1.24,
) -> float:
    """Filamentlänge (mm) → Gramm (PETG/PLA ~1,24 g/cm³, 1,75 mm)."""
    if length_mm <= 0:
        return 0.0
    r_cm = (diameter_mm / 10.0) / 2.0
    length_cm = length_mm / 10.0
    volume_cm3 = math.pi * r_cm * r_cm * length_cm
    return volume_cm3 * density_g_cm3


def _grams_from_printer_slot(
    fw_raw: str | None,
    used_raw: str | None,
) -> float | None:
    """
    K2 retGcodeFileInfo2: filamentWeight oft Slicer-Schätzung;
    materialUsed oft Ist-Verbrauch in mm (z. B. 7380 → ~22 g).
    """
    fw = _parse_float(fw_raw) if fw_raw not in (None, "") else None
    used = _parse_float(used_raw) if used_raw not in (None, "") else None
    fw_g = slot_filament_grams(fw) if fw is not None else None
    used_g = _material_used_to_grams(used) if used is not None and used > 0 else None
    if used_g is not None and fw_g is not None:
        if fw_g > used_g * 2.5 and used_g >= 0.1:
            return used_g
        if used_g > fw_g * 2.5 and fw_g >= 0.1:
            return fw_g
    return used_g if used_g is not None else fw_g


def slot_filament_grams(val: float | None) -> float | None:
    """Pro CFS-Slot / Farbe — auch kleine Orca-Werte (z. B. 0,2 g Blau)."""
    if val is None or val <= 0.01:
        return None
    if val > _MAX_PLAUSIBLE_GRAMS:
        return None
    if val >= _MIN_PLAUSIBLE_GRAMS:
        return val
    if val >= 0.15:
        return val
    return None


def _material_used_to_grams(v: float) -> float | None:
    """K2 materialUsed: praktisch immer extrudierte Länge in mm."""
    if v <= 0:
        return None
    if v >= 15:
        return slot_filament_grams(mm_filament_to_grams(v))
    return slot_filament_grams(v)


def _nonzero_usage_grams(values: list[str]) -> list[float]:
    """Alle materialUsed-Werte > 0 in Reihenfolge (mm → g)."""
    out: list[float] = []
    for raw in values:
        v = _parse_float(raw)
        if v is None:
            continue
        g = _material_used_to_grams(v)
        if g is not None:
            out.append(g)
    return out


def parse_filament_specs(info: dict[str, Any]) -> list[GcodeFilamentSpec]:
    """Aus retGcodeFileInfo2-Eintrag (materialColors, material, filamentWeight)."""
    colors = _split_fields(str(info.get("materialColors") or ""), ";")
    materials = _split_fields(str(info.get("material") or ""), ";")
    weights = _split_numeric_fields(str(info.get("filamentWeight") or ""))
    used = _split_numeric_fields(str(info.get("materialUsed") or ""))

    color_hexes = [creality_color_to_hex(c) for c in colors if c]
    color_hexes = [h for h in color_hexes if h]
    used_by_order = _nonzero_usage_grams(used)
    fw_by_order: list[float] = []
    for raw in weights:
        g = _grams_from_printer_slot(raw or None, None)
        if g is not None:
            fw_by_order.append(g)

    n = max(len(colors), len(materials), len(weights), len(used), 4)
    specs: list[GcodeFilamentSpec] = []
    color_slot = 0
    for i in range(n):
        color_raw = colors[i] if i < len(colors) else ""
        mat = materials[i] if i < len(materials) else ""
        color_hex = creality_color_to_hex(color_raw) if color_raw else None
        mtype = mat.strip() if mat and mat.strip() else None
        w: float | None = None
        if color_hex and color_slot < len(used_by_order) and len(used_by_order) == len(color_hexes):
            w = used_by_order[color_slot]
            color_slot += 1
        else:
            fw_t = weights[i] if i < len(weights) else ""
            used_t = used[i] if i < len(used) else ""
            w = _grams_from_printer_slot(fw_t or None, used_t or None)
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
    by_weight = [
        s
        for s in specs
        if slot_filament_grams(s.weight_g) is not None
    ]
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

# Creality Print 7.x: Verbrauch + CONFIG_BLOCK oft erst nach END_PRINT (Dateiende).
_GCODE_TAIL_BYTES = 400_000


def _read_gcode_region(path: Path, *, max_bytes: int, from_end: bool) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            read_len = min(max_bytes, size)
            if from_end and size > read_len:
                f.seek(size - read_len)
            raw = f.read(read_len)
        return raw.decode("utf-8", errors="ignore")
    except OSError:
        return ""


def format_gcode_snippet_for_view(
    path: Path | str,
    *,
    head_bytes: int = 96_000,
    tail_bytes: int = 48_000,
) -> tuple[str, str]:
    """
    G-Code-Text für die Anzeige (Anfang + ggf. Ende großer Dateien).
    Rückgabe: (text, statuszeile).
    """
    p = Path(path)
    if not p.is_file():
        return "", "Datei nicht gefunden."
    try:
        size = p.stat().st_size
    except OSError:
        return "", "Datei nicht lesbar."
    head = _read_gcode_region(p, max_bytes=head_bytes, from_end=False)
    if size <= head_bytes + 1024:
        lines = head.count("\n") + 1
        return head, f"{size:,} Bytes · {lines:,} Zeilen (vollständig)"
    tail = _read_gcode_region(p, max_bytes=tail_bytes, from_end=True)
    omitted = max(0, size - head_bytes - tail_bytes)
    mid = (
        f"; --- {omitted:,} Bytes in der Mitte nicht angezeigt "
        f"(„Herunterladen…“ für die ganze Datei) ---\n"
    )
    text = head.rstrip() + "\n\n" + mid + "\n" + tail.lstrip()
    return text, f"{size:,} Bytes · Anfang + Ende (Vorschau)"


def _active_weight_slots(weights: list[float]) -> int:
    return sum(1 for w in weights if w is not None and w > 0.01)


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
    gcode_path: str | Path, *, max_bytes: int = 120_000, tail_bytes: int = _GCODE_TAIL_BYTES
) -> tuple[list[str], list[str]]:
    """
    Farben/Material aus Slicer-Kommentaren (Kopf + bei großen Dateien Footer).
    Rückgabe: (farben als #RRGGBB, materialtypen).
    """
    path = Path(gcode_path) if not isinstance(gcode_path, Path) else gcode_path
    if not path.is_file():
        resolved = _resolve_local_gcode_path(str(gcode_path))
        if resolved is None:
            return [], []
        path = resolved

    head_raw = _read_gcode_region(path, max_bytes=max_bytes, from_end=False)
    head = _parse_filament_fields_from_text(head_raw, stop_on_motion=True, max_lines=400)
    tail: tuple[list[str], list[str], list[float]] = ([], [], [])
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    if file_size > max_bytes:
        tail_raw = _read_gcode_region(path, max_bytes=tail_bytes, from_end=True)
        tail = _parse_filament_fields_from_text(
            tail_raw, stop_on_motion=False, max_lines=None
        )
    colors, materials, _weights = _merge_filament_field_lists(head, tail)
    return colors, materials


_RE_FILAMENT_LIST_LINE = re.compile(
    r"filament_colou?rs?\s*[=:]\s*(.+)$",
    re.I,
)
_RE_FILAMENT_USED_G_LIST = re.compile(
    r"(?:^|;\s*)(?:total\s+)?filament used \[g\]\s*[=:]\s*([\d.,\s]+)\s*$",
    re.I | re.M,
)
_RE_FILAMENT_USED_G_ORCA = re.compile(
    r"filament_used_g\s*[=:]\s*([\d.,\s]+)",
    re.I,
)
_RE_MATERIAL_LIST = re.compile(r";?\s*material\s*[=:]\s*([A-Za-z0-9 _+,-]+)\s*$", re.I)
_RE_FILAMENT_TYPE_LIST = re.compile(r"filament_type\s*[=:]\s*(.+)$", re.I)


def _parse_color_token_list(raw: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"[,;]", raw):
        hx = creality_color_to_hex(part.strip().strip("\"'"))
        if hx:
            out.append(hx)
    return out


def _parse_float_list(raw: str) -> list[float]:
    out: list[float] = []
    for part in re.split(r"[,;]", raw):
        v = _parse_float(part)
        if v is not None:
            out.append(v)
    return out


def _parse_filament_fields_from_text(
    raw: str,
    *,
    stop_on_motion: bool,
    max_lines: int | None = 600,
) -> tuple[list[str], list[str], list[float]]:
    """
    Farben, Materialtypen und Gramm pro Extruder aus Slicer-Kommentaren.
    stop_on_motion: True am Dateianfang (Abbruch bei erstem G-Befehl).
    """
    colors: list[str] = []
    materials: list[str] = []
    weights: list[float] = []
    total_g: float | None = None

    lines = raw.splitlines()
    if max_lines is not None:
        lines = lines[:max_lines]

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(";"):
            if stop_on_motion and stripped.startswith("G"):
                break
            continue
        body = stripped.lstrip(";").strip()

        m_col = _RE_FILAMENT_LIST_LINE.search(body)
        if m_col:
            parsed = _parse_color_token_list(m_col.group(1))
            if len(parsed) > len(colors):
                colors = parsed
            continue

        for pat in _HEADER_COLOR_RE[:2]:
            m = pat.search(body)
            if m:
                hx = None
                for g in m.groups():
                    if g and creality_color_to_hex(g):
                        hx = creality_color_to_hex(g)
                        break
                if hx and not _RE_FILAMENT_LIST_LINE.search(body):
                    colors.append(hx)
                break

        m_type = _RE_FILAMENT_TYPE_LIST.search(body)
        if m_type:
            parsed_m = [p.strip() for p in re.split(r"[,;]", m_type.group(1)) if p.strip()]
            if len(parsed_m) > len(materials):
                materials = parsed_m
            continue

        m_mat = _RE_MATERIAL_LIST.match(body)
        if m_mat:
            for part in re.split(r"[,;]", m_mat.group(1)):
                mt = part.strip()
                if mt:
                    materials.append(mt)
            continue

        if re.search(r"total\s+filament", body, re.I):
            m_tot = _RE_FILAMENT_USED_G_LIST.search(body)
            if m_tot:
                vals = _parse_float_list(m_tot.group(1))
                if len(vals) == 1:
                    total_g = plausible_filament_grams(vals[0]) or vals[0]
            continue

        m_used = _RE_FILAMENT_USED_G_LIST.search(body) or _RE_FILAMENT_USED_G_ORCA.search(body)
        if m_used:
            vals = _parse_float_list(m_used.group(1))
            plausible = [slot_filament_grams(v) for v in vals]
            plausible = [p for p in plausible if p is not None]
            if len(plausible) >= 2:
                weights = plausible
            elif len(plausible) == 1 and not weights:
                weights = plausible

    if not weights and total_g is not None:
        return colors, materials, []
    return colors, materials, weights


def _merge_filament_field_lists(
    head: tuple[list[str], list[str], list[float]],
    tail: tuple[list[str], list[str], list[float]],
) -> tuple[list[str], list[str], list[float]]:
    hc, hm, hw = head
    tc, tm, tw = tail
    if _active_weight_slots(tw) > _active_weight_slots(hw):
        return (
            tc if len(tc) >= len(hc) else hc,
            tm if len(tm) >= len(hm) else hm,
            tw,
        )
    if _active_weight_slots(hw) > 0:
        return hc, hm, hw
    if _active_weight_slots(tw) > 0:
        return (
            tc if tc else hc,
            tm if tm else hm,
            tw,
        )
    return hc or tc, hm or tm, hw or tw


def _filament_specs_from_fields(
    colors: list[str],
    materials: list[str],
    weights: list[float],
) -> list[GcodeFilamentSpec]:
    n = max(len(colors), len(materials), len(weights), 1)
    specs: list[GcodeFilamentSpec] = []
    for i in range(n):
        w = weights[i] if i < len(weights) else None
        if w is not None:
            w = slot_filament_grams(w)
        specs.append(
            GcodeFilamentSpec(
                extruder_index=i,
                color_hex=colors[i] if i < len(colors) else None,
                material_type=materials[i] if i < len(materials) else None,
                weight_g=w,
            )
        )
    out = [s for s in specs if s.weight_g or s.color_hex]
    if weights:
        active = [s for s in out if s.weight_g is not None and s.weight_g > 0.01]
        if active:
            return active
    return out


def parse_filament_specs_from_gcode_file(
    gcode_path: str | Path, *, max_bytes: int = 200_000, tail_bytes: int = _GCODE_TAIL_BYTES
) -> list[GcodeFilamentSpec]:
    """
    Orca/Bambu/Creality: Farben + Gramm pro Filament.
    Kopf (Orca/Prusa) und bei großen Dateien zusätzlich Footer (Creality Print 7.x).
    """
    path = Path(gcode_path) if not isinstance(gcode_path, Path) else gcode_path
    if not path.is_file():
        resolved = resolve_local_gcode_path(str(gcode_path))
        if resolved is None:
            return []
        path = resolved

    head_raw = _read_gcode_region(path, max_bytes=max_bytes, from_end=False)
    head = _parse_filament_fields_from_text(head_raw, stop_on_motion=True)

    tail: tuple[list[str], list[str], list[float]] = ([], [], [])
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    if file_size > max_bytes:
        tail_raw = _read_gcode_region(path, max_bytes=tail_bytes, from_end=True)
        tail = _parse_filament_fields_from_text(
            tail_raw, stop_on_motion=False, max_lines=None
        )

    colors, materials, weights = _merge_filament_field_lists(head, tail)
    return _filament_specs_from_fields(colors, materials, weights)


def _specs_to_info_fields(specs: list[GcodeFilamentSpec]) -> dict[str, str]:
    colors = ";".join(s.color_hex or "" for s in specs)
    materials = ";".join(s.material_type or "" for s in specs)
    weights = ",".join(
        f"{s.weight_g:.2f}".rstrip("0").rstrip(".") if s.weight_g is not None else "0"
        for s in specs
    )
    return {
        "materialColors": colors,
        "material": materials,
        "filamentWeight": weights,
    }


def _should_prefer_file_filament_specs(
    file_specs: list[GcodeFilamentSpec],
    printer_specs: list[GcodeFilamentSpec],
    *,
    local_path: Path | None,
) -> bool:
    file_active = active_filament_specs(file_specs)
    if not file_active or not any(s.weight_g for s in file_active):
        return False
    file_total = sum(s.weight_g or 0 for s in file_active)
    printer_active = active_filament_specs(printer_specs)
    printer_total = sum(s.weight_g or 0 for s in printer_active)
    header_total = (
        parse_filament_grams_from_file(local_path) if local_path and local_path.is_file() else None
    )
    ref = header_total or file_total
    if ref and printer_total > ref * 1.35 + 2:
        return True
    if len(file_active) >= 2 and abs(printer_total - file_total) > max(3.0, file_total * 0.25):
        return True
    return False


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

    local_path = resolve_local_gcode_path(gcode_path)
    if local_path and local_path.is_file():
        file_specs = parse_filament_specs_from_gcode_file(local_path)
        if file_specs:
            printer_specs = parse_filament_specs(merged) if merged else []
            if _should_prefer_file_filament_specs(
                file_specs, printer_specs, local_path=local_path
            ):
                merged.update(_specs_to_info_fields(file_specs))
            elif not merged.get("filamentWeight") and any(s.weight_g for s in file_specs):
                merged.update(_specs_to_info_fields(file_specs))
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
    for m in _RE_FILAMENT_USED_G_LIST.finditer(raw):
        vals = _parse_float_list(m.group(1))
        plausible = [slot_filament_grams(v) for v in vals]
        plausible = [p for p in plausible if p is not None]
        if len(plausible) >= 2:
            total = sum(plausible)
            if best is None or total > best:
                best = total
        elif len(plausible) == 1:
            g = plausible[0]
            if best is None or g > best:
                best = g
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


def parse_filament_grams_from_file(
    path: Path, *, max_bytes: int = 120_000, tail_bytes: int = _GCODE_TAIL_BYTES
) -> float | None:
    """Slicer-Kommentare (Kopf + bei großen Dateien Footer)."""
    head_raw = _read_gcode_region(path, max_bytes=max_bytes, from_end=False)
    best = parse_filament_grams_from_text(head_raw)
    try:
        file_size = path.stat().st_size
    except OSError:
        file_size = 0
    if file_size > max_bytes:
        tail_raw = _read_gcode_region(path, max_bytes=tail_bytes, from_end=True)
        tail_best = parse_filament_grams_from_text(tail_raw)
        if tail_best is not None and (best is None or tail_best > best):
            best = tail_best
    return best


def cache_gcode_from_printer(
    host: str,
    password: str,
    file_entry: dict[str, Any],
) -> Path | None:
    """G-Code per SSH in data/gcode_cache/ — für Slicer-Kommentare ohne manuellen Klick."""
    if not host or not password or not file_entry:
        return None
    try:
        from creality_nfc.printer_gcode import entry_remote_path
        from creality_nfc.printer_ssh import download_gcode_from_printer

        remote = entry_remote_path(file_entry)
        name = str(file_entry.get("name") or Path(remote).name).strip()
        if not name.lower().endswith(".gcode"):
            return None
        try:
            from app.paths import GCODE_CACHE_DIR
        except ImportError:
            return None
        GCODE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        dest = GCODE_CACHE_DIR / name
        download_gcode_from_printer(host, password, remote, dest)
        if dest.is_file() and dest.stat().st_size >= 64:
            return dest
    except Exception:
        return None
    return None


def refresh_state_for_filament_usage(
    conn: Any | None,
    *,
    wait_sec: float = 0.9,
) -> dict[str, Any]:
    """Aktuelle retGcodeFileInfo2 vom Drucker holen (vor Verbrauchs-Dialog)."""
    if conn is None or not getattr(conn, "connected", False):
        return {}
    try:
        conn.request_get(
            reqGcodeFileInfo2=1,
            reqGcodeFile=1,
            reqGcodeFileInfo=1,
        )
        time.sleep(max(0.2, wait_sec))
        return conn.snapshot() or {}
    except Exception:
        return {}


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
        g = slot_filament_grams(spec.weight_g)
        if g is None:
            continue
        grams = int(round(g))
        if grams < 1 and g >= 0.15:
            grams = 1
        out.append(
            GcodeSlotUsage(
                slot_index=slot_idx,
                slot_label=SLOT_LABELS[slot_idx],
                spec=spec,
                grams=grams,
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
    local = resolve_local_gcode_path(gcode_path)
    if local and local.is_file() and active_filament_specs(
        parse_filament_specs_from_gcode_file(local)
    ):
        parts = ["G-Code-Datei (Slicer)"]
    else:
        parts = ["Drucker (materialUsed / Gewicht)"]
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
