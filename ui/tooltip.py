"""Kurze Hover-Erklärungen für tk/ttk-Widgets."""

from __future__ import annotations

import tkinter as tk

from ui.theme import BORDER_STRONG, CONFIRM_BG, F_SMALL, ON_HEADER

DEFAULT_DELAY_MS = 450


class ToolTip:
    def __init__(self, widget: tk.Misc, text: str, *, delay_ms: int = DEFAULT_DELAY_MS) -> None:
        self.widget = widget
        self.text = text.strip()
        self.delay_ms = delay_ms
        self._tw: tk.Toplevel | None = None
        self._after_id: str | None = None
        if self.text:
            widget.bind("<Enter>", self._schedule, add="+")
            widget.bind("<Leave>", self._hide, add="+")

    def set_text(self, text: str) -> None:
        self.text = text.strip()

    def _schedule(self, _event=None) -> None:
        self._hide()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _show(self) -> None:
        self._after_id = None
        if self._tw or not self.text:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._tw = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(
            tw,
            text=self.text,
            justify="left",
            background=CONFIRM_BG,
            foreground=ON_HEADER,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER_STRONG,
            font=F_SMALL,
            padx=10,
            pady=7,
            wraplength=380,
        ).pack()
        tw.update_idletasks()
        sw = tw.winfo_screenwidth()
        if x + tw.winfo_width() > sw - 10:
            x = max(10, sw - tw.winfo_width() - 10)
        tw.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        if self._tw:
            self._tw.destroy()
            self._tw = None


def tip(widget: tk.Misc, text: str, *, delay_ms: int = DEFAULT_DELAY_MS) -> tk.Misc:
    """Tooltip an Widget hängen; gibt das Widget zurück."""
    ToolTip(widget, text, delay_ms=delay_ms)
    return widget
