"""Final i18n sweep — wire remaining user-facing strings."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# file -> list of (old, new)
SWEEPS: dict[str, list[tuple[str, str]]] = {
    "ui/panels/model_library_panel.py": [
        (
            '"PDF, TXT, Bilder … mit Standardprogramm; STL/3MF im 3D-Viewer."',
            '_t("mlp.tip.open_file_types")',
        ),
        (
            '"Haken setzen = Teil ist erledigt. Bleibt nach Neustart gespeichert."',
            '_t("mlp.tip.done_checkbox")',
        ),
        ('storage = "Kopie" if e.storage == "copy" else "Link"', 'storage = _t("mlp.storage.copy") if e.storage == "copy" else _t("mlp.storage.link")'),
        (
            'label = f"{folder.name}  ({n_files} Datei{\'en\' if n_files != 1 else \'\'})"',
            'label = _t("mlp.folder.file_count", name=folder.name, n=n_files)',
        ),
        ('self._path_var.set(str(path) if path else "— Datei nicht gefunden —")', 'self._path_var.set(str(path) if path else _t("mlp.path.not_found"))'),
        ('self._stl_preview.clear("Datei nicht gefunden.")', 'self._stl_preview.clear(_t("mlp.preview.file_not_found"))'),
        (
            'self._stl_preview.clear("3MF: Vorschau nur extern\\n(„3D extern…“ oder Creality).")',
            'self._stl_preview.clear(_t("mlp.preview.3mf_external"))',
        ),
        ('return [(e, Path()) for e in file_sel], f"{len(file_sel)} Datei(en)"', 'return [(e, Path()) for e in file_sel], _t("mlp.export.n_files", n=len(file_sel))'),
        ('return items, f"Ordner {label}"', 'return items, _t("mlp.export.folder_label", label=label)'),
        ('notify(self, f"Nicht gefunden: {raw}", "warn")', 'notify(self, _t("mlp.notify.not_found_raw", raw=raw), "warn")'),
        ('notify(self, f"{p.name}: {exc}", "error")', 'notify(self, _t("mlp.notify.path_error", name=p.name, exc=exc), "error")'),
        ('notify(self, f"{Path(p).name}: {exc}", "error")', 'notify(self, _t("mlp.notify.path_error", name=Path(p).name, exc=exc), "error")'),
        (
            'msg += f"\\n\\nInkl. Unterordner: {n} Datei(en) werden entfernt."',
            'msg += "\\n\\n" + _t("mlp.confirm.delete_folder_extra", n=n)',
        ),
        (
            'f"{len(entries)} Datei(en) als {\'erledigt\' if mark_done else \'offen\'} markiert."',
            '_t("mlp.notify.marked_done", n=len(entries), state=_t("mlp.state.done") if mark_done else _t("mlp.state.open"))',
        ),
        (
            'f"{moved} Datei(en) verschoben nach: {crumb}"',
            '_t("mlp.notify.moved_files", n=moved, dest=crumb)',
        ),
        (
            'msg = f"{moved} Ordner verschoben nach: {crumb}"',
            'msg = _t("mlp.notify.moved_folders", n=moved, dest=crumb)',
        ),
        (
            'f"Bibliothek gesichert ({n} Dateien):\\n{dest}"',
            '_t("mlp.notify.backup_ok", n=n, dest=dest)',
        ),
        (
            'f"Bibliothek wiederhergestellt ({n} Dateien).\\n\\n{src}"',
            '_t("mlp.notify.restore_ok", n=n, src=src)',
        ),
        (
            '"Aktuelle Modell-Bibliothek durch das ZIP-Backup ersetzen?\\n\\n"\n            "Tipp: Vorher „Bibliothek sichern…“.\\n\\n"\n            "Fortfahren?"',
            '_t("mlp.confirm.restore")',
        ),
        (
            '"Keine Dateien zum Exportieren (Ordner leer oder Filter „Nur offen“ ausblenden)."',
            '_t("mlp.notify.export_empty")',
        ),
        (
            'title = f"„{label}“ — {len(items)} Dateien exportieren (Ordnerstruktur)"',
            'title = _t("mlp.title.export_batch", label=label, n=len(items))',
        ),
        (
            'msg = f"{ok} Datei(en) nach\\n{dest_dir}"',
            'msg = _t("mlp.notify.export_ok", n=ok, dest=dest_dir)',
        ),
        (
            'msg += f"\\n\\nFehler ({len(failed)}):\\n" + "\\n".join(failed[:5])',
            'msg += "\\n\\n" + _t("mlp.notify.export_errors_header", n=len(failed)) + "\\n".join(failed[:5])',
        ),
        ('filetypes=[("ZIP-Backup", "*.zip")]', 'filetypes=[(_t("mlp.filetype.zip_backup"), "*.zip")]'),
        ('filetypes=[("ZIP-Backup", "*.zip"), ("Alle", "*.*")]', 'filetypes=[(_t("mlp.filetype.zip_backup"), "*.zip"), (_t("mlp.filetype.all"), "*.*")]'),
    ],
    "ui/panels/printer_device_panel.py": [
        ('notify(self, f"HTML exportiert:\\n{path}", "ok")', 'notify(self, _t("pdp.notify.html_exported", path=path), "ok")'),
        ('notify(self, f"Nicht gefunden: {needle}", "warn")', 'notify(self, _t("pdp.notify.not_found", needle=needle), "warn")'),
        ('notify(self, f"Filament-Warnung vor Druck:\\n{msg}", "warn")', 'notify(self, _t("pdp.notify.filament_warn", msg=msg), "warn")'),
        ('self.app.notify(f"Filament-Abzug konnte nicht starten: {exc}", "warn")', 'self.app.notify(_t("pdp.notify.deduct_failed", exc=exc), "warn")'),
        ('lambda: notify(self, f"Zufuhr gestartet — Slot {slot.label}", "ok")', 'lambda: notify(self, _t("pdp.notify.feed_started", label=slot.label), "ok")'),
        ('lambda: notify(self, f"{label} OK", "ok")', 'lambda: notify(self, _t("pdp.notify.cmd_ok", label=label), "ok")'),
        ('self.app.after(0, lambda: notify(self, f"{label} OK", "ok"))', 'self.app.after(0, lambda l=label: notify(self, _t("pdp.notify.cmd_ok", label=l), "ok"))'),
        ('confirm(self, f"Druck auf {host} wirklich stoppen?", do)', 'confirm(self, _t("pdp.confirm.stop", host=host), do)'),
        (
            'text=f"Kein Vorschaubild\\n{name}\\n\\n(nur beim Slicen erzeugt)"',
            'text=_t("pdp.gcode.no_preview", name=name)',
        ),
        (
            'self.gcode_preview_label.config(image="", text=f"Vorschaubild fehlerhaft\\n{name}")',
            'self.gcode_preview_label.config(image="", text=_t("pdp.gcode.preview_bad", name=name))',
        ),
        (
            '"Slot wählen, dann Zufuhr oder Zurückziehen"',
            '_t("pdp.cfs.choose_feed_retract")',
        ),
        (
            '"Slot wählen · → RFID übernimmt Material in den Editor"',
            '_t("pdp.cfs.choose_rfid")',
        ),
        ('self._status_var.set("Dateiliste wird geladen…")', 'self._status_var.set(_t("pdp.status.loading_files"))'),
        ('self._status_var.set(f"{len(files)} Dateien (SSH)")', 'self._status_var.set(_t("pdp.status.files_ssh", n=len(files)))'),
        ('prog_txt = f"~{pct} % (Drucker meldet 0 %)"', 'prog_txt = _t("pdp.progress.stuck", percent=pct)'),
    ],
    "ui/panels/spool_panel.py": [
        ('("Bezeichnung", self.label_var)', '(_t("spools.field.label"), self.label_var)'),
        ('("Bemerkung", self.notes_var)', '(_t("spools.field.notes"), self.notes_var)'),
        ('("Material", self.material_var)', '(_t("spools.field.material"), self.material_var)'),
        ('("Filament-ID (5 Ziffern)", self.fid_var)', '(_t("spools.field.filament_id"), self.fid_var)'),
        ('("Seriennummer", self.serial_var)', '(_t("spools.field.serial"), self.serial_var)'),
        ('("Restgewicht (g)", self.remaining_var)', '(_t("spools.field.remaining"), self.remaining_var)'),
        ('("Drucker am Tag", self.printer_var)', '(_t("spools.field.printer_tag"), self.printer_var)'),
        (
            '"Marke, Material, Filament-ID und Profilfarbe aus der Material-Datenbank laden."',
            '_t("spools.editor.adopt_tip")',
        ),
        ('"Windows-Farbauswahl (wie im RFID-Tab)."', '_t("spools.editor.color_dialog_tip")'),
        ('"Alle Chip-UIDs von dieser Spule entfernen."', '_t("spools.editor.unlink_all_tip")'),
        ('title="Filamentfarbe"', 'title=_t("spools.color.title")'),
        ('loc_vals = [""] + [p.name for p in load_printers()] + ["Lager / Regal"]', 'loc_vals = [""] + [p.name for p in load_printers()] + [_t("spools.location.storage")]'),
        ('("Material", self.material_var)', '(_t("spools.field.material"), self.material_var)'),  # spool list cols - may duplicate
    ],
    "ui/panels/filament_editor_panel.py": [
        (
            'self._summary_temp.config(text=f"Temperaturbereich: {min_t} – {max_t} °C")',
            'self._summary_temp.config(text=_t("fep.summary.temp_range", min_t=min_t, max_t=max_t))',
        ),
    ],
    "app/main_window.py": [
        ('self.ask_confirm(msg + "\\n\\nJetzt starten?", self.start_smartcard_service)', 'self.ask_confirm(msg + _t("mw.notify.start_now_q"), self.start_smartcard_service)'),
        ('self.ask_confirm(msg + "\\n\\nJetzt neu starten?", self.start_smartcard_service)', 'self.ask_confirm(msg + _t("mw.notify.restart_now_q"), self.start_smartcard_service)'),
        ('self._set_status("Cloud OK", "ok")', 'self._set_status(_t("mw.status.cloud_ok"), "ok")'),
        ('self._set_status(f"Merge OK — {total} Profile", "ok")', 'self._set_status(_t("mw.status.merge_ok", total=total), "ok")'),
        ('self.notify(f"+{added} neu, {updated} aktualisiert. Gesamt: {total}.{extra}", "ok")', 'self.notify(_t("mw.notify.merge_result", added=added, updated=updated, total=total, extra=extra), "ok")'),
        ('self.notify("Zuerst DB laden.")', 'self.notify(_t("mw.notify.load_db_first"))'),
        ('self._set_status("Tag wird geleert…", "info")', 'self._set_status(_t("mw.status.clearing_tag"), "info")'),
        ('self._set_status("Smartcard wird neu gestartet…", "warn")', 'self._set_status(_t("mw.status.scard_restarting"), "warn")'),
        ('self._set_status("Smartcard aktiv", "ok")', 'self._set_status(_t("mw.status.scard_active"), "ok")'),
        ('self._set_status("Dienst OK — Reader per USB verbinden", "warn")', 'self._set_status(_t("mw.status.scard_ok_usb"), "warn")'),
        (
            'self.notify("Dienst antwortet noch nicht.\\n\\n"\n                          "UAC mit „Ja“ bestätigen, 5–10 s warten, erneut „Reader verbinden“.", "warn")',
            'self.notify(_t("mw.notify.service_not_ready"), "warn")',
        ),
        ('self._set_status(f"Reader verbunden: {short}", "ok")', 'self._set_status(_t("mw.status.reader_connected", short=short), "ok")'),
        ('self._set_status("Tag leer", "ok")', 'self._set_status(_t("mw.status.tag_empty"), "ok")'),
        ('self._set_status("Tag gelesen", "ok")', 'self._set_status(_t("mw.status.tag_read"), "ok")'),
        ('self._set_status("Tag wird gelesen…", "info")', 'self._set_status(_t("mw.status.tag_reading"), "info")'),
        ('self._set_status("Tag wird geschrieben…", "info")', 'self._set_status(_t("mw.status.tag_writing"), "info")'),
        ('self._set_status(f"Reader: {short}", "ok")', 'self._set_status(_t("mw.status.reader_label", short=short), "ok")'),
        ('self._set_status("Reader einstecken…", "warn")', 'self._set_status(_t("mw.status.reader_plug_in"), "warn")'),
        ('self.notify(f"Slot {slot_label(slot_index)} → „{sp.label}“", "ok")', 'self.notify(_t("mw.notify.slot_linked", slot=slot_label(slot_index), label=sp.label), "ok")'),
        ('self.notify(f"Slot {slot_label(slot_index)} → „{sp.label if sp else sid}“", "ok")', 'self.notify(_t("mw.notify.slot_linked", slot=slot_label(slot_index), label=sp.label if sp else sid), "ok")'),
        ('started or "aktiv" in msg', 'started or _t("mw.status.active_keyword") in msg'),
    ],
    "app/bundled_assets.py": [
        ('notify(parent, f"Datei fehlt im Programm:\\n{relative}", "error")', 'notify(parent, _t("assets.file_missing", path=relative), "error")'),
        ('notify(parent, f"Gespeichert:\\n{path}", "info")', 'notify(parent, _t("assets.saved", path=path), "info")'),
    ],
    "printer_manager.py": [
        ('ttk.Button(btn_bar, text="OK", command=ok, style="Accent.TButton")', 'ttk.Button(btn_bar, text=_t("btn.ok"), command=ok, style="Accent.TButton")'),
    ],
    "creality_nfc/print_readiness.py": [
        ('ReadinessLine("error", "Keine G-Code-Datei gewählt.")', 'ReadinessLine("error", _t("readiness.no_gcode"))'),
        (
            '"Keine Farb-/Slot-Zuordnung aus G-Code — bitte Material im Slicer prüfen."',
            '_t("readiness.no_color_mapping")',
        ),
        ('ReadinessLine("info", f"Geschätzter Gesamtverbrauch: ca. {total_g} g ({job[1]}).")', 'ReadinessLine("info", _t("readiness.total_usage", total_g=total_g, job=job[1]))'),
        (
            'f"{lab}: keine Spule in „Meine Spulen“ verknüpft "\n                        f"(ca. {need_g} g nötig)."',
            '_t("readiness.no_spool_linked", slot=lab, need_g=need_g)',
        ),
        (
            'f"{lab}: „{sp.label}“ — Rest unbekannt, ca. {need_g} g nötig."',
            '_t("readiness.unknown_remain", slot=lab, label=sp.label, need_g=need_g)',
        ),
        (
            'f"{lab}: „{sp.label}“ — nur {rem} g Rest, ca. {need_g} g nötig."',
            '_t("readiness.low_remain", slot=lab, label=sp.label, rem=rem, need_g=need_g)',
        ),
        (
            'f"{lab}: „{sp.label}“ — {rem} g Rest, ca. {need_g} g nötig."',
            '_t("readiness.ok_remain", slot=lab, label=sp.label, rem=rem, need_g=need_g)',
        ),
    ],
    "creality_nfc/live_filament.py": [
        ('return "Filament: Schätzung aus G-Code nicht verfügbar"', 'return _t("live_filament.no_estimate")'),
        ('parts.append("⚠ Rest evtl. knapp für Job-Ende")', 'parts.append(_t("live_filament.low_warning"))'),
    ],
    "creality_nfc/print_cfs.py": [
        (
            '"Kein Filament im CFS — Slot mit Material wählen (z. B. 1A oder 3B) oder Spule einlegen."',
            '_t("print_cfs.no_filament")',
        ),
        ('"Spulenhalter"', '_t("print_cfs.spool_holder")'),
    ],
    "creality_nfc/cfs_feed.py": [
        (
            '"Filament-Zufuhr: Zeitüberschreitung.\\n"\n        "Filament in Creality Print laden (Zufuhr) oder in der App den richtigen Slot wählen "',
            '_t("cfs_feed.timeout_part1")',
        ),
        (
            '"Fehler FR0121: CFS-Filament im Extruder, Job aber für Spulenhalter gesliced → CFS zurückziehen "',
            '_t("cfs_feed.error_fr0121")',
        ),
    ],
    "creality_nfc/spool_inventory.py": [
        ('return "— (kein Tag verknüpft)"', 'return _t("spools.editor.no_tag_linked")'),
    ],
}


def main() -> None:
    for rel, pairs in SWEEPS.items():
        path = ROOT / rel
        if not path.exists():
            print(f"SKIP missing {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = 0
        for old, new in pairs:
            if old not in text:
                missing += 1
                print(f"  MISSING [{rel}]: {old[:60]}...")
            else:
                text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        print(f"{rel}: {len(pairs) - missing}/{len(pairs)} applied")


if __name__ == "__main__":
    main()
