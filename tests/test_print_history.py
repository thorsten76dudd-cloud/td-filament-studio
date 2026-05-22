"""Tests: Druck-Historie."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.print_history import PrintHistoryStore, PrintJobRecord


class PrintHistoryTests(unittest.TestCase):
    def test_add_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hist.json"
            store = PrintHistoryStore(path)
            store.add(
                PrintJobRecord(
                    id="a1",
                    ts="2026-01-01T12:00:00Z",
                    filename="test.gcode",
                    deducted_g=12,
                )
            )
            self.assertEqual(len(store.list_entries()), 1)
            csv_path = Path(tmp) / "out.csv"
            store.export_csv(csv_path)
            self.assertIn("test.gcode", csv_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
