"""Tests: Fenster-Geometrie speichern."""

import tempfile
import unittest
from pathlib import Path

from creality_nfc.app_settings import AppSettings
from ui.window_geometry import (
    clamp_geometry,
    clear_table_dialog_geometries,
    format_geometry,
    parse_geometry,
    repair_stored_window_geometries,
)


class WindowGeometryTests(unittest.TestCase):
    def test_parse_and_format(self) -> None:
        self.assertEqual(parse_geometry("920x380+40+60"), (920, 380, 40, 60))
        self.assertEqual(format_geometry(920, 380, 40, 60), "920x380+40+60")

    def test_clamp(self) -> None:
        out = clamp_geometry("4000x3000+9999+9999", screen_w=1920, screen_h=1080)
        p = parse_geometry(out)
        self.assertIsNotNone(p)
        w, h, x, y = p  # type: ignore[misc]
        self.assertLessEqual(w, 1920 - 48)
        self.assertLessEqual(h, 1080 - 48)
        self.assertLessEqual(x or 0, 1920)
        self.assertLessEqual(y or 0, 1080)

    def test_clamp_wide_dialog_off_screen(self) -> None:
        out = clamp_geometry("1514x420+920+510", screen_w=1920, screen_h=1080)
        p = parse_geometry(out)
        self.assertIsNotNone(p)
        w, h, x, y = p  # type: ignore[misc]
        self.assertLessEqual(w, 1920 - 48)
        self.assertLessEqual((x or 0) + w, 1920)

    def test_repair_stored_geometries(self) -> None:
        store = {"print_history": "1514x420+920+510"}
        self.assertTrue(
            repair_stored_window_geometries(store, screen_w=1920, screen_h=1080)
        )
        p = parse_geometry(store["print_history"])
        self.assertIsNotNone(p)
        w, h, x, y = p  # type: ignore[misc]
        self.assertLessEqual(w, 920)
        self.assertLessEqual((x or 0) + w, 1920)

    def test_clear_table_dialog_geometries(self) -> None:
        store = {"print_history": "900x500", "spool_location": "800x520", "main": "1280x800"}
        self.assertTrue(clear_table_dialog_geometries(store))
        self.assertNotIn("print_history", store)
        self.assertNotIn("spool_location", store)
        self.assertIn("main", store)

    def test_settings_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app_settings.json"
            s = AppSettings()
            s.window_geometry["cfs_all_slots"] = "900x400+10+20"
            s.main_window_maximized = True
            s.save(path)
            loaded = AppSettings.load(path)
            self.assertEqual(loaded.window_geometry["cfs_all_slots"], "900x400+10+20")
            self.assertTrue(loaded.main_window_maximized)
