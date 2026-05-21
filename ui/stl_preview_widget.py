"""STL-Vorschau: Three.js in eingebettetem Edge (Qualität wie 3D-Viewer)."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from creality_nfc.stl_preview_server import StlPreviewServer

from ui.theme import BG_SUBTLE, MUTED, TEXT

try:
    from creality_nfc.stl_preview_embed import EmbeddedStlPreview
except ImportError:
    EmbeddedStlPreview = None  # type: ignore[misc, assignment]


class StlPreviewWidget(ttk.Frame):
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._path: Path | None = None
        self._external_cb = None
        self._embed: EmbeddedStlPreview | None = None
        self._server_url: str | None = None
        self._embed_ok = False

        hdr = ttk.Frame(self)
        hdr.pack(fill="x")
        ttk.Label(hdr, text="3D-Vorschau", style="Muted.TLabel").pack(side="left")
        self._hint_lbl = ttk.Label(hdr, text="", style="Muted.TLabel")
        self._hint_lbl.pack(side="right")

        self._host = tk.Frame(self, bg=BG_SUBTLE, height=280)
        self._host.pack(fill="both", expand=True, pady=(4, 0))
        self._host.pack_propagate(False)

        self._placeholder = tk.Label(
            self._host,
            text="STL wählen — Vorschau lädt hier.\n\n"
            "Drehen/Zoomen mit Maus (wie 3D-Viewer).\n"
            "Einmalig Internet für Three.js nötig.",
            bg=BG_SUBTLE,
            fg=MUTED,
            justify="center",
            wraplength=280,
        )
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Neu laden", command=self._reload, style="Secondary.TButton").pack(side="left")
        ttk.Button(
            btns,
            text="Windows 3D Viewer",
            command=self._open_external,
            style="Secondary.TButton",
        ).pack(side="right")

        self._host.bind("<Configure>", lambda _e: self._resize_embed())

    def set_external_handler(self, callback) -> None:
        self._external_cb = callback

    def _ensure_server(self) -> str | None:
        try:
            if not self._server_url:
                self._server_url = StlPreviewServer().start()
            return self._server_url
        except OSError:
            return None

    def _start_embed(self) -> bool:
        if sys.platform != "win32" or EmbeddedStlPreview is None:
            return False
        base = self._ensure_server()
        if not base:
            return False
        if self._embed is None:
            self._embed = EmbeddedStlPreview(self._host)
            self._embed.bind_resize()
        if self._embed.active:
            self._embed_ok = True
            self._placeholder.place_forget()
            return True
        if self._embed.start(base):
            self._embed_ok = True
            self._placeholder.place_forget()
            self.after(50, self.fit_to_panel)
            return True
        return False

    def _resize_embed(self) -> None:
        if self._embed and self._embed.active:
            self._embed.resize()

    def fit_to_panel(self) -> None:
        """Vorschau-Fenster an Rahmengröße anpassen (nach Layout / Sash)."""
        self._resize_embed()
        if self._embed:
            self._embed._schedule_resize_burst()

    def _stop_embed(self) -> None:
        if self._embed:
            self._embed.stop()
        self._embed_ok = False
        self._placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def clear(self, message: str | None = None) -> None:
        self._path = None
        self._hint_lbl.config(text="")
        StlPreviewServer.state().set_file(None)
        self._stop_embed()
        self._placeholder.config(
            text=message
            or "STL wählen — Vorschau lädt hier.\n\nDrehen/Zoomen mit Maus.",
            fg=MUTED,
        )

    def load_stl(self, path: Path) -> bool:
        path = path.resolve()
        if not path.is_file():
            self.clear("Datei nicht gefunden.")
            return False
        self._path = path
        self._hint_lbl.config(text=path.name[:36] + ("…" if len(path.name) > 36 else ""))
        StlPreviewServer.state().set_file(path)
        if not self._start_embed():
            self._placeholder.config(
                text="3D-Vorschau: Edge/Chrome nötig\n"
                f"(STL: {path.name})\n\n"
                "„Windows 3D Viewer“ für volle Ansicht.",
                fg=MUTED,
            )
            self._placeholder.place(relx=0.5, rely=0.5, anchor="center")
            return False
        self._resize_embed()
        return True

    def _reload(self) -> None:
        if self._path:
            StlPreviewServer.state().set_file(self._path)
            self._resize_embed()

    def _open_external(self) -> None:
        if self._external_cb and self._path:
            self._external_cb(self._path)

    def destroy(self) -> None:
        self._stop_embed()
        super().destroy()
