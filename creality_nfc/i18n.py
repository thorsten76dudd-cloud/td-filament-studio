"""Einfache Dictionary-basierte Lokalisierung.

Aufruf:
    from creality_nfc.i18n import t, set_language
    set_language("en")
    t("button.save")  # -> "Save"
    t("notify.print_done", filename="cube.gcode")
        # -> "Print finished: cube.gcode"

Fallback: Wenn der Key in der Zielsprache fehlt, wird der Wert aus `de`
zurueckgegeben (Default-Locale). Fehlt er auch dort, gibt es den Key selbst.
"""
from __future__ import annotations

from typing import Any, Dict

_DEFAULT_LANG = "de"
_SUPPORTED = ("de", "en")
_current_lang = _DEFAULT_LANG

_catalogs: Dict[str, Dict[str, str]] = {}


def _load_catalogs() -> None:
    if _catalogs:
        return
    from creality_nfc.locale import de as _de
    from creality_nfc.locale import en as _en

    _catalogs["de"] = dict(_de.STRINGS)
    _catalogs["en"] = dict(_en.STRINGS)


def supported_languages() -> tuple[str, ...]:
    return _SUPPORTED


def get_language() -> str:
    return _current_lang


def current_language() -> str:
    """Alias fuer get_language() zur Verwendung in Sprach-Switches."""

    return _current_lang


def set_language(lang: str) -> None:
    global _current_lang
    if lang not in _SUPPORTED:
        lang = _DEFAULT_LANG
    _current_lang = lang
    _load_catalogs()


def t(key: str, /, **kwargs: Any) -> str:
    """Uebersetzt einen Key. Optional Platzhalter via str.format."""
    _load_catalogs()
    cat = _catalogs.get(_current_lang) or {}
    text = cat.get(key)
    if text is None:
        text = _catalogs.get(_DEFAULT_LANG, {}).get(key)
    if text is None:
        text = key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


class LazyString:
    """Verzögerte Übersetzung — wird erst bei str() / .strip() aufgelöst."""

    __slots__ = ("_fn",)

    def __init__(self, fn) -> None:
        self._fn = fn

    def _resolve(self) -> str:
        return self._fn()

    def __str__(self) -> str:
        return self._resolve()

    def strip(self, chars: str | None = None) -> str:
        s = self._resolve()
        return s.strip(chars) if chars is not None else s.strip()

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)


def language_display(lang: str | None = None) -> str:
    """Liefert die Sprachbezeichnung in der Sprache selbst (z.B. fuer Dropdowns)."""
    code = (lang or _current_lang).lower()
    return {
        "de": "Deutsch",
        "en": "English",
    }.get(code, code)
