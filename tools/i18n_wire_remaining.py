"""Wire remaining hardcoded German UI strings to _t() keys."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS: dict[str, list[tuple[str, str]]] = {
    "ui/panels/model_library_panel.py": [
        ('text="Datei importieren…"', 'text=_t("mlp.btn.import_file")'),
        ('text="Ordner importieren…"', 'text=_t("mlp.btn.import_folder")'),
        ('text="Umbenennen…", command=self._rename_file', 'text=_t("mlp.btn.rename"), command=self._rename_file'),
        ('text="In Ordner verschieben…"', 'text=_t("mlp.btn.move")'),
        ('text="Bibliothek sichern…"', 'text=_t("mlp.btn.backup")'),
        ('text="Bibliothek laden…"', 'text=_t("mlp.btn.restore")'),
        ('text="Speichern unter…", command=self._export_file', 'text=_t("mlp.btn.save_as"), command=self._export_file'),
        ('text="Ordner", style="Muted.TLabel"', 'text=_t("mlp.label.folder"), style="Muted.TLabel"'),
        ('text="Unterordner", command=self._new_folder', 'text=_t("mlp.btn.subfolder"), command=self._new_folder'),
        ('text="Umbenennen", command=self._rename_folder', 'text=_t("mlp.btn.rename_short"), command=self._rename_folder'),
        ('text="Dateien", style="Muted.TLabel"', 'text=_t("mlp.label.files"), style="Muted.TLabel"'),
        ('text="Suche:"', 'text=_t("mlp.label.search")'),
        ('text="Nur offen"', 'text=_t("mlp.chk.open_only")'),
        ('text="Umbenennen", command=self._rename_file', 'text=_t("mlp.btn.rename_short"), command=self._rename_file'),
        ('text="Erledigt ✓"', 'text=_t("mlp.btn.done")'),
        ('text="  Vorschau  "', 'text=_t("mlp.section.preview")'),
        ('text="Erledigt (bereits gedruckt / fertig)"', 'text=_t("mlp.chk.printed")'),
        ('text="Anzeigename", style="Muted.TLabel"', 'text=_t("mlp.label.display_name"), style="Muted.TLabel"'),
        ('text="Quelle (URL)", style="Muted.TLabel"', 'text=_t("mlp.label.source_url"), style="Muted.TLabel"'),
        ('text="Bemerkung", style="Muted.TLabel"', 'text=_t("mlp.label.note"), style="Muted.TLabel"'),
        ('text="Pfad", style="Muted.TLabel"', 'text=_t("mlp.label.path"), style="Muted.TLabel"'),
        ('text="3D extern…"', 'text=_t("mlp.btn.open_3d")'),
        ('text="Details speichern"', 'text=_t("mlp.btn.save_details")'),
        (
            'text="Speichern unter: Dateien oder Ordner links (Strg+Klick) — mit Unterordnern | Verschieben: auf Zielordner ziehen."',
            'text=_t("mlp.hint.save_under")',
        ),
        ('self._files_title.config(text="Dateien")', 'self._files_title.config(text=_t("mlp.label.files"))'),
        ('notify(self, "Zum Verschieben auf einen Ordner links loslassen.", "warn")', 'notify(self, _t("mlp.notify.drop_on_folder"), "warn")'),
        ('notify(self, "Gespeichert.", "ok")', 'notify(self, _t("mlp.notify.saved"), "ok")'),
        ('ok_text="Verschieben"', 'ok_text=_t("mlp.btn.move_ok")'),
        (
            'notify(self, "Export fehlgeschlagen:\\n" + "\\n".join(failed[:8]), "error")',
            'notify(self, _t("mlp.notify.export_failed", failed="\\n".join(failed[:8])), "error")',
        ),
        (
            'notify(self, "Microsoft Store geöffnet — „3D Viewer“ installieren.", "info")',
            'notify(self, _t("mlp.notify.store_opened"), "info")',
        ),
        (
            'messagebox.showwarning(\n                APP_NAME,\n                "Bitte zuerst eine Datei in der mittleren Liste anklicken.\\n\\n"\n                + _t("mlp.notify.check_path_or_reimport"),',
            'messagebox.showwarning(\n                APP_NAME,\n                _t("mlp.msg.pick_one_file") + "\\n\\n"\n                + _t("mlp.notify.check_path_or_reimport"),',
        ),
    ],
    "ui/panels/settings_panel.py": [
        ('value="GitHub-Statistik: wird geladen …"', 'value=_t("settings.github.loading")'),
        ('set("GitHub-Statistik: wird geladen …")', 'set(_t("settings.github.loading"))'),
        ('text = "GitHub: keine Release-Infos erreichbar."', 'text = _t("settings.github.no_release")'),
        ('hint = " — Update verfügbar!" if newer else ""', 'hint = _t("settings.github.update_hint") if newer else ""'),
        (
            'text = (\n                        f"Installiert: {APP_VERSION}{hint}\\n"\n                        f"GitHub neuestes Release: {info.tag}\\n"\n                        f"{dl}"\n                    )',
            'text = _t("settings.github.stats_line", version=APP_VERSION, hint=hint, tag=info.tag, downloads=dl)',
        ),
        ('text = f"GitHub-Statistik fehlgeschlagen: {exc}"', 'text = _t("settings.github.failed", exc=exc)'),
    ],
    "ui/panels/cfs_dashboard.py": [
        ('title = "Filamenteinstellungen" if self._creality else "Filament"', 'title = _t("cfsd.title_creality") if self._creality else _t("cfsd.title_filament")'),
        ('value="1 CFS am Drucker (1A–1D)"', 'value=_t("cfsd.summary_one_cfs")'),
        ('"4× CFS Demo"', '_t("cfsd.demo_start")'),
        ('"Vier CFS-Einheiten nur zur Ansicht (ohne Drucker). Erneut klicken = aus."', '_t("cfsd.demo_tip")'),
        ('"Alle Slots"', '_t("cfsd.btn.all_slots")'),
        ('"CFS-Daten neu laden."', '_t("cfsd.refresh_tip")'),
        ('value="Aktiv: —"', 'value=_t("cfsd.active_none")'),
        ('value="Feuchtigkeit: —"', 'value=_t("cfsd.humidity_none")'),
        ('"Filament in den Drucker laden."', '_t("cfsd.feed_tip")'),
        ('"Spule" if not compact else "Sp"', '_t("cfsd.label_spool") if not compact else _t("cfsd.label_spool_short")'),
        ('self._status_var.set(f"{lab}: leer — Spule einlegen")', 'self._status_var.set(_t("cfsd.slot_empty", label=lab))'),
    ],
    "ui/panels/printer_device_panel.py": [
        ('text="Verbinde mit dem Drucker — Kamera startet automatisch"', 'text=_t("pdp.cam.connecting")'),
        ('notify(self, "Bitte Drucker-IP eintragen (Tab RFID-Tag oder Material-Datenbank).", "warn")', 'notify(self, _t("pdp.notify.enter_ip"), "warn")'),
        ('notify(self, "Pillow fehlt — pip install pillow", "error")', 'notify(self, _t("pdp.notify.pillow_missing"), "error")'),
        ('notify(self, "Kein G-Code zum Kopieren.", "warn")', 'notify(self, _t("pdp.notify.no_gcode_copy"), "warn")'),
        ('notify(self, "G-Code in Zwischenablage kopiert.", "ok")', 'notify(self, _t("pdp.notify.copied"), "ok")'),
        ('notify(self, "Kein G-Code zum Speichern.", "warn")', 'notify(self, _t("pdp.notify.no_gcode_save"), "warn")'),
        ('notify(self, f"Speichern fehlgeschlagen: {exc}", "error")', 'notify(self, _t("pdp.notify.save_failed", exc=exc), "error")'),
        ('notify(self, "Kein G-Code zum Export.", "warn")', 'notify(self, _t("pdp.notify.no_gcode_export"), "warn")'),
        ('notify(self, "Suchbegriff eingeben (z. B. M104, LAYER).", "warn")', 'notify(self, _t("pdp.notify.search_term"), "warn")'),
        ('notify(self, "Zuerst mit dem Drucker verbinden.", "warn")', 'notify(self, _t("pdp.notify.connect_first"), "warn")'),
        ('notify(self, "Druck-Check wird vorbereitet …", "info")', 'notify(self, _t("pdp.notify.print_check_prep"), "info")'),
        ('notify(self, "CFS-Slots werden geladen …", "info")', 'notify(self, _t("pdp.notify.cfs_loading"), "info")'),
        ('notify(self, "Kein laufender Druck — Job in Creality Print starten.", "warn")', 'notify(self, _t("pdp.notify.no_print_running"), "warn")'),
        ('notify(self, "Pause gesendet", "ok")', 'notify(self, _t("pdp.notify.pause_sent"), "ok")'),
        ('notify(self, "Fortsetzen gesendet", "ok")', 'notify(self, _t("pdp.notify.resume_sent"), "ok")'),
        ('notify(self, "4× CFS Demo beendet — wieder echte CFS-Daten.", "ok")', 'notify(self, _t("pdp.notify.demo_ended"), "ok")'),
        ('notify(self, "Stopp gesendet", "ok")', 'notify(self, _t("pdp.notify.stop_sent"), "ok")'),
        ('notify(self, "Bitte zuerst die Drucker-IP im Tab „RFID-Tag“ eintragen.", "warn")', 'notify(self, _t("pdp.notify.enter_ip_rfid"), "warn")'),
        ('title="G-Code vom Drucker speichern"', 'title=_t("pdp.title.save_from_printer")'),
        ('title="G-Code auf den Drucker kopieren"', 'title=_t("pdp.title.upload_gcode")'),
        ('self.cfs_dashboard.set_mode_hint("1 CFS am Drucker (1A–1D)")', 'self.cfs_dashboard.set_mode_hint(_t("cfsd.summary_one_cfs"))'),
    ],
}

MW_REPLACEMENTS = [
    ('"Aktuelle Tag-Daten als Spule unter „Meine Spulen“ speichern."', '_t("mw.tip.save_spool")'),
    ('"Material-Datenbank als JSON-Datei speichern."', '_t("mw.tip.save_db_json")'),
    ('"Letztes Material erneut laden — Seriennummer +1, neuer Tag."', '_t("mw.tip.same_spool_again")'),
    ('"Suchfeld leeren und alle Materialien wieder anzeigen."', '_t("mw.tip.clear_search")'),
    (
        '"Tab „Filament-Profil“ — Profil anzeigen (nur Lesen, Daten vom Drucker)."',
        '_t("mw.tip.edit_profile_readonly")',
    ),
    ('"Zum Tab Material-Datenbank — Profil nur per „Vom Drucker (SSH)“ laden."', '_t("mw.tip.goto_db_printer")'),
    ('"Zum Tab Material-Datenbank wechseln (Import vom Drucker/Cloud)."', '_t("mw.tip.goto_db_cloud")'),
    ('"material_database.json per SSH vom Drucker holen."', '_t("mw.tip.db_ssh")'),
    ('"Material-Datenbank von Creality Cloud herunterladen."', '_t("mw.tip.db_cloud")'),
    ('"material_database.json per SSH vom Drucker holen (nur Lesen)."', '_t("mw.tip.db_ssh_readonly")'),
    ('("name", "Material", 220)', '("name", _t("mw.label.material"), 220)'),
    ('"IP, SSH, DB-Vergleich und Upload im Tab „Drucker“."', '_t("mw.tip.printer_ssh")'),
    ('"Hilfe zum NFC-Reader und Windows Smartcard-Dienst."', '_t("mw.tip.smartcard_help")'),
    ('"Tag-Halter STL speichern…"', '_t("mw.btn.holder_stl")'),
    (
        '"Halter (Thingiverse), Tags/Reader (Amazon-Beispiele), weitere Links — Printables & Creality Cloud."',
        '_t("mw.tip.holder_links")',
    ),
    ('"ACS NFC-Reader per USB verbinden (PC/SC muss laufen)."', '_t("mw.tip.connect_reader")'),
    ('"Neues Filament-Profil in der Datenbank anlegen."', '_t("mw.tip.new_profile")'),
    ('txt = f"⚠  {n} Demo-Materialien — bitte DB laden"', 'txt = _t("mw.status.demo_materials", n=n)'),
    ('"printer": "Drucker"', '"printer": _t("mw.src.printer")'),
    ('txt = f"✓  {n} Materialien  ·  {src}  ·  {name}"', 'txt = _t("mw.status.materials_ok", n=n, src=src, name=name)'),
    ('"name": "Material"', '"name": _t("mw.label.material")'),
    (
        'text=f"⚠ Demo: {shown} von {total} — bitte echte DB laden (Cloud/Drucker)"',
        'text=_t("mw.profile.demo_banner", shown=shown, total=total)',
    ),
    (
        'self._profile_list_title.config(text=f"Alle {total} Material-Profile in der Datenbank")',
        'self._profile_list_title.config(text=_t("mw.profile.all_count", total=total))',
    ),
    ('self._set_status(f"{label} fehlgeschlagen", "error")', 'self._set_status(_t("mw.status.task_failed", label=label), "error")'),
    ('msg = f"{n} Material-Profile von Creality Cloud geladen."', 'msg = _t("mw.notify.cloud_loaded", n=n)'),
    ('msg + f"\\n\\n(Drucker: {printer})"', ' + _t("mw.notify.printer_line", printer=printer)'),
    (
        '"Bitte Drucker-IP eintragen\\n"\n                "(Tab „Material-Datenbank“ unten oder „RFID-Tag“)."',
        '_t("mw.notify.enter_ip_msg")',
    ),
    ('self._run_ssh_job("Vom Drucker laden", work, on_ok=on_ok)', 'self._run_ssh_job(_t("mw.job.from_printer"), work, on_ok=on_ok)'),
    ('self.notify(f"{len(self.profiles)} Profile geladen.")', 'self.notify(_t("mw.notify.profiles_loaded", n=len(self.profiles)))'),
    ('self.notify("Keine DB geladen.")', 'self.notify(_t("mw.notify.no_db_loaded"))'),
    ('return f"Spule „{existing.label}“ aktualisiert"', 'return _t("mw.spools.updated", label=existing.label)'),
    ('return f"Spule „{sp.label}“ neu angelegt"', 'return _t("mw.spools.created_new", label=sp.label)'),
    ('label = "Neue Spule"', 'label = _t("mw.label.new_spool")'),
    ('sp.label in ("Neue Spule", "Spule")', 'sp.label in (_t("mw.label.new_spool"), _t("mw.label.spool_default"))'),
    ('self._set_status(f"Spule: {spool.label} — {prof.name}", "ok")', 'self._set_status(_t("mw.status.spool_with_profile", label=spool.label, name=prof.name), "ok")'),
    ('self._set_status(f"Spule: {spool.label}", "ok")', 'self._set_status(_t("mw.status.spool_only", label=spool.label), "ok")'),
    ('dlg.title(f"CFS {slot.label} — Spule zuweisen")', 'dlg.title(_t("mw.cfs.bind_title", label=slot.label))'),
    (
        'text=f"Slot {slot_label(slot_index)}: {slot.display}\\n"\n            "Welche Spule aus „Meine Spulen“ steckt hier?"',
        'text=_t("mw.cfs.bind_prompt", slot=slot_label(slot_index), display=slot.display)',
    ),
    (
        '"Verbrauch von der Spule abgezogen, aber der Historie-Eintrag "\n                "konnte nicht gespeichert werden — bitte App neu starten und erneut versuchen."',
        '_t("mw.history.save_failed")',
    ),
    ('matched.label or matched.material_name or "Spule"', 'matched.label or matched.material_name or _t("mw.label.spool_default")'),
    ('return "Meine Spule: " + " · ".join(parts)', 'return _t("mw.spool.my_prefix") + " · ".join(parts)'),
    ('.replace("Meine Spule: ", "")', '.replace(_t("mw.spool.my_prefix"), "")'),
    ('self._set_tag_diagnostic_text(f"Diagnose fehlgeschlagen:\\n{exc}")', 'self._set_tag_diagnostic_text(_t("mw.tag.diagnostic_failed", exc=exc))'),
    ('f"UID: {uid}\\nSpule: {spool_txt}\\n\\n"', 'f"{_t(\'mw.tag.uid_line\', uid=uid)}\\n{_t(\'mw.tag.spool_line\', spool=spool_txt)}\\n\\n"'),
    ('f"Material-ID: {info[\'material_id\']}\\n"', 'f"{_t(\'mw.tag.material_id\', id=info[\'material_id\'])}\\n"'),
    ('f"Drucker: {info.get(\'printer\', \'\') or \'—\'}"', 'f"{_t(\'mw.tag.printer_label\', printer=info.get(\'printer\', \'\') or \'—\')}"'),
    ('messagebox.showerror(APP_NAME, "Lesen fehlgeschlagen — Vorgang abgebrochen.")', 'messagebox.showerror(APP_NAME, _t("mw.dup.read_failed_abort"))'),
    (
        '"Bitte den Vorlagen-Chip wirklich wegnehmen und einen anderen "\n                    "Chip auflegen (z. B. die andere Seite der Spole)."',
        '_t("mw.dup.swap_chip_warn")',
    ),
    ('self._set_status("Schreiben abgebrochen — Ziel-Chip erneut auflegen", "warn")', 'self._set_status(_t("mw.dup.write_cancelled"), "warn")'),
    (
        '"Nicht in „Meine Spulen“ — bitte Spule anlegen, sonst wirkt der neue Chip „fremd“"',
        '_t("mw.dup.not_in_spools")',
    ),
    ('body += f"Spule in der App: „{spool_title}“\\n"', 'body += _t("mw.dup.spool_in_app", title=spool_title) + "\\n"'),
    ('if messagebox.askyesno(APP_NAME, "Fehler — Vorgang abbrechen?", default="yes"):', 'if messagebox.askyesno(APP_NAME, _t("mw.notify.dup_abort_q"), default="yes"):'),
    (
        '"Legen Sie den bereits beschriebenen Vorlagen-Chip "\n            "auf den Reader (Schritt 1)."',
        '_t("mw.dup.template_place")',
    ),
    ('self._set_status("Chip duplizieren abgebrochen", "info")', 'self._set_status(_t("mw.dup.cancelled_status"), "info")'),
    ('self._set_status("Reader-Fehler", "error")', 'self._set_status(_t("mw.status.reader_error"), "error")'),
    ('self._set_status(f"Reader bereit — Tag auflegen: {short}", "ok")', 'self._set_status(_t("mw.status.reader_ready", short=short), "ok")'),
    ('self.notify(f"Gesichert:\\n{path}")', 'self.notify(_t("mw.notify.saved_backup", path=path))'),
    ('self.notify(f"Material-DB importiert:\\n{out.name}")', 'self.notify(_t("mw.notify.db_imported", name=out.name))'),
    ('self._set_status("Update: Setup wird geladen (ca. 60 MB) …", "info")', 'self._set_status(_t("mw.update.downloading"), "info")'),
    ('text = f"Update: {received // (1024 * 1024)} MB geladen …"', 'text = _t("mw.update.downloaded_mb", mb=received // (1024 * 1024))'),
]

REPLACEMENTS["app/main_window.py"] = MW_REPLACEMENTS


def apply_file(rel: str, pairs: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    missing = []
    for old, new in pairs:
        if old not in text:
            missing.append(old[:70])
        else:
            text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print(f"{rel}: {len(pairs) - len(missing)}/{len(pairs)} applied")
    for m in missing[:8]:
        print(f"  MISSING: {m}")
    if len(missing) > 8:
        print(f"  ... and {len(missing) - 8} more")


def main() -> None:
    for rel, pairs in REPLACEMENTS.items():
        apply_file(rel, pairs)


if __name__ == "__main__":
    main()
