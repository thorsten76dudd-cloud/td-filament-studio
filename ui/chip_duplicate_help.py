"""Texte für den Assistenten „Chip duplizieren"."""

from creality_nfc.i18n import LazyString, t as _t


def _chip_dup_tooltip() -> str:
    return _t("chip_dup.tooltip")


def _chip_dup_intro() -> str:
    return _t("chip_dup.intro")


def _chip_dup_step_hints() -> dict[str, str]:
    return {
        "source": _t("chip_dup.step.source"),
        "target": _t("chip_dup.step.target"),
    }


class _LazyDict:
    def __init__(self, fn):
        self._fn = fn

    def get(self, key, default=""):
        return self._fn().get(key, default)

    def __getitem__(self, key):
        return self._fn()[key]


CHIP_DUP_TOOLTIP = LazyString(_chip_dup_tooltip)
CHIP_DUP_INTRO = LazyString(_chip_dup_intro)
CHIP_DUP_STEP_HINTS = _LazyDict(_chip_dup_step_hints)
