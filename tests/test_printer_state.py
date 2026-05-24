"""Tests: Druck-Phase erkennen."""

import unittest

from creality_nfc.printer_state import (
    build_print_phase_notification,
    payload_has_meaningful_refresh,
    payload_has_print_refresh,
    print_job_phase,
    should_notify_print_phase_change,
    temp_target_spinbox_value,
)


class MeaningfulRefreshTests(unittest.TestCase):
    def test_cfs_only_heartbeat_not_meaningful(self) -> None:
        self.assertFalse(
            payload_has_meaningful_refresh({"cfsConnect": 1, "boxsInfo": {"enable": 1}})
        )

    def test_print_progress_is_meaningful(self) -> None:
        self.assertTrue(
            payload_has_meaningful_refresh(
                {"printProgress": 42, "printFileName": "x.gcode"}
            )
        )

    def test_temp_alone_not_print_refresh(self) -> None:
        self.assertFalse(payload_has_print_refresh({"nozzleTemp": 210}))
        self.assertTrue(payload_has_print_refresh({"printProgress": 10}))


class PrintJobPhaseTests(unittest.TestCase):
    def test_print_state_signature_changes_with_progress(self) -> None:
        from creality_nfc.printer_state import print_state_signature

        a = print_state_signature({"state": 1, "printProgress": 98, "printFileName": "x.gcode"})
        b = print_state_signature({"state": 2, "printProgress": 100, "printFileName": "x.gcode"})
        self.assertNotEqual(a, b)
        c = print_state_signature({"state": 1, "printProgress": 98, "printFileName": "x.gcode"})
        self.assertEqual(a, c)

    def test_print_state_signature_ignores_left_time(self) -> None:
        from creality_nfc.printer_state import print_state_signature

        base = {
            "state": 1,
            "printProgress": 74,
            "printFileName": "x.gcode",
            "curLayer": 103,
            "totalLayer": 147,
        }
        a = print_state_signature({**base, "printTimeLeft": 420})
        b = print_state_signature({**base, "printTimeLeft": 380})
        self.assertEqual(a, b)

    def test_stale_100_percent_with_time_left_is_printing(self) -> None:
        """Neuer Druck: Fortschritt noch 100 % vom alten Job, aber Restzeit > 0."""
        phase = print_job_phase(
            {
                "state": 0,
                "printProgress": 100,
                "printFileName": "test.gcode",
                "printTimeLeft": 240,
            }
        )
        self.assertEqual(phase, "printing")

    def test_state_1_is_printing_even_at_100(self) -> None:
        phase = print_job_phase(
            {"state": 1, "printProgress": 100, "printFileName": "x.gcode"}
        )
        self.assertEqual(phase, "printing")

    def test_complete_when_done(self) -> None:
        phase = print_job_phase(
            {
                "state": 2,
                "printProgress": 100,
                "printFileName": "x.gcode",
                "printTimeLeft": 0,
            }
        )
        self.assertEqual(phase, "complete")


class PrintPhaseAlertTests(unittest.TestCase):
    def test_notify_printing_to_paused(self) -> None:
        self.assertTrue(
            should_notify_print_phase_change(
                "printing", "paused", has_job=True, synced=True
            )
        )

    def test_no_notify_without_sync(self) -> None:
        self.assertFalse(
            should_notify_print_phase_change(
                "printing", "paused", has_job=True, synced=False
            )
        )

    def test_no_notify_idle_without_job(self) -> None:
        self.assertFalse(
            should_notify_print_phase_change(
                "idle", "paused", has_job=False, synced=True
            )
        )

    def test_build_paused_message(self) -> None:
        note = build_print_phase_notification(
            {"state": 5, "aiPausePrint": 0},
            "paused",
            filename="teil.gcode",
            progress=42,
        )
        self.assertIsNotNone(note)
        assert note is not None
        self.assertIn("teil.gcode", note["detail"])
        self.assertEqual(note["level"], "warn")


class TempTargetSpinboxTests(unittest.TestCase):
    def test_idle_zero_does_not_clear_user_value(self) -> None:
        self.assertIsNone(temp_target_spinbox_value(210, 0, locked=False))

    def test_heating_target_updates_spinbox(self) -> None:
        self.assertEqual(temp_target_spinbox_value(0, 210, locked=False), 210)

    def test_lock_blocks_overwrite(self) -> None:
        self.assertIsNone(temp_target_spinbox_value(200, 180, locked=True))

    def test_job_active_blocks_zero_clear(self) -> None:
        self.assertIsNone(
            temp_target_spinbox_value(60, 0, locked=False, job_active=True)
        )


if __name__ == "__main__":
    unittest.main()
