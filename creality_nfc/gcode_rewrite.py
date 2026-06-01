"""G-Code-Metadaten (Creality Print) an lokale Spulen / RFID-IDs anpassen."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from creality_nfc.cfs_layout import cfs_slot_label
from creality_nfc.color_util import creality_color_to_hex
from creality_nfc.gcode_filament import (
    _GCODE_TAIL_BYTES,
    _merge_filament_field_lists,
    _parse_filament_fields_from_text,
    _read_gcode_region,
    parse_filament_colors_from_gcode_file,
    parse_filament_specs_from_gcode_file,
)
from creality_nfc.materials import normalize_filament_id
from creality_nfc.spool_inventory import Spool

_RE_FILAMENT_IDS = re.compile(r"^(;\s*filament_ids\s*=\s*)(.+)$", re.I | re.M)
_RE_FILAMENT_NOTES = re.compile(r"^(;\s*filament_notes\s*=\s*)(.+)$", re.I | re.M)
_RE_FILAMENT_SETTINGS = re.compile(
    r'^(;\s*filament_settings_id\s*=\s*)(.+)$', re.I | re.M
)
_RE_START_TOOL = re.compile(
    r"^(START_PRINT[^\n]*\n)T(\d)\s*$", re.I | re.M
)


@dataclass
class GcodeChannelInfo:
    index: int
    color_hex: str | None
    material_type: str | None
    weight_g: float
    filament_id: str
    profile_name: str
    notes_raw: str


@dataclass
class ChannelSpoolMapping:
    channel: int
    gcode_color: str | None
    gcode_id: str
    gcode_profile: str
    weight_g: float
    spool: Spool | None
    new_id: str = ""
    new_profile: str = ""
    new_notes: str = ""
    match_reason: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class GcodeRewritePlan:
    source_path: Path
    channels: list[GcodeChannelInfo]
    mappings: list[ChannelSpoolMapping]
    initial_tool: int | None
    warnings: list[str] = field(default_factory=list)


def _color_rgb(hex_color: str | None) -> tuple[int, int, int] | None:
    hx = creality_color_to_hex(hex_color)
    if not hx:
        return None
    rgb = hx.lstrip("#")
    return int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)


def _color_distance(a: str | None, b: str | None) -> float:
    ra, rb = _color_rgb(a), _color_rgb(b)
    if ra is None or rb is None:
        return 1e9
    return float(
        (ra[0] - rb[0]) ** 2 + (ra[1] - rb[1]) ** 2 + (ra[2] - rb[2]) ** 2
    ) ** 0.5


def _material_type_from_spool(spool: Spool) -> str:
    text = f"{spool.material_name} {spool.label}".upper()
    for tok in ("PLA", "PETG", "ABS", "ASA", "TPU", "PA", "PC", "PVA"):
        if tok in text:
            return tok
    return "PLA"


def _profile_name_from_spool(spool: Spool) -> str:
    name = (spool.material_name or "").strip()
    if name:
        return name
    label = (spool.label or "").strip()
    if " — " in label:
        return label.split(" — ", 1)[-1].strip()
    return label


def _notes_json(spool: Spool) -> str:
    fid = normalize_filament_id(spool.filament_id)
    payload = {
        "id": fid,
        "vendor": (spool.brand or "Creality").strip() or "Creality",
        "type": _material_type_from_spool(spool),
        "name": _profile_name_from_spool(spool),
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _format_notes_field(json_str: str) -> str:
    if not (json_str or "").strip():
        return ""
    escaped = json_str.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _split_semicolon_values(raw: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    in_quote = False
    for ch in raw.strip():
        if ch == '"':
            in_quote = not in_quote
            cur.append(ch)
        elif ch == ";" and not in_quote:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def _join_semicolon_values(values: list[str]) -> str:
    out: list[str] = []
    for v in values:
        v = v.strip()
        if not v:
            out.append("")
        elif " " in v or ";" in v:
            if v.startswith('"') and v.endswith('"'):
                out.append(v)
            else:
                out.append(f'"{v}"')
        else:
            out.append(v)
    return ";".join(out)


def _parse_config_lists(tail_text: str) -> tuple[list[str], list[str], list[str]]:
    ids: list[str] = []
    notes: list[str] = []
    profiles: list[str] = []
    for line in tail_text.splitlines():
        body = line.strip()
        if not body.startswith(";"):
            continue
        text = body.lstrip(";").strip()
        if text.lower().startswith("filament_ids"):
            raw = text.split("=", 1)[1].strip()
            ids = [normalize_filament_id(x) for x in raw.split(";")]
        elif text.lower().startswith("filament_notes"):
            raw = text.split("=", 1)[1].strip()
            notes = _split_semicolon_values(raw)
        elif text.lower().startswith("filament_settings_id"):
            raw = text.split("=", 1)[1].strip()
            profiles = [p.strip().strip('"') for p in _split_semicolon_values(raw)]
    return ids, notes, profiles


def _detect_initial_tool(head_text: str) -> int | None:
    m = _RE_START_TOOL.search(head_text)
    if m:
        try:
            return int(m.group(2))
        except ValueError:
            return None
    return None


def parse_gcode_for_rewrite(path: Path | str) -> GcodeRewritePlan:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"G-Code nicht gefunden: {p}")

    specs = parse_filament_specs_from_gcode_file(p)
    colors_cp, materials_cp = parse_filament_colors_from_gcode_file(p)
    tail = _read_gcode_region(p, max_bytes=_GCODE_TAIL_BYTES, from_end=True)
    head = _read_gcode_region(p, max_bytes=96_000, from_end=False)
    tail_fields = _parse_filament_fields_from_text(
        tail, stop_on_motion=False, max_lines=None
    )
    head_fields = _parse_filament_fields_from_text(
        head, stop_on_motion=True, max_lines=400
    )
    tc, tm, tw = tail_fields
    if len(tw) >= 2 and (
        sum(1 for w in tw if w > 0.01) > 0 or len(tc) >= 2
    ):
        colors = tc if tc else colors_cp
        materials = tm if tm else materials_cp
        weights = tw
    else:
        head_bundle: tuple[list[str], list[str], list[float]] = (
            colors_cp,
            materials_cp,
            [float(s.weight_g or 0) for s in specs],
        )
        colors, materials, weights = _merge_filament_field_lists(head_bundle, tail_fields)
    ids, notes, profiles = _parse_config_lists(tail)

    n = max(len(specs), len(colors), len(ids), 4)
    channels: list[GcodeChannelInfo] = []
    for i in range(n):
        spec = specs[i] if i < len(specs) else None
        channels.append(
            GcodeChannelInfo(
                index=i,
                color_hex=colors[i] if i < len(colors) else (spec.color_hex if spec else None),
                material_type=(
                    materials[i]
                    if i < len(materials)
                    else (spec.material_type if spec else None)
                ),
                weight_g=(
                    float(weights[i])
                    if i < len(weights)
                    else (float(spec.weight_g or 0) if spec else 0.0)
                ),
                filament_id=ids[i] if i < len(ids) else "",
                profile_name=profiles[i] if i < len(profiles) else "",
                notes_raw=notes[i] if i < len(notes) else "",
            )
        )

    return GcodeRewritePlan(
        source_path=p,
        channels=channels,
        mappings=[],
        initial_tool=_detect_initial_tool(head),
    )


def _spool_slot_label(spool: Spool) -> str:
    if spool.cfs_slot is not None:
        box = spool.cfs_box_id or 1
        return cfs_slot_label(box, spool.cfs_slot)
    return ""


def _types_compatible(gcode_type: str | None, spool: Spool) -> bool:
    gt = (gcode_type or "").strip().upper()
    st = _material_type_from_spool(spool)
    if not gt:
        return True
    if gt == st:
        return True
    if gt == "PETG" and st == "PETG":
        return True
    if gt == "PLA" and st == "PLA":
        return True
    return False


def build_spool_mappings(
    plan: GcodeRewritePlan,
    spools: list[Spool],
    *,
    only_active: bool = False,
) -> GcodeRewritePlan:
    """Kanäle im G-Code lokalen Spulen zuordnen (Farbe, Material, CFS)."""
    used_spool_ids: set[str] = set()
    mappings: list[ChannelSpoolMapping] = []
    cfs_spools = [s for s in spools if s.cfs_slot is not None]
    pool = cfs_spools if cfs_spools else list(spools)

    channel_order = sorted(
        plan.channels,
        key=lambda c: (-(1 if c.weight_g > 0.01 else 0), -c.weight_g, c.index),
    )
    mapping_by_ch: dict[int, ChannelSpoolMapping] = {}

    for ch in channel_order:
        if only_active and ch.weight_g <= 0.01 and not ch.color_hex:
            mappings.append(
                ChannelSpoolMapping(
                    channel=ch.index,
                    gcode_color=ch.color_hex,
                    gcode_id=ch.filament_id,
                    gcode_profile=ch.profile_name,
                    weight_g=ch.weight_g,
                    spool=None,
                    new_id=ch.filament_id,
                    new_profile=ch.profile_name,
                    new_notes=ch.notes_raw,
                    match_reason="unused",
                )
            )
            continue

        candidates = [s for s in pool if s.id not in used_spool_ids]
        best: Spool | None = None
        best_dist = 1e9
        for sp in candidates:
            if not _types_compatible(ch.material_type, sp):
                continue
            dist = _color_distance(ch.color_hex, sp.color_hex)
            if dist < best_dist:
                best_dist = dist
                best = sp

        if best is None and candidates:
            for sp in candidates:
                dist = _color_distance(ch.color_hex, sp.color_hex)
                if dist < best_dist:
                    best_dist = dist
                    best = sp

        m = ChannelSpoolMapping(
            channel=ch.index,
            gcode_color=ch.color_hex,
            gcode_id=ch.filament_id,
            gcode_profile=ch.profile_name,
            weight_g=ch.weight_g,
            spool=best,
        )
        if best:
            used_spool_ids.add(best.id)
            m.new_id = normalize_filament_id(best.filament_id)
            m.new_profile = _profile_name_from_spool(best)
            m.new_notes = _notes_json(best)
            slot = _spool_slot_label(best)
            m.match_reason = f"color+spool {slot}".strip()
            if best_dist > 120:
                m.warnings.append(
                    f"Kanal {ch.index}: Farbabweichung G-Code ↔ Spule ({best_dist:.0f})"
                )
        else:
            m.warnings.append(f"Kanal {ch.index}: keine passende Spule")
            m.new_id = ch.filament_id
            m.new_profile = ch.profile_name
            m.new_notes = ch.notes_raw

        mapping_by_ch[ch.index] = m

    for ch in plan.channels:
        mappings.append(mapping_by_ch[ch.index])

    plan.mappings = mappings
    if plan.initial_tool is not None:
        active = [m for m in mappings if m.channel == plan.initial_tool]
        if active and active[0].spool is None:
            plan.warnings.append(
                f"Start-Tool T{plan.initial_tool}: keine Spule zugeordnet"
            )
    return plan


def _replace_config_line(text: str, pattern: re.Pattern[str], new_value: str) -> str:
    def repl(m: re.Match[str]) -> str:
        return m.group(1) + new_value

    new_text, n = pattern.subn(repl, text, count=1)
    if n == 0:
        return text
    return new_text


def apply_rewrite_plan(plan: GcodeRewritePlan, dest: Path) -> Path:
    """G-Code-Datei mit angepassten filament_ids / notes / settings_id speichern."""
    if not plan.mappings:
        raise ValueError("Keine Zuordnung — zuerst build_spool_mappings aufrufen.")

    src = plan.source_path
    text = src.read_text(encoding="utf-8", errors="replace")
    n = max((m.channel for m in plan.mappings), default=-1) + 1

    new_ids = [
        plan.mappings[i].new_id if i < len(plan.mappings) else ""
        for i in range(n)
    ]
    while new_ids and not new_ids[-1]:
        new_ids.pop()
    if not new_ids:
        raise ValueError("Keine Kanäle zum Umschreiben.")

    new_notes = []
    new_profiles = []
    for i in range(len(new_ids)):
        m = plan.mappings[i] if i < len(plan.mappings) else None
        if m and m.new_notes:
            raw = m.new_notes.strip()
            if raw.startswith('"') and raw.endswith('"'):
                new_notes.append(raw)
            elif raw.startswith("{"):
                new_notes.append(_format_notes_field(raw))
            else:
                new_notes.append(raw)
        else:
            new_notes.append("")
        prof = (m.new_profile if m else "") or ""
        new_profiles.append(prof)

    text = _replace_config_line(
        text, _RE_FILAMENT_IDS, ";".join(new_ids)
    )
    text = _replace_config_line(
        text, _RE_FILAMENT_NOTES, _join_semicolon_values(new_notes)
    )
    text = _replace_config_line(
        text, _RE_FILAMENT_SETTINGS, _join_semicolon_values(new_profiles)
    )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    return dest


def default_output_path(source: Path) -> Path:
    stem = source.stem
    if stem.endswith("_TD"):
        return source
    return source.with_name(f"{stem}_TD.gcode")
