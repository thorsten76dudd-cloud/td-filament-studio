import struct
import unittest
from pathlib import Path

from app.paths import app_dir
from ui.app_icon import _asset_path


class AppIconTests(unittest.TestCase):
    def test_icon_files_exist(self) -> None:
        ico = _asset_path(Path("icons") / "app_icon.ico")
        logo = _asset_path(Path("icons") / "app_logo_48.png")
        self.assertTrue(ico.is_file(), f"missing: {ico}")
        self.assertTrue(logo.is_file(), f"missing: {logo}")
        self.assertGreater(ico.stat().st_size, 5000)
        self.assertGreater(logo.stat().st_size, 500)
        data = ico.read_bytes()
        count = struct.unpack_from("<H", data, 4)[0]
        self.assertGreaterEqual(count, 5, "ICO braucht mehrere Größen für Windows-Verknüpfungen")
        self.assertEqual(app_dir().name, app_dir().resolve().name)


if __name__ == "__main__":
    unittest.main()
