"""Tests: wann nach Druckende der Filament-Abzug ausgelöst wird."""

import unittest

from ui.panels.printer_device_panel import PrinterDevicePanel


class PostPrintTriggerTests(unittest.TestCase):
  def test_late_connect_complete(self) -> None:
    self.assertTrue(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "idle",
        "complete",
        progress=100,
        last_progress=0,
        filename="job.gcode",
        last_filename="",
      )
    )

  def test_printing_to_complete(self) -> None:
    self.assertTrue(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "printing",
        "complete",
        progress=100,
        last_progress=80,
        filename="job.gcode",
        last_filename="job.gcode",
      )
    )

  def test_stays_complete_no_repeat(self) -> None:
    self.assertFalse(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "complete",
        "complete",
        progress=100,
        last_progress=100,
        filename="job.gcode",
        last_filename="job.gcode",
      )
    )

  def test_printing_to_idle_at_100(self) -> None:
    self.assertTrue(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "printing",
        "idle",
        progress=None,
        last_progress=100,
        filename="",
        last_filename="job.gcode",
      )
    )

  def test_printing_to_idle_progress_reset_peak(self) -> None:
    """Firmware setzt Fortschritt auf 0 — Peak während des Drucks zählt."""
    self.assertTrue(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "printing",
        "idle",
        progress=0,
        last_progress=80,
        peak_progress=100,
        filename="job.gcode",
        last_filename="job.gcode",
      )
    )

  def test_printing_to_idle_at_99(self) -> None:
    self.assertTrue(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "printing",
        "idle",
        progress=99,
        last_progress=99,
        filename="job.gcode",
        last_filename="job.gcode",
      )
    )

  def test_late_connect_idle_layers_done(self) -> None:
    state = {"curLayer": 120, "totalLayer": 120, "state": 0}
    ps = {"file": "job.gcode", "progress": 0}
    self.assertTrue(
      PrinterDevicePanel.printer_job_looks_finished(state, ps, "idle")
    )

  def test_late_connect_complete_phase(self) -> None:
    self.assertTrue(
      PrinterDevicePanel.printer_job_looks_finished({}, {"file": "x.gcode"}, "complete")
    )

  def test_idle_no_file_not_finished(self) -> None:
    self.assertFalse(
      PrinterDevicePanel.printer_job_looks_finished({}, {"file": ""}, "idle")
    )

  def test_printing_stuck_at_zero_triggers_deduct(self) -> None:
    self.assertTrue(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "printing",
        "printing",
        progress=0,
        last_progress=74,
        peak_progress=74,
        filename="job.gcode",
        last_filename="job.gcode",
      )
    )

  def test_printing_stuck_not_at_job_start(self) -> None:
    self.assertFalse(
      PrinterDevicePanel.should_trigger_post_print_deduct(
        "printing",
        "printing",
        progress=0,
        last_progress=0,
        peak_progress=0,
        filename="job.gcode",
        last_filename="job.gcode",
      )
    )

  def test_printing_stuck_finished_heuristic(self) -> None:
    state = {"state": 1, "printProgress": 0, "printFileName": "job.gcode"}
    ps = {"file": "job.gcode", "progress": 0}
    self.assertTrue(
      PrinterDevicePanel.printer_job_looks_finished(
        state, ps, "printing", peak_progress=74, last_progress=74
      )
    )


if __name__ == "__main__":
  unittest.main()
