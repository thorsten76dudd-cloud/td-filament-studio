"""Tests: Spulen-Standort-Helfer."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.spool_inventory import Spool, SpoolInventory
from creality_nfc.spool_location import spools_at_printer, spools_in_storage


class SpoolLocationTests(unittest.TestCase):
    def test_at_printer_and_storage_use_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inv = SpoolInventory(Path(tmp) / "spools.json")
            inv.spools = [
                Spool(id="1", label="A", location_printer="K2"),
                Spool(id="2", label="B"),
            ]
            at = spools_at_printer(inv, "K2")
            self.assertEqual(len(at), 1)
            self.assertEqual(at[0].label, "A")
            storage = spools_in_storage(inv)
            self.assertEqual(len(storage), 1)
            self.assertEqual(storage[0].label, "B")


if __name__ == "__main__":
    unittest.main()
