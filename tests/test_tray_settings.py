"""Tray-Hintergrund: Einstellungen persistieren."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creality_nfc.app_settings import AppSettings


class TraySettingsTests(unittest.TestCase):
    def test_default_off(self) -> None:
        s = AppSettings()
        self.assertFalse(s.tray_run_in_background)

    def test_save_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app_settings.json"
            s = AppSettings(tray_run_in_background=True)
            s.save(path)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(raw["tray_run_in_background"])
            loaded = AppSettings.load(path)
            self.assertTrue(loaded.tray_run_in_background)


if __name__ == "__main__":
    unittest.main()
