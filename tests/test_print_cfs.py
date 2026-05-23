"""Tests: Druckstart CFS vs Spulenhalter, Filament-Status."""

import unittest

from creality_nfc.cfs_adopt import parse_cfs_slots
from creality_nfc.cfs_feed import (
    filament_ready_in_extruder,
    find_loaded_slot_index,
    resolve_live_filament_slot_index,
)
from creality_nfc.gcode_filament import gcode_uses_external_spool
from creality_nfc.print_cfs import build_print_steps, cfs_feed_required_before_print


class FilamentReadyTests(unittest.TestCase):
    def test_loaded_index_counts_as_ready(self) -> None:
        state = {
            "materialStatus": 0,
            "boxsInfo": {
                "materialBoxs": [
                    {
                        "type": 0,
                        "materials": [
                            {"state": 2, "selected": 0},
                            {"state": 0},
                            {"state": 0},
                            {"state": 0},
                        ],
                    }
                ]
            },
        }
        self.assertEqual(find_loaded_slot_index(state), 0)
        self.assertTrue(filament_ready_in_extruder(state, 0))

    def test_live_slot_prefers_gcode_over_wrong_loaded(self) -> None:
        """Firmware meldet 1D geladen, G-Code verbraucht vor allem Orange (1A)."""
        state = {
            "cfsConnect": 1,
            "boxsInfo": {
                "enable": 1,
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
                                "state": 0,
                            },
                            {
                                "vendor": "Creality",
                                "name": "Blau",
                                "type": "PETG",
                                "color": "0000FF",
                                "state": 0,
                            },
                            {
                                "vendor": "Creality",
                                "name": "Grau",
                                "type": "PETG",
                                "color": "808080",
                                "state": 0,
                            },
                            {
                                "vendor": "Creality",
                                "name": "Weiss",
                                "type": "PLA",
                                "color": "FFFFFF",
                                "state": 2,
                            },
                        ],
                    }
                ],
            },
            "retGcodeFileInfo2": [
                {
                    "name": "1A.stl_PETG_6m38s.gcode",
                    "materialColors": "#ff8000;#0000ff;;",
                    "material": "PETG;PETG;;",
                    "filamentWeight": "2.29, 0.66, 0.00, 0.00",
                }
            ],
        }
        slots = parse_cfs_slots(state)
        self.assertEqual(find_loaded_slot_index(state), 3)
        self.assertEqual(
            resolve_live_filament_slot_index(
                state,
                "1A.stl_PETG_6m38s.gcode",
                slots,
            ),
            0,
        )


class ExternalSpoolGcodeTests(unittest.TestCase):
    def test_metadata_enable_cfs_zero(self) -> None:
        self.assertTrue(gcode_uses_external_spool({"enableCfs": 0}))

    def test_metadata_cfs_enabled(self) -> None:
        self.assertFalse(gcode_uses_external_spool({"enableCfs": 1}))


class BuildPrintStepsTests(unittest.TestCase):
    def test_feeds_when_extruder_empty(self) -> None:
        state = {
            "cfsConnect": 1,
            "materialStatus": 0,
            "boxsInfo": {
                "enable": 1,
                "materialBoxs": [
                    {
                        "type": 0,
                        "id": 1,
                        "materials": [
                            {"vendor": "X", "name": "PLA", "type": "PLA", "color": "FF0000"},
                            {},
                            {},
                            {},
                        ],
                    }
                ],
            },
        }
        self.assertTrue(cfs_feed_required_before_print(state, 0))
        steps, _idx, _lbl, _mode = build_print_steps(
            "part.gcode",
            state,
            file_entry={
                "name": "part.gcode",
                "materialColors": "#ff0000",
                "material": "PLA",
                "nozzleTemp": 22000,
                "bedTemp": 6000,
            },
        )
        self.assertIn("feedInOrOut", str(steps))
        self.assertIn("nozzleTempControl", str(steps))
        self.assertIn("bedTempControl", str(steps))

    def test_default_skips_prefeed_when_loaded(self) -> None:
        state = {
            "cfsConnect": 1,
            "materialStatus": 0,
            "boxsInfo": {
                "enable": 1,
                "materialBoxs": [
                    {
                        "type": 0,
                        "id": 1,
                        "materials": [
                            {"vendor": "X", "name": "PLA", "type": "PLA", "color": "FF0000", "state": 2},
                            {},
                            {},
                            {},
                        ],
                    }
                ],
            },
        }
        self.assertFalse(cfs_feed_required_before_print(state, 0))
        steps, _idx, _lbl, mode = build_print_steps(
            "part.gcode",
            state,
            file_entry={"name": "part.gcode", "materialColors": "#ff0000", "material": "PLA"},
        )
        self.assertEqual(mode, "normal")
        self.assertNotIn("feedInOrOut", str(steps))

    def test_loaded_slot_skips_prefeed(self) -> None:
        state = {
            "cfsConnect": 1,
            "materialStatus": 0,
            "boxsInfo": {
                "enable": 1,
                "materialBoxs": [
                    {
                        "type": 0,
                        "id": 1,
                        "materials": [
                            {"vendor": "X", "name": "PLA", "type": "PLA", "color": "FF0000", "state": 2},
                            {},
                            {},
                            {},
                        ],
                    }
                ],
            },
        }
        steps, _idx, _lbl, _mode = build_print_steps(
            "part.gcode",
            state,
            auto_feed=True,
            file_entry={"name": "part.gcode", "materialColors": "#ff0000", "material": "PLA"},
        )
        self.assertNotIn("feedInOrOut", str(steps))

    def test_external_job_skips_cfs_feed(self) -> None:
        state = {"cfsConnect": 1, "boxsInfo": {"enable": 1, "materialBoxs": [{"type": 0}]}}
        steps, _idx, label, mode = build_print_steps(
            "part.gcode",
            state,
            file_entry={"name": "part.gcode", "enableCfs": 0},
        )
        self.assertEqual(mode, "external")
        self.assertEqual(label, "Spulenhalter")
        self.assertEqual(len(steps), 1)
        self.assertIn("opGcodeFile", steps[0])
        self.assertNotIn("feedInOrOut", str(steps))


class MulticolorModeTests(unittest.TestCase):
    def test_single_color_uses_op_gcode_file(self) -> None:
        state = {
            "cfsConnect": 1,
            "boxsInfo": {
                "enable": 1,
                "boxColorInfo": [{"id": 1}],
                "materialBoxs": [{"type": 0, "id": 1, "materials": [{"vendor": "X", "name": "PLA", "type": "PLA", "color": "FF0000"}]}],
            },
        }
        steps, _i, _l, mode = build_print_steps(
            "/mnt/UDISK/printer_data/gcodes/part.gcode",
            state,
            file_entry={"name": "part.gcode", "path": "/mnt/UDISK/printer_data/gcodes/part.gcode"},
        )
        self.assertEqual(mode, "normal")
        self.assertTrue(any("opGcodeFile" in s for s in steps))
        self.assertFalse(any("multiColorPrint" in s for s in steps))


if __name__ == "__main__":
    unittest.main()
