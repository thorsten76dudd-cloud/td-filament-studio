"""Tests: In-App-Update-Hilfen."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from creality_nfc.app_update import (
    confirm_install_ok,
    default_setup_download_path,
    install_downloaded_setup,
    kill_all_app_processes,
    purge_old_setup_downloads,
    setup_download_path_for_version,
    stage_setup_for_install,
    unblock_setup_file,
    validate_setup_exe,
    write_install_now_helper,
)


class AppUpdateTests(unittest.TestCase):
    def test_default_download_path_legacy(self) -> None:
        p = default_setup_download_path()
        self.assertTrue(str(p).endswith("TD-Filament-Studio-Setup.exe"))

    def test_versioned_download_path(self) -> None:
        p = setup_download_path_for_version("1.5.143")
        self.assertTrue(str(p).endswith("TD-Filament-Studio-Setup-1.5.143.exe"))

    def test_validate_rejects_tiny_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "TD-Filament-Studio-Setup.exe"
            bad.write_bytes(b"MZ" + b"\0" * 100)
            with self.assertRaises(ValueError):
                validate_setup_exe(bad)

    @patch("creality_nfc.app_update.read_setup_product_version", return_value="1.5.141")
    def test_validate_rejects_wrong_version(self, _mock_pe: object) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "setup.exe"
            exe.write_bytes(b"MZ" + b"\0" * 5_000_001)
            with self.assertRaises(ValueError) as ctx:
                validate_setup_exe(exe, expected_version="1.5.143")
            self.assertIn("1.5.141", str(ctx.exception))

    @patch("creality_nfc.app_update.subprocess.run")
    @patch("creality_nfc.app_update.sys.platform", "win32")
    def test_kill_calls_taskkill_without_tree(self, mock_run: object) -> None:
        kill_all_app_processes()
        self.assertGreaterEqual(mock_run.call_count, 1)
        args = mock_run.call_args_list[0][0][0]
        self.assertIn("taskkill", args)
        self.assertIn("TD Filament Studio.exe", args)
        self.assertNotIn("/T", args)

    @patch("creality_nfc.app_update.sys.platform", "win32")
    @patch("creality_nfc.app_update.ctypes.windll")
    def test_confirm_install_ok(self, mock_windll: object) -> None:
        mock_windll.user32.MessageBoxW.return_value = 1
        self.assertTrue(confirm_install_ok("T", "Body"))
        mock_windll.user32.MessageBoxW.assert_called_once()

    def test_write_install_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "TD-Filament-Studio-Setup-1.5.143.exe"
            setup.write_bytes(b"MZ" + b"\0" * 5_000_001)
            bat = write_install_now_helper(setup)
            self.assertTrue(bat.is_file())
            self.assertIn("FORCECLOSEAPPLICATIONS", bat.read_text(encoding="utf-8"))

    def test_default_download_under_localappdata(self) -> None:
        p = default_setup_download_path("1.5.143")
        self.assertIn("TD Filament Studio", str(p))
        self.assertIn("Updates", str(p))

    def test_purge_old_setups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            old = folder / "TD-Filament-Studio-Setup.exe"
            keep = folder / "TD-Filament-Studio-Setup-1.5.143.exe"
            old.write_bytes(b"x")
            keep.write_bytes(b"y")
            with patch("creality_nfc.app_update.updates_folder", return_value=folder):
                purge_old_setup_downloads(keep=keep)
            self.assertFalse(old.is_file())
            self.assertTrue(keep.is_file())

    @patch("creality_nfc.app_update.os._exit")
    @patch("creality_nfc.app_update._launch_installer_after_exit")
    @patch("creality_nfc.app_update._popen_installer_detached")
    @patch("creality_nfc.app_update._launch_installer")
    @patch("creality_nfc.app_update.unblock_setup_file")
    @patch("creality_nfc.app_update.sys.platform", "win32")
    def test_install_single_launch(
        self,
        _mock_unblock: object,
        mock_launch: object,
        mock_popen: object,
        mock_deferred: object,
        mock_exit: object,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "TD-Filament-Studio-Setup-1.5.143.exe"
            setup.write_bytes(b"MZ" + b"\0" * 5_000_001)
            with patch(
                "creality_nfc.app_update.read_setup_product_version",
                return_value="1.5.143",
            ):
                install_downloaded_setup(setup, expected_version="1.5.143")
            mock_launch.assert_called_once()
            mock_popen.assert_not_called()
            mock_deferred.assert_not_called()
            mock_exit.assert_called_once_with(0)

    @patch("creality_nfc.app_update.sys.platform", "win32")
    @patch("creality_nfc.app_update.ctypes.windll")
    def test_unblock_deletes_zone_identifier(self, mock_windll: object) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setup = Path(tmp) / "TD-Filament-Studio-Setup.exe"
            setup.write_bytes(b"MZ")
            mock_windll.kernel32.DeleteFileW.return_value = 1
            unblock_setup_file(setup)
            mock_windll.kernel32.DeleteFileW.assert_called_once()

    def test_stage_returns_same_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "TD-Filament-Studio-Setup-1.5.143.exe"
            src.write_bytes(b"MZ" + b"\0" * 5_000_001)
            dest = stage_setup_for_install(src)
            self.assertEqual(dest.resolve(), src.resolve())


if __name__ == "__main__":
    unittest.main()
