import unittest
from pathlib import Path

from ui.dnd_files import parse_dnd_file_list


class TestParseDndFileList(unittest.TestCase):
    def test_braced_path_with_spaces(self) -> None:
        data = r"{C:\Users\tdudd\Desktop\Parol 6}"
        paths = parse_dnd_file_list(data)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], Path(r"C:\Users\tdudd\Desktop\Parol 6"))

    def test_multiple_braced(self) -> None:
        data = r"{C:\a.stl} {D:\b folder\c.pdf}"
        paths = parse_dnd_file_list(data)
        self.assertEqual(len(paths), 2)
        self.assertEqual(paths[1], Path(r"D:\b folder\c.pdf"))

    def test_unbraced_single_path_with_spaces(self) -> None:
        data = r"C:\Projects\Parol 6\STL"
        paths = parse_dnd_file_list(data)
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0], Path(r"C:\Projects\Parol 6\STL"))

    def test_newline_separated(self) -> None:
        data = "C:\\a.stl\nC:\\b.stl"
        paths = parse_dnd_file_list(data)
        self.assertEqual(len(paths), 2)


if __name__ == "__main__":
    unittest.main()
