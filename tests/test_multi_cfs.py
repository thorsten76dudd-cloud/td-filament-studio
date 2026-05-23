"""Tests: bis zu 4 CFS-Einheiten am einen K2."""

import unittest

from creality_nfc.cfs_adopt import parse_cfs_meta
from creality_nfc.cfs_feed import (
    find_loaded_slot_ref,
    find_loaded_flat_index,
    resolve_live_filament_slot_index,
)
from creality_nfc.cfs_layout import parse_cfs_layout
from creality_nfc.cfs_slot_index import flat_slot_index, usage_slot_label
from creality_nfc.print_readiness import check_print_readiness
from creality_nfc.spool_inventory import Spool, SpoolInventory


def _two_box_state() -> dict:
    return {
        "cfsConnect": 1,
        "boxsInfo": {
            "materialBoxs": [
                {
                    "type": 0,
                    "id": 1,
                    "materials": [
                        {
                            "vendor": "A",
                            "name": "Orange",
                            "type": "PETG",
                            "color": "FF8000",
                            "state": 0,
                        },
                        {"state": 0},
                        {"state": 0},
                        {"state": 0},
                    ],
                },
                {
                    "type": 0,
                    "id": 2,
                    "materials": [
                        {"state": 0},
                        {"state": 0},
                        {"state": 0},
                        {
                            "vendor": "B",
                            "name": "Weiss",
                            "type": "PLA",
                            "color": "FFFFFF",
                            "state": 2,
                        },
                    ],
                },
            ],
        },
        "retGcodeFileInfo2": [
            {
                "name": "part_PETG.gcode",
                "materialColors": "#ff8000;;;",
                "material": "PETG;;;",
                "filamentWeight": "3.0, 0, 0, 0",
            }
        ],
    }


class MultiCfsTests(unittest.TestCase):
    def test_layout_eight_slots(self) -> None:
        layout = parse_cfs_layout(_two_box_state())
        self.assertEqual(layout.box_count(), 2)
        slots = layout.all_slots()
        self.assertEqual(len(slots), 8)
        self.assertEqual(slots[0].label, "1A")
        self.assertEqual(slots[7].label, "2D")

    def test_loaded_on_box_two(self) -> None:
        state = _two_box_state()
        ref = find_loaded_slot_ref(state)
        self.assertEqual(ref, (2, 3))
        layout = parse_cfs_layout(state)
        flat = find_loaded_flat_index(state, layout.all_slots())
        self.assertEqual(flat, 7)

    def test_live_slot_prefers_gcode_on_box_one(self) -> None:
        state = _two_box_state()
        slots = parse_cfs_layout(state).all_slots()
        self.assertEqual(
            resolve_live_filament_slot_index(state, "part_PETG.gcode", slots),
            0,
        )

    def test_usage_label_box_two(self) -> None:
        slots = parse_cfs_layout(_two_box_state()).all_slots()
        self.assertEqual(usage_slot_label(slots, 7), "2D")

    def test_readiness_uses_second_box(self) -> None:
        state = _two_box_state()
        layout = parse_cfs_layout(state)
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            inv.spools = [
                Spool(
                    id="1",
                    label="Weiss",
                    cfs_box_id=2,
                    cfs_slot=3,
                    remaining_g=500,
                ),
            ]
            report = check_print_readiness(
                state,
                "part_PETG.gcode",
                inv,
                layout=layout,
            )
        labels = [p.slot_label for p in report.slot_plans]
        self.assertIn("1A", labels)
        texts = " ".join(ln.text for ln in report.lines)
        self.assertIn("1A", texts)
        self.assertNotIn("2D", labels)

    def test_meta_tracks_box_id(self) -> None:
        meta = parse_cfs_meta(_two_box_state())
        self.assertEqual(meta.loaded_index, 3)
        self.assertEqual(meta.loaded_box_id, 2)


if __name__ == "__main__":
    unittest.main()
