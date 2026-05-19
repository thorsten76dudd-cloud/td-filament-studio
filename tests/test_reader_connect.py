import unittest

from creality_nfc.reader import is_no_tag_on_reader_error


class TestReaderConnectErrors(unittest.TestCase):
    def test_detects_windows_removed_card(self) -> None:
        exc = Exception(
            "Unable to connect: Es ist keine weitere Kommunikation möglich, "
            "da die Smartcard entfernt wurde. (0x80100069)"
        )
        self.assertTrue(is_no_tag_on_reader_error(exc))

    def test_ignores_other_errors(self) -> None:
        self.assertFalse(is_no_tag_on_reader_error(Exception("Kein NFC-Reader gefunden")))


if __name__ == "__main__":
    unittest.main()
