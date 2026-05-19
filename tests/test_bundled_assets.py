import unittest
from pathlib import Path

from app.bundled_assets import CHIP_TAG_PLASTIC_3MF, bundled_asset_path


class TestBundledAssets(unittest.TestCase):
    def test_chip_tag_3mf_exists_in_dev_tree(self) -> None:
        path = bundled_asset_path(CHIP_TAG_PLASTIC_3MF)
        self.assertTrue(path.is_file(), f"missing: {path}")
        self.assertGreater(path.stat().st_size, 1000)
        self.assertEqual(path.suffix.lower(), ".3mf")


if __name__ == "__main__":
    unittest.main()
