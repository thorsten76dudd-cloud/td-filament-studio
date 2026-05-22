"""Druck-Check: G-Code-Farbe → richtiger CFS-Slot (nicht immer 1A)."""

import unittest

from creality_nfc.cfs_adopt import parse_cfs_slots
from creality_nfc.gcode_filament import build_slot_usage_plan, resolve_slots_from_gcode
from creality_nfc.print_readiness import check_print_readiness
from creality_nfc.spool_inventory import Spool, SpoolInventory
from pathlib import Path
import tempfile


def _two_petg_slots_state() -> dict:
    return {
        "boxsInfo": {
            "materialBoxs": [
                {
                    "type": 0,
                    "id": 1,
                    "materials": [
                        {
                            "vendor": "Creality",
                            "name": "Orange",
                            "type": "PETG",
                            "color": "FF8000",
                            "state": 2,
                        },
                        {
                            "vendor": "Creality",
                            "name": "Blau",
                            "type": "PETG",
                            "color": "0000FF",
                        },
                        {},
                        {},
                    ],
                }
            ],
        },
    }


class PrintCheckColorTests(unittest.TestCase):
    def test_blue_gcode_maps_to_blue_slot_not_orange_loaded(self) -> None:
        state = _two_petg_slots_state()
        slots = parse_cfs_slots(state)
        entry = {
            "name": "teil.PETG.gcode",
            "materialColors": "#0000FF",
            "material": "PETG",
            "filamentWeight": "36",
        }
        maps = resolve_slots_from_gcode(
            state,
            "teil.PETG.gcode",
            slots,
            file_entry=entry,
            loaded_slot_index=0,
        )
        self.assertEqual(maps[0][0], 1)
        plans = build_slot_usage_plan(
            state,
            "teil.PETG.gcode",
            slots,
            file_entry=entry,
            loaded_slot_index=None,
        )
        self.assertEqual(plans[0].slot_index, 1)

    def test_readiness_warns_wrong_color_slot(self) -> None:
        state = _two_petg_slots_state()
        state["retGcodeFileInfo2"] = {
            "name": "teil.PETG.gcode",
            "materialColors": "#0000FF",
            "material": "PETG",
            "filamentWeight": "36",
        }
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "s.json")
            inv.add(
                Spool(
                    id="orange",
                    label="Orange",
                    cfs_slot=0,
                    remaining_g=800,
                    color_hex="FF8000",
                )
            )
            report = check_print_readiness(
                state,
                "teil.PETG.gcode",
                inv,
                loaded_slot_index=0,
            )
            self.assertTrue(
                any("1B" in ln.text for ln in report.lines),
                report.lines,
            )
            self.assertFalse(
                any(ln.level == "ok" and "1A" in ln.text for ln in report.lines),
                report.lines,
            )


    def test_active_specs_ignores_color_palette_without_weight(self) -> None:
        from creality_nfc.gcode_filament import GcodeFilamentSpec, active_filament_specs

        specs = [
            GcodeFilamentSpec(0, "#FF8000", "PETG", None),
            GcodeFilamentSpec(1, "#0000FF", "PETG", None),
            GcodeFilamentSpec(2, None, None, None),
            GcodeFilamentSpec(3, None, None, None),
        ]
        self.assertEqual(active_filament_specs(specs), [])


if __name__ == "__main__":
    unittest.main()
