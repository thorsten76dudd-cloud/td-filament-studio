"""Tests: Creality-Print-Wächter."""

import unittest
from unittest.mock import patch

from creality_nfc.creality_watch import (
    _any_image_running,
    _main_app_pid_alive,
    is_creality_running,
    is_main_app_running,
    register_main_app,
    unregister_main_app,
)


class CrealityWatchTests(unittest.TestCase):
    def test_tasklist_match(self) -> None:
        blob = '"crealityprint.exe","1234","Console","1","12.345 K"'
        self.assertTrue(_any_image_running(blob, ("CrealityPrint.exe",)))
        self.assertFalse(_any_image_running(blob, ("TD Filament Studio.exe",)))

    def test_main_pid_registration(self) -> None:
        unregister_main_app()
        with patch("creality_nfc.creality_watch._pid_alive", return_value=True):
            register_main_app()
            self.assertTrue(_main_app_pid_alive())
        unregister_main_app()
        self.assertFalse(_main_app_pid_alive())

    @patch("creality_nfc.creality_watch._win_creality_running_powershell", return_value=True)
    def test_creality_detected_via_powershell(self, _mock_ps) -> None:
        self.assertTrue(is_creality_running())

    @patch("creality_nfc.creality_watch._win_creality_running_powershell", return_value=None)
    @patch("creality_nfc.creality_watch._tasklist_blob", return_value='"crealityprint.exe","1"')
    def test_creality_fallback_tasklist(self, _blob, _mock_ps) -> None:
        self.assertTrue(is_creality_running())

    def test_frozen_exe_watcher_not_counted_as_gui(self) -> None:
        unregister_main_app()
        blob = '"td filament studio.exe","99","Console","1","1 K"'
        with patch("creality_nfc.creality_watch._tasklist_blob", return_value=blob):
            with patch("creality_nfc.creality_watch._main_app_pid_alive", return_value=False):
                with patch("creality_nfc.creality_watch._win_td_studio_gui_running", return_value=False):
                    with patch("creality_nfc.creality_watch.sys") as mock_sys:
                        mock_sys.platform = "win32"
                        mock_sys.frozen = True
                        self.assertFalse(is_main_app_running())


if __name__ == "__main__":
    unittest.main()
