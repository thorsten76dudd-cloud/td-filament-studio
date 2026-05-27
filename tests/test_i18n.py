"""i18n / Sprache: Tests."""
from __future__ import annotations

import unittest

from creality_nfc.app_settings import AppSettings
from creality_nfc.i18n import (
    get_language,
    set_language,
    supported_languages,
    t,
)


class I18nTests(unittest.TestCase):
    def test_default_language_is_german(self) -> None:
        set_language("de")
        self.assertEqual(get_language(), "de")
        self.assertEqual(t("printer.btn.connect"), "Verbinden")

    def test_switch_to_english(self) -> None:
        set_language("en")
        self.assertEqual(get_language(), "en")
        self.assertEqual(t("printer.btn.connect"), "Connect")

    def test_invalid_lang_falls_back_to_default(self) -> None:
        set_language("xx")
        # 'xx' wird auf 'de' gemappt
        self.assertEqual(get_language(), "de")

    def test_unknown_key_returns_key(self) -> None:
        set_language("de")
        self.assertEqual(t("does.not.exist"), "does.not.exist")

    def test_missing_in_target_falls_back_to_default(self) -> None:
        # Notification-Strings sollten in beiden Sprachen vorhanden sein
        set_language("en")
        self.assertEqual(t("notify.connect_first"), "Connect to the printer first.")

    def test_format_kwargs(self) -> None:
        set_language("de")
        self.assertEqual(t("notify.print_finished", filename="cube.gcode"), "Druck beendet: cube.gcode")
        set_language("en")
        self.assertEqual(t("notify.print_finished", filename="cube.gcode"), "Print finished: cube.gcode")

    def test_supported(self) -> None:
        self.assertIn("de", supported_languages())
        self.assertIn("en", supported_languages())


class AppSettingsLanguageTests(unittest.TestCase):
    def test_default_language(self) -> None:
        s = AppSettings()
        self.assertEqual(s.language, "de")

    def test_persist_language(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "app_settings.json"
            s = AppSettings()
            s.language = "en"
            s.save(p)

            raw = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(raw.get("language"), "en")

            loaded = AppSettings.load(p)
            self.assertEqual(loaded.language, "en")


if __name__ == "__main__":
    unittest.main()
