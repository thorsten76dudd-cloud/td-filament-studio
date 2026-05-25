"""Sync-Pfad nach App-Start: leere Snaps blockieren keine Erkennung mehr."""

from __future__ import annotations

import unittest

from ui.panels.printer_device_panel import PrinterDevicePanel


class PrintSnapUsableForSyncTests(unittest.TestCase):
    def test_empty_snap_is_not_usable(self) -> None:
        self.assertFalse(
            PrinterDevicePanel._print_snap_usable_for_sync(
                phase="idle", fname="", progress=None, last_filename=""
            )
        )

    def test_idle_with_zero_progress_not_usable(self) -> None:
        self.assertFalse(
            PrinterDevicePanel._print_snap_usable_for_sync(
                phase="idle", fname="", progress=0, last_filename=""
            )
        )

    def test_filename_makes_snap_usable(self) -> None:
        self.assertTrue(
            PrinterDevicePanel._print_snap_usable_for_sync(
                phase="idle", fname="job.gcode", progress=None, last_filename=""
            )
        )

    def test_remembered_filename_makes_snap_usable(self) -> None:
        self.assertTrue(
            PrinterDevicePanel._print_snap_usable_for_sync(
                phase="idle", fname="", progress=None, last_filename="job.gcode"
            )
        )

    def test_phase_complete_makes_snap_usable(self) -> None:
        self.assertTrue(
            PrinterDevicePanel._print_snap_usable_for_sync(
                phase="complete", fname="", progress=None, last_filename=""
            )
        )

    def test_progress_above_zero_is_usable(self) -> None:
        self.assertTrue(
            PrinterDevicePanel._print_snap_usable_for_sync(
                phase="idle", fname="", progress=42, last_filename=""
            )
        )


if __name__ == "__main__":
    unittest.main()
