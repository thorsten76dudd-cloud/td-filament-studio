import unittest

from creality_nfc.update_check import (
    ReleaseInfo,
    _parse_release_payload,
    _pick_release_asset,
    format_setup_downloads,
    is_newer,
)


class UpdateCheckTests(unittest.TestCase):
    def test_is_newer(self) -> None:
        self.assertTrue(is_newer("1.5.31", "1.5.30"))
        self.assertFalse(is_newer("1.5.30", "1.5.30"))
        self.assertFalse(is_newer("1.5.29", "1.5.30"))

    def test_pick_setup_exe_first(self) -> None:
        url, label, count = _pick_release_asset(
            [
                {
                    "name": "TD Filament Studio.exe",
                    "browser_download_url": "https://example.com/portable.exe",
                    "download_count": 99,
                },
                {
                    "name": "TD-Filament-Studio-Setup.exe",
                    "browser_download_url": "https://example.com/setup.exe",
                    "download_count": 12,
                },
            ]
        )
        self.assertEqual(label, "TD-Filament-Studio-Setup.exe")
        self.assertIn("setup.exe", url or "")
        self.assertEqual(count, 12)

    def test_format_downloads_zero(self) -> None:
        self.assertIn("0", format_setup_downloads(0))
        self.assertIn("verzögert", format_setup_downloads(0).lower())

    def test_parse_release_payload(self) -> None:
        info = _parse_release_payload(
            {
                "tag_name": "v1.5.31",
                "name": "TD Filament Studio 1.5.31",
                "html_url": "https://github.com/tdudd/td-filament-studio/releases/tag/v1.5.31",
                "assets": [
                    {
                        "name": "TD-Filament-Studio-Setup.exe",
                        "browser_download_url": "https://github.com/dl/setup.exe",
                        "download_count": 3,
                    }
                ],
            }
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.version, "1.5.31")
        self.assertEqual(info.download_label, "TD-Filament-Studio-Setup.exe")
        self.assertEqual(info.setup_download_count, 3)


if __name__ == "__main__":
    unittest.main()
