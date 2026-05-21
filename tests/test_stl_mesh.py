import tempfile
import unittest
from pathlib import Path

from creality_nfc.stl_mesh import load_stl_triangles, triangle_bounds


class TestStlMesh(unittest.TestCase):
    def test_ascii_stl(self) -> None:
        stl = """solid test
  facet normal 0 0 1
    outer loop
      vertex 0 0 0
      vertex 1 0 0
      vertex 0 1 0
    endloop
  endfacet
endsolid test
"""
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False, mode="w", encoding="utf-8") as f:
            f.write(stl)
            path = Path(f.name)
        try:
            tris = load_stl_triangles(path)
            self.assertEqual(len(tris), 1)
            center, radius = triangle_bounds(tris)
            self.assertGreater(radius, 0)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
