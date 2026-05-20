"""Tests: Verbrauchs-Dialog nicht erneut für dieselbe G-Code-Datei."""

import unittest

from creality_nfc.app_settings import AppSettings


class PostPrintHandledTests(unittest.TestCase):
    def test_remember_and_check(self) -> None:
        s = AppSettings()
        self.assertFalse(s.is_post_print_deduct_handled("job.gcode"))
        s.remember_post_print_deduct("job.gcode")
        self.assertTrue(s.is_post_print_deduct_handled("job.gcode"))
        self.assertFalse(s.is_post_print_deduct_handled("other.gcode"))

    def test_cap_list(self) -> None:
        s = AppSettings()
        for i in range(50):
            s.remember_post_print_deduct(f"f{i}.gcode")
        self.assertLessEqual(len(s.post_print_deduct_handled), AppSettings._MAX_POST_PRINT_HANDLED)


if __name__ == "__main__":
    unittest.main()
