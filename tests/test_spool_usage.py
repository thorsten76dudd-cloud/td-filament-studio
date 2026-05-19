"""Tests: Restgewicht & Verbrauch."""

import unittest

from creality_nfc.spool_inventory import Spool
from creality_nfc.spool_usage import deduct_grams, is_low_filament, weight_class_to_grams


class SpoolUsageTests(unittest.TestCase):
    def test_weight_class_to_grams(self) -> None:
        self.assertEqual(weight_class_to_grams("1 KG"), 1000)
        self.assertEqual(weight_class_to_grams("750 G"), 750)

    def test_deduct_and_low_warning(self) -> None:
        sp = Spool(id="a", label="PLA", remaining_g=300, weight="1 KG")
        deduct_grams(sp, 100, note="test")
        self.assertEqual(sp.remaining_g, 200)
        self.assertEqual(len(sp.usage_log), 1)
        self.assertTrue(is_low_filament(sp, 250))
        self.assertFalse(is_low_filament(sp, 100))


if __name__ == "__main__":
    unittest.main()
