"""Tests: CFS-Batch-Dialog Hilfslogik."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.cfs_adopt import parse_cfs_slots
from creality_nfc.cfs_spool_link import find_spool_for_slot
from creality_nfc.spool_inventory import Spool, SpoolInventory


class CfsBatchDialogTests(unittest.TestCase):
    def test_find_spool_accepts_slot_object_not_int(self) -> None:
        state = {
            "boxsInfo": {
                "materialBoxs": [
                    {
                        "type": 0,
                        "materials": [
                            {"vendor": "X", "name": "PETG", "type": "PETG", "color": "1E90FF"},
                        ],
                    }
                ],
            },
        }
        slot = parse_cfs_slots(state)[0]
        self.assertFalse(slot.empty)
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "s.json")
            inv.add(
                Spool(
                    id="s1",
                    label="Blau",
                    cfs_slot=0,
                    filament_id="12345",
                )
            )
            sp = find_spool_for_slot(inv, slot)
            self.assertIsNotNone(sp)
            self.assertEqual(sp.label, "Blau")
        with self.assertRaises(AttributeError):
            find_spool_for_slot(inv, 1)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
