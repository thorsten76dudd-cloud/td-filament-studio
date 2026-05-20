"""Tests: K2-Neustart-Hilfsfunktionen."""

import unittest
from unittest.mock import MagicMock, patch

from creality_nfc.printer_ssh import (
    _ssh_disconnect_error,
    _ssh_try_reboot,
    reboot_printer_ws,
)


class RebootHelperTests(unittest.TestCase):
    def test_disconnect_error_tokens(self) -> None:
        self.assertTrue(_ssh_disconnect_error(TimeoutError("timed out")))
        self.assertTrue(_ssh_disconnect_error(OSError("Connection reset by peer")))
        self.assertFalse(_ssh_disconnect_error(ValueError("bad")))

    def test_ssh_try_reboot_on_exit_zero(self) -> None:
        client = MagicMock()
        stdout = MagicMock()
        stdout.channel.recv_exit_status.return_value = 0
        client.exec_command.return_value = (None, stdout, MagicMock())
        self.assertTrue(_ssh_try_reboot(client))

    @patch("creality_nfc.printer_ws.send_set_once")
    def test_reboot_ws_first_candidate(self, send_mock: MagicMock) -> None:
        send_mock.return_value = None
        self.assertEqual(reboot_printer_ws("192.168.1.50"), "WLAN:restart")


if __name__ == "__main__":
    unittest.main()
