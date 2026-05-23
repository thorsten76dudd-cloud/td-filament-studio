"""Druck-Check: G-Code-Farben vs. CFS-Slots und Spulen-Rest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from creality_nfc.cfs_adopt import CfsSlotInfo
from creality_nfc.cfs_layout import CfsLayout, cfs_slot_label, layout_from_slot_list
from creality_nfc.cfs_spool_link import find_spool_for_slot
from creality_nfc.gcode_filament import (
    build_slot_usage_plan,
    find_gcode_file_info,
    total_job_filament_grams,
)
from creality_nfc.spool_passport import compare_passport_with_slot
from creality_nfc.spool_usage import is_low_filament

if TYPE_CHECKING:
    from creality_nfc.spool_inventory import SpoolInventory


@dataclass
class ReadinessLine:
    level: str  # ok | warn | error | info
    text: str


@dataclass
class PrintReadinessReport:
    filename: str
    ready: bool
    lines: list[ReadinessLine] = field(default_factory=list)
    total_grams: int | None = None
    slot_plans: list = field(default_factory=list)

    def summary(self) -> str:
        if self.ready:
            return "Druck-Check: OK — Material und Rest passen."
        errs = sum(1 for ln in self.lines if ln.level == "error")
        warns = sum(1 for ln in self.lines if ln.level == "warn")
        return f"Druck-Check: {errs} Problem(e), {warns} Hinweis(e)"


def check_print_readiness(
    state: dict[str, Any],
    filename: str,
    inventory: SpoolInventory,
    cfs_slots: list[CfsSlotInfo] | None = None,
    *,
    layout: CfsLayout | None = None,
    local_gcode: Path | None = None,
    file_entry: dict[str, Any] | None = None,
    low_threshold_g: int = 200,
    loaded_slot_index: int | None = None,
) -> PrintReadinessReport:
    fn = (filename or "").strip()
    lines: list[ReadinessLine] = []
    if not fn:
        return PrintReadinessReport(
            filename="",
            ready=False,
            lines=[ReadinessLine("error", "Keine G-Code-Datei gewählt.")],
        )

    if layout is None:
        if cfs_slots:
            layout = layout_from_slot_list(cfs_slots)
        else:
            from creality_nfc.cfs_layout import parse_cfs_layout

            layout = parse_cfs_layout(state)
    slots = layout.all_slots()
    all_slots = slots

    entry = file_entry if file_entry else find_gcode_file_info(state, fn)
    job = total_job_filament_grams(state, fn, file_entry=entry, local_path=local_gcode)
    total_g = job[0] if job else None

    # Kein „aktuell geladenes“ Filament — Zuordnung nur aus G-Code-Farbe/Material.
    plans = build_slot_usage_plan(
        state,
        fn,
        slots,
        file_entry=entry,
        loaded_slot_index=None,
    )

    if not plans:
        lines.append(
            ReadinessLine(
                "warn",
                "Keine Farb-/Slot-Zuordnung aus G-Code — bitte Material im Slicer prüfen.",
            )
        )
    else:
        if total_g:
            lines.append(
                ReadinessLine("info", f"Geschätzter Gesamtverbrauch: ca. {total_g} g ({job[1]}).")
            )
        if plans and plans[0].spec.color_hex:
            lines.append(
                ReadinessLine(
                    "info",
                    f"G-Code-Farbe: {plans[0].spec.color_hex} → Slot {plans[0].slot_label}",
                )
            )
        for plan in plans:
            sid = plan.slot_index
            need_g = plan.grams
            lab = plan.slot_label
            slot = slots[sid] if 0 <= sid < len(slots) else None
            if slot is None or slot.empty:
                for s in all_slots:
                    if s.index == sid and not s.empty:
                        slot = s
                        lab = cfs_slot_label(getattr(s, "box_id", 1), s.index)
                        break
            if slot is None or slot.empty:
                lines.append(
                    ReadinessLine(
                        "error",
                        f"{lab}: Slot leer — G-Code braucht ca. {need_g} g "
                        f"({plan.spec.material_type or 'Material'}).",
                    )
                )
                continue

            mat = (slot.material_type or slot.name or "").strip()
            gmat = (plan.spec.material_type or "").strip()
            gcol = (plan.spec.color_hex or "").strip()
            scol = f"#{slot.color_hex}" if slot.color_hex else ""
            if gcol and scol:
                from creality_nfc.gcode_filament import _color_distance

                dist = _color_distance(gcol, scol)
                if dist > 80:
                    lines.append(
                        ReadinessLine(
                            "warn",
                            f"{lab}: Farbe G-Code ({gcol}) weicht von CFS ({scol}) ab.",
                        )
                    )
            if gmat and mat and gmat.upper() not in mat.upper() and mat.upper() not in gmat.upper():
                lines.append(
                    ReadinessLine(
                        "warn",
                        f"{lab}: Material G-Code ({gmat}) vs. CFS ({mat}).",
                    )
                )

            sp = find_spool_for_slot(inventory, slot)
            if sp is None:
                lines.append(
                    ReadinessLine(
                        "warn",
                        f"{lab}: keine Spule in „Meine Spulen“ verknüpft "
                        f"(ca. {need_g} g nötig).",
                    )
                )
            else:
                rem = sp.remaining_g
                if rem is None:
                    lines.append(
                        ReadinessLine(
                            "warn",
                            f"{lab}: „{sp.label}“ — Rest unbekannt, ca. {need_g} g nötig.",
                        )
                    )
                elif rem < need_g:
                    lines.append(
                        ReadinessLine(
                            "error",
                            f"{lab}: „{sp.label}“ — nur {rem} g Rest, ca. {need_g} g nötig.",
                        )
                    )
                elif is_low_filament(sp, low_threshold_g) or rem - need_g < low_threshold_g:
                    after = max(0, rem - need_g)
                    lines.append(
                        ReadinessLine(
                            "warn",
                            f"{lab}: „{sp.label}“ — nach Druck ca. {after} g "
                            f"(unter {low_threshold_g} g Schwelle).",
                        )
                    )
                else:
                    lines.append(
                        ReadinessLine(
                            "ok",
                            f"{lab}: „{sp.label}“ — {rem} g Rest, ca. {need_g} g nötig.",
                        )
                    )
                for issue in compare_passport_with_slot(sp, slot):
                    lines.append(ReadinessLine("warn", f"{lab}: {issue}"))

    if not plans and total_g and total_g > 0:
        lines.append(
            ReadinessLine(
                "info",
                f"Gesamt ca. {total_g} g — keine Slot-Aufteilung im G-Code.",
            )
        )
        for sp in inventory.all():
            rem = sp.remaining_g
            if rem is None:
                continue
            if rem < total_g:
                lines.append(
                    ReadinessLine(
                        "error",
                        f"„{sp.label}“: nur {rem} g Rest, Job braucht ca. {total_g} g.",
                    )
                )
            elif rem - total_g < low_threshold_g:
                lines.append(
                    ReadinessLine(
                        "warn",
                        f"„{sp.label}“: nach Job ca. {max(0, rem - total_g)} g Rest.",
                    )
                )

    if layout.box_count() > 1:
        lines.insert(
            0,
            ReadinessLine(
                "info",
                f"{layout.box_count()} CFS-Einheiten erkannt (Slots 1A–{layout.box_count()}D).",
            ),
        )

    has_error = any(ln.level == "error" for ln in lines)
    return PrintReadinessReport(
        filename=fn,
        ready=not has_error,
        lines=lines,
        total_grams=total_g,
        slot_plans=plans,
    )
