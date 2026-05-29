"""Tests: In-App-Update-Hilfen."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creality_nfc.app_update import (
    _SETUP_NAME,
    default_setup_download_path,
    install_downloaded_setup,
    kill_all_app_processes,
    stage_setup_for_install,
    unblock_setup_file,
    validate_setup_exe,
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
    def test_kill_calls_taskkill_without_tree(self, mock_run) -> None:
        kill_all_app_processes()
        self.assertGreaterEqual(mock_run.call_count, 1)
        args = mock_run.call_args_list[0][0][0]
        self.assertIn("taskkill", args)
        self.assertIn("TD Filament Studio.exe", args)
        self.assertNotIn("/T", args)

    def test_default_download_under_localappdata(self) -> None:
        p = default_setup_download_path()
        self.assertIn("TD Filament Studio", str(p))
        self.assertIn("Updates", str(p))

    @patch("creality_nfc.app_update.os._exit")
    @patch("creality_nfc.app_update.kill_all_app_processes")
    @patch("creality_nfc.app_update._shell_execute")
    @patch("creality_nfc.app_update.unblock_setup_file")
    @patch("creality_nfc.app_update.sys.platform", "win32")
    def test_install_launches_and_exits(
        self, _mock_unblock, mock_shell, _mock_kill, mock_exit
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "TD-Filament-Studio-Setup.exe"
            setup.write_bytes(b"MZ" + b"\0" * 5_000_001)
            with patch(
                "creality_nfc.app_update.default_setup_download_path",
                return_value=setup,
            ):
                install_downloaded_setup(setup)
            mock_shell.assert_called_once()
            mock_exit.assert_called_once_with(0)

    @patch("creality_nfc.app_update.sys.platform", "win32")
    @patch("creality_nfc.app_update.ctypes.windll")
    def test_unblock_deletes_zone_identifier(self, mock_windll) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "TD-Filament-Studio-Setup.exe"
            setup.write_bytes(b"MZ")
            mock_windll.kernel32.DeleteFileW.return_value = 1
            unblock_setup_file(setup)
            mock_windll.kernel32.DeleteFileW.assert_called_once()

    def test_stage_setup_copies_to_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.exe"
            src.write_bytes(b"MZ" + b"\0" * 5_000_001)
            dest_path = Path(tmp) / "Updates" / _SETUP_NAME
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with patch(
                "creality_nfc.app_update.default_setup_download_path",
                return_value=dest_path,
            ):
                dest = stage_setup_for_install(src)
                self.assertTrue(dest.is_file())
                self.assertGreater(dest.stat().st_size, 5_000_000)


if __name__ == "__main__":
    unittest.main()
