"""Tests: Druck-Check."""

import unittest

from creality_nfc.print_readiness import check_print_readiness
from creality_nfc.spool_inventory import Spool, SpoolInventory
from pathlib import Path
import tempfile


class PrintReadinessTests(unittest.TestCase):
    def test_low_rest_error(self) -> None:
        state = {
            "boxsInfo": {
                "materialBoxs": [
                    {
                        "type": 0,
                        "id": 1,
                        "materials": [
                            {
                                "vendor": "X",
                                "name": "PLA",
                                "type": "PLA",
                                "color": "FF0000",
                                "slot": 0,
                            },
                        ],
                    }
                ],
            },
            "retGcodeFileInfo2": {
                "name": "test.gcode",
                "filamentWeight": "400",
                "materialColors": "#FF0000",
                "material": "PLA",
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "s.json")
            inv.add(
                Spool(
                    id="s1",
                    label="Rot",
                    cfs_slot=0,
                    remaining_g=50,
                    color_hex="FF0000",
                )
            )
            report = check_print_readiness(
                state,
                "test.gcode",
                inv,
                low_threshold_g=200,
            )
            self.assertFalse(report.ready)
            self.assertTrue(any(ln.level == "error" for ln in report.lines))


if __name__ == "__main__":
    unittest.main()
