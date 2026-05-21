import tempfile
import unittest
import zipfile
from pathlib import Path

from creality_nfc.data_backup import backup_model_library, restore_model_library
from creality_nfc.model_library import ModelLibrary


class TestModelLibraryBackup(unittest.TestCase):
    def test_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "lib"
            lib = ModelLibrary(root)
            lib.add_folder("Test", "root")
            zip_path = Path(tmp) / "backup.zip"
            n = backup_model_library(root, zip_path)
            self.assertGreaterEqual(n, 1)
            self.assertTrue(zipfile.is_zipfile(zip_path))

            root2 = Path(tmp) / "lib2"
            ModelLibrary(root2)
            restored = restore_model_library(zip_path, root2)
            self.assertGreaterEqual(restored, 1)
            lib2 = ModelLibrary(root2)
            names = [f.name for f in lib2.child_folders("root")]
            self.assertIn("Test", names)


if __name__ == "__main__":
    unittest.main()
