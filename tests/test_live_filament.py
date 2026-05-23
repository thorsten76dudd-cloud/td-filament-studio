"""Tests: Live-Filament-Anzeige nach Druckende."""

import unittest
from pathlib import Path

from creality_nfc.live_filament import format_live_filament_status


class LiveFilamentTests(unittest.TestCase):
    def test_complete_job_with_display_prefix(self) -> None:
        cache = (
            Path.home()
            / "AppData/Local/Programs/TD Filament Studio/data/gcode_cache/1A.stl_PETG_6m38s.gcode"
        )
        if not cache.is_file():
            self.skipTest("installierter G-Code-Cache fehlt")
        text = format_live_filament_status(
            {},
            filename="Letzter Druck: 1A.stl_PETG_6m38s.gcode",
            progress_pct=100,
            active_slot=None,
            cfs_slots=None,
            local_gcode=cache,
        )
        self.assertIn("verbraucht", text)
        self.assertNotIn("nicht verfügbar", text)


if __name__ == "__main__":
    unittest.main()
