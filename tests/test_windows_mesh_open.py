"""Tests: STL/3MF in Windows-Viewer öffnen."""

import unittest
from pathlib import Path
from unittest.mock import patch

from creality_nfc.windows_mesh_open import open_mesh_choose_viewer


class WindowsMeshOpenTests(unittest.TestCase):
    def test_missing_file(self) -> None:
        ok, msg, mode = open_mesh_choose_viewer(Path("/nonexistent/file.stl"))
        self.assertFalse(ok)
        self.assertEqual(mode, "error")
        self.assertIn("nicht gefunden", msg)

    @patch("creality_nfc.windows_mesh_open._find_viewer_exe", return_value=None)
    @patch("creality_nfc.windows_mesh_open._shell_invoke_openas", return_value=True)
    @patch("creality_nfc.windows_mesh_open.sys.platform", "win32")
    def test_openas_via_shell(self, _mock_shell, _mock_viewer) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as tmp:
            tmp.write(b"solid\nendsolid\n")
            path = Path(tmp.name)
        try:
            ok, msg, mode = open_mesh_choose_viewer(path)
            self.assertTrue(ok)
            self.assertEqual(mode, "openas")
            self.assertIn("Öffnen mit", msg)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
