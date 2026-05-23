"""Tests: Druck-Historie."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.print_history import (
    PrintHistoryStore,
    PrintJobRecord,
    normalize_history_note,
    repair_history_entry,
)


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

    def test_update_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hist.json"
            store = PrintHistoryStore(path)
            store.add(
                PrintJobRecord(
                    id="a1",
                    ts="2026-01-01T12:00:00Z",
                    filename="test.gcode",
                    note="Druck beendet (kein Abzug)",
                )
            )
            rec = store.get("a1")
            assert rec is not None
            self.assertTrue(
                store.update_record(rec, deducted_g=42, note="Nachträglich abgezogen")
            )
            e = store.get("a1")
            assert e is not None
            self.assertEqual(e.deducted_g, 42)
            self.assertEqual(e.note, "Nachträglich abgezogen")

    def test_update_record_by_filename_ts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hist.json"
            store = PrintHistoryStore(path)
            rec = PrintJobRecord(
                id="",
                ts="2026-01-01T12:00:00Z",
                filename="part.gcode",
            )
            store.add(rec)
            loaded = store.list_entries()[0]
            snap = PrintJobRecord(
                id="wrong",
                ts=loaded.ts,
                filename=loaded.filename,
            )
            self.assertTrue(store.update_record(snap, deducted_g=15))
            self.assertEqual(store.list_entries()[0].deducted_g, 15)

    def test_repair_contradictory_note(self) -> None:
        rec = PrintJobRecord(
            id="x",
            ts="2026-01-01T12:00:00Z",
            filename="a.gcode",
            deducted_g=46,
            note="Druck beendet (kein Abzug)",
        )
        self.assertTrue(repair_history_entry(rec))
        self.assertEqual(rec.note, "Abzug bestätigt")
        self.assertEqual(
            normalize_history_note(rec),
            "Abzug bestätigt",
        )

    def test_display_estimate_when_no_deduct(self) -> None:
        rec = PrintJobRecord(
            id="y",
            ts="2026-01-01T12:00:00Z",
            filename="b.gcode",
            estimated_total_g=46,
            note="Druck beendet (kein Abzug)",
        )
        self.assertEqual(normalize_history_note(rec), "Druck beendet (kein Abzug)")


if __name__ == "__main__":
    unittest.main()
