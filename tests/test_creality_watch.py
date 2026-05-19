"""Tests: Creality-Print-Wächter."""

import unittest

from creality_nfc.creality_watch import _any_image_running


class CrealityWatchTests(unittest.TestCase):
    def test_tasklist_match(self) -> None:
        blob = '"crealityprint.exe","1234","Console","1","12.345 K"'
        self.assertTrue(_any_image_running(blob, ("CrealityPrint.exe",)))
        self.assertFalse(_any_image_running(blob, ("TD Filament Studio.exe",)))


if __name__ == "__main__":
    unittest.main()
