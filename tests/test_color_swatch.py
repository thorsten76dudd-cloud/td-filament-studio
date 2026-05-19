import unittest

from ui.color_swatch import color_from_tag_field, normalize_hex


class TestColorSwatch(unittest.TestCase):
    def test_tag_field_short_digits(self) -> None:
        self.assertEqual(color_from_tag_field("000eff0"), "00EFF0")
        self.assertEqual(color_from_tag_field("eff"), "000EFF")

    def test_normalize_three_char_css(self) -> None:
        self.assertEqual(normalize_hex("f00"), "FF0000")

    def test_tag_field_creality(self) -> None:
        self.assertEqual(color_from_tag_field("0FFFFFF"), "FFFFFF")
        self.assertEqual(len(color_from_tag_field("0000eff")), 6)


if __name__ == "__main__":
    unittest.main()
