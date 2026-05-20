import unittest
from pathlib import Path

from app.bundled_assets import (
    CHIP_TAG_PLASTIC_HOLDER_DIR,
    CHIP_TAG_PLASTIC_STL_NAMES,
    bundled_asset_path,
    bundled_plastic_holder_stls,
)


class TestBundledAssets(unittest.TestCase):
    def test_plastic_holder_stls_exist_in_dev_tree(self) -> None:
        stls = bundled_plastic_holder_stls()
        self.assertEqual(len(stls), len(CHIP_TAG_PLASTIC_STL_NAMES))
        for path in stls:
            self.assertTrue(path.is_file(), f"missing: {path}")
            self.assertGreater(path.stat().st_size, 1000)
            self.assertEqual(path.suffix.lower(), ".stl")
        legacy = bundled_asset_path(Path("downloads") / "Chip-Tag.3mf")
        self.assertFalse(legacy.is_file(), f"old asset should be removed: {legacy}")

    def test_holder_dir_layout(self) -> None:
        for name in CHIP_TAG_PLASTIC_STL_NAMES:
            path = bundled_asset_path(CHIP_TAG_PLASTIC_HOLDER_DIR / name)
            self.assertTrue(path.is_file(), f"missing: {name}")


if __name__ == "__main__":
    unittest.main()
