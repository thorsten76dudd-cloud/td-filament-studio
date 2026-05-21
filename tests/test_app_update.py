"""Tests: In-App-Update-Hilfen."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creality_nfc.app_update import (
    default_setup_download_path,
    kill_all_app_processes,
    validate_setup_exe,
    _schedule_windows_installer,
)


class AppUpdateTests(unittest.TestCase):
    def test_default_download_path(self) -> None:
        p = default_setup_download_path()
        self.assertTrue(str(p).endswith("TD-Filament-Studio-Setup.exe"))

    def test_validate_rejects_tiny_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "TD-Filament-Studio-Setup.exe"
            bad.write_bytes(b"MZ" + b"\0" * 100)
            with self.assertRaises(ValueError):
                validate_setup_exe(bad)

    @patch("creality_nfc.app_update.subprocess.run")
    @patch("creality_nfc.app_update.sys.platform", "win32")
    def test_kill_calls_taskkill(self, mock_run) -> None:
        kill_all_app_processes()
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("taskkill", args)
        self.assertIn("TD Filament Studio.exe", args)

    @patch("creality_nfc.app_update.subprocess.Popen")
    @patch("creality_nfc.app_update.sys.platform", "win32")
    def test_schedule_installer_uses_cmd_script(self, mock_popen) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "TD-Filament-Studio-Setup.exe"
            setup.write_bytes(b"MZ" + b"\0" * 5_000_001)
            _schedule_windows_installer(setup)
            cmd_script = setup.parent / "_td_install_update.cmd"
            self.assertTrue(cmd_script.is_file())
            self.assertIn(str(setup), cmd_script.read_text(encoding="utf-8"))
            mock_popen.assert_called_once()
            popen_args = mock_popen.call_args[0][0]
            self.assertEqual(popen_args[0], "cmd.exe")


if __name__ == "__main__":
    unittest.main()
