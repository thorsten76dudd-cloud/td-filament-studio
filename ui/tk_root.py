"""Tk-Hauptfenster mit optional Drag & Drop vom Betriebssystem."""

from __future__ import annotations

import tkinter as tk

try:
    from tkinterdnd2 import TkinterDnD

    AppTk = TkinterDnD.Tk
    HAS_OS_DND = True
except ImportError:
    AppTk = tk.Tk
    HAS_OS_DND = False
