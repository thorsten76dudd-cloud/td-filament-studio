import unittest

from creality_nfc.update_check import (
    ReleaseInfo,
    _parse_release_payload,
    _pick_release_asset,
    is_newer,
)


class UpdateCheckTests(unittest.TestCase):
    def test_is_newer(self) -> None:
        self.assertTrue(is_newer("1.5.31", "1.5.30"))
        self.assertFalse(is_newer("1.5.30", "1.5.30"))
        self.assertFalse(is_newer("1.5.29", "1.5.30"))

    def test_pick_setup_exe_first(self) -> None:
        url, label = _pick_release_asset(
            [
                {
                    "name": "TD Filament Studio.exe",
                    "browser_download_url": "https://example.com/portable.exe",
                },
                {
                    "name": "TD-Filament-Studio-Setup.exe",
                    "browser_download_url": "https://example.com/setup.exe",
                },
            ]
        )
        self.assertEqual(label, "TD-Filament-Studio-Setup.exe")
        self.assertIn("setup.exe", url or "")

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
                    }
                ],
            }
        )
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.version, "1.5.31")
        self.assertEqual(info.download_label, "TD-Filament-Studio-Setup.exe")


if __name__ == "__main__":
    unittest.main()
