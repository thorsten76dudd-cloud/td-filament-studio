"""GitHub-Release-Versionsvergleich."""

import unittest

from creality_nfc.update_check import is_newer, normalize_release_version


class UpdateCheckTests(unittest.TestCase):
    def test_normalize_stable_tag(self) -> None:
        self.assertEqual(normalize_release_version("v1.5.58-stable"), "1.5.58")

    def test_is_newer_ignores_stable_suffix(self) -> None:
        self.assertTrue(is_newer("1.5.58-stable", "1.5.57"))
        self.assertFalse(is_newer("1.5.58-stable", "1.5.58"))


if __name__ == "__main__":
    unittest.main()
