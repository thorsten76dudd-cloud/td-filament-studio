"""Tests: In-App-Update-Hilfen."""

import unittest
from unittest.mock import patch

from creality_nfc.app_update import default_setup_download_path, kill_all_app_processes


class AppUpdateTests(unittest.TestCase):
    def test_default_download_path(self) -> None:
        p = default_setup_download_path()
        self.assertTrue(str(p).endswith("TD-Filament-Studio-Setup.exe"))

    @patch("creality_nfc.app_update.subprocess.run")
    @patch("creality_nfc.app_update.sys.platform", "win32")
    def test_kill_calls_taskkill(self, mock_run) -> None:
        kill_all_app_processes()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("taskkill", args)
        self.assertIn("TD Filament Studio.exe", args)


if __name__ == "__main__":
    unittest.main()
