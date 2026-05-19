"""Kamera-Snapshot-Hilfen."""

import unittest

from creality_nfc.printer_camera import camera_snapshot_urls, normalize_host


class TestPrinterCamera(unittest.TestCase):
    def test_k2_urls_first(self) -> None:
        urls = camera_snapshot_urls("192.168.1.10", probe_moonraker=False)
        self.assertTrue(urls[0].startswith("http://192.168.1.10:8000/"))

    def test_normalize_host_strips_port(self) -> None:
        self.assertEqual(normalize_host("192.168.1.10:8000"), "192.168.1.10")


if __name__ == "__main__":
    unittest.main()
