"""Kamera-Viewer-HTML: Watchdog gegen eingefrorenes Video."""

from __future__ import annotations

import unittest

from creality_nfc.k2_camera_live import _VIEWER_HTML


class CameraViewerWatchdogTests(unittest.TestCase):
    def test_html_has_watchdog_constants(self) -> None:
        self.assertIn("STALL_LIMIT_MS", _VIEWER_HTML)
        self.assertIn("RELOAD_LIMIT_MS", _VIEWER_HTML)

    def test_html_triggers_reload_on_stall(self) -> None:
        self.assertIn("hardReload", _VIEWER_HTML)
        self.assertIn("window.location.reload", _VIEWER_HTML)

    def test_html_uses_request_video_frame_callback(self) -> None:
        self.assertIn("requestVideoFrameCallback", _VIEWER_HTML)

    def test_html_handles_ice_disconnect(self) -> None:
        self.assertIn("disconnected", _VIEWER_HTML)
        self.assertIn("Recovery", _VIEWER_HTML)

    def test_html_still_shows_initial_status(self) -> None:
        self.assertIn("Verbinde mit __HOST__", _VIEWER_HTML)
        self.assertIn("WebRTC verbunden", _VIEWER_HTML)

    def test_no_unreplaced_curly_placeholders(self) -> None:
        for needle in ("{STALL", "{HOST", "{RELOAD"):
            self.assertNotIn(needle, _VIEWER_HTML)


if __name__ == "__main__":
    unittest.main()
