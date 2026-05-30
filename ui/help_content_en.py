"""English help text for TD Filament Studio."""

PROGRAM_HELP_EN = """
TD FILAMENT STUDIO \u2014 Quick guide
==================================

Overview
--------
TD Filament Studio writes Creality K2/CFS RFID tags (MIFARE Classic) and manages
the material database (material_database.json) on the printer.

The RFID tag only stores: material ID, color, weight class, serial number, printer model.
All print parameters (temperatures, flow, retraction) live in the JSON database
on the printer \u2014 not on the tag.

The printer IP is shared between the RFID tab, the "Printer" tab and SSH
(one field, used everywhere).


Required hardware & tags (shopping list)
----------------------------------------
To write the RFID tags from the PC you need this exact combination:

RFID tags (per spool)
\u2022 Chip type: MIFARE Classic 1K (ISO 14443A) \u2014 often sold as "MF1 S50", "1K", "M1"
\u2022 Form: round stickers/discs, typically 25 mm in diameter (1 inch)
\u2022 Not suitable: NTAG213/215/216, NTAG2xx, plain UID tags without Classic 1K memory
\u2022 Creality original tags on spools work; blank aftermarket stickers work too
\u2022 Recommendation: 2 tags per spool (left + right on the flange), write both identically
\u2022 Packs of "10 pcs \u00d7 2" = 20 stickers for 10 spools

NFC reader (on the PC)
\u2022 USB reader with PC/SC driver, proven: ACS ACR122U (or compatible clone)
\u2022 USB on the PC; LED lit, place tag flat to read/write
\u2022 On Windows: Device Manager \u2192 "Smart card readers" (when driver OK)
\u2022 iPhone/iPad: tags cannot be written with those (no Classic 1K access)

Example (purchased by the developer, Amazon.de \u2014 no affiliate link):
\u2022 Reader: Ieron RFID/NFC ACR122U \u2014 https://www.amazon.de/dp/B0DSC293JN
\u2022 Tags: YARONGTECH MF1 S50, 25 mm, 10 pcs \u2014 https://www.amazon.de/dp/B0BL2YJ5GB
  (also under "Tag holder (links)\u2026" \u2192 Amazon section)

Windows (prerequisite)
\u2022 The "Smart Card" service (SCardSvr) must be running \u2014 see "Smartcard service" section
\u2022 TD Filament Studio does not need admin for normal use; only UAC when starting the service

Optional
\u2022 3D holder: "Save tag holder STL\u2026" (bundled) or "Tag holder (links)\u2026" in the RFID tab
\u2022 K2/CFS printer + WiFi: only needed for material DB and live control, not for writing tags


Tab: RFID tag
-------------
At the top of the action bar
\u2022 Big line: spool name or "Tag empty \u2014 ready to write"
\u2022 UID and hint whether the spool is linked in "My spools"

Reader & tags
\u2022 Connect reader \u2014 ACR122U via USB; smart card service must be running (see below).
  Works without a tag on the reader; place the tag flat to read/write.
\u2022 Start smartcard / Restart (UAC) \u2014 if the service is stopped or stuck
\u2022 Read tag / Write tag \u2014 with verification after writing (dialog "done")
\u2022 Tag protection (settings): warn if the chip already carries filament data
\u2022 Clear tag\u2026 \u2014 deletes Creality data; afterwards often C3B98E\u2026 blocks in raw data
  (encrypted empty \u2014 normal). Lift tag for 2\u20133 s, place again.
\u2022 Duplicate chip\u2026 \u2014 read the template chip, copy onto a second tag
  (e.g. left+right on the spool); every UID is mapped to the same spool in "My spools"
\u2022 Same spool again \u2014 reuse the last material (serial +1)
\u2022 Export tag\u2026 \u2014 the last read operation as JSON
\u2022 Presets / Color\u2026 / Photo\u2026 \u2014 color for the tag
\u2022 Save spool \u2014 form \u2192 "My spools"

Filament for the tag (scroll down)
\u2022 Brand / Material \u2014 "Name \u00b7 ID 12345"; an ID row must appear underneath
\u2022 Writing a tag from the PC: spool does NOT need to be in the CFS \u2014 just pick the material
\u2022 Shortcut: "My spools" tab \u2192 pick spool \u2192 "\u2192 RFID tab" (transfers data)
\u2022 Leave the search field empty, otherwise the material may be missing in the list
\u2022 A spool with a filament ID can be written even without an exact DB entry
\u2022 Edit profile / New profile\u2026 / Load database\u2026
\u2022 Tag memory\u2026 / "Read now from tag" \u2014 raw data (blocks 0\u201315)

Automation (options)
\u2022 Auto read \u2014 place tag \u2192 data is read, spool linked if possible
\u2022 Auto write \u2014 place tag \u2192 the selected material is written
\u2022 Sync spool to "My spools" \u2014 after each tag write create/update the spool (UID, color, material)
\u2022 Batch mode \u2014 for writing many tags in a row (see below)
\u2022 Auto +1 \u2014 increment the serial number after every write

Batch mode (short)
------------------
Only useful together with "Auto write".
1. Pick material, enable batch mode + auto write.
2. Place the first tag on the reader \u2192 it is written.
3. Status: "Tag OK \u2014 place next tag".
4. Remove the tag, place the next one \u2192 written automatically again.
Without batch mode the app writes only when a new tag UID is seen (a different tag).


Tab: Filament profile
---------------------
Edit the print parameters in the material database (not on the RFID tag).
\u2022 Selection: "RFID tag" tab \u2192 brand and material (with ID in the list)
\u2022 Tabs: Basic (ID, brand, name, type, min/max \u00b0C), print parameters, JSON (kvParam)
\u2022 "Protect from cloud/printer updates" \u2014 keeps your own temperatures during cloud merge
\u2022 Save to database \u2014 local only (k2_pro.json); printer is not overwritten

Important: several profiles can share the same 5-digit ID (e.g. three \u00d7 "06001").
Always pick the exact material from the list (name \u00b7 ID), otherwise the temperatures will be wrong.


Tab: Material database
----------------------
\u2022 Cloud \u2014 official Creality profiles (internet)
\u2022 From printer \u2014 load from the K2 via SSH (read-only; enable root, same WiFi)
\u2022 Merge cloud \u2014 insert cloud profiles into the local DB
\u2022 Import slicer profiles\u2026 \u2014 Orca/Creality JSON (notes: {"id","vendor","type","name"})
\u2022 Printer SSH \u2014 IP and password inside the tab
\u2022 Printer dashboard \u2014 status, compare DB, material_options.json, reboot

File menu
\u2022 Open DB / Save DB as\u2026
\u2022 Export material_options.json\u2026 \u2014 brand list for the display
\u2022 Backup data (ZIP)\u2026 / restore\u2026 \u2014 the entire data/ folder
\u2022 Settings \u2192 Reset program\u2026 \u2014 wipe everything like a fresh install (back up first!)
\u2022 Import CFS-RFID ZIP\u2026 \u2014 data from the older CFS-RFID tool


Tab: Printer
------------
Connection
\u2022 Connect \u2014 live WebSocket (port 9999), same as Creality Print
\u2022 Often automatic when opening the tab and on start if the IP is filled
\u2022 Disconnect \u2014 end the connection
\u2022 Live data stuck? The app reconnects on its own after a few seconds without reply
\u2022 Status bar at the bottom: "Connected \u2014 IP"; messages also there (no longer permanently black)

G-code
\u2022 List from the printer, preview image on click
\u2022 Upload\u2026 \u2014 file from the PC to the printer
\u2022 Download\u2026 \u2014 save the selected file to the PC
\u2022 Delete \u2014 remove the file on the printer
\u2022 Refresh \u2014 reload the list
\u2022 Start a print: Creality Print or the printer display (not from TD Filament Studio)

Print control (monitor)
\u2022 Pause / Resume / Stop \u2014 the running job from the app
\u2022 Resume only after pause \u2014 start a new job from Creality Print
\u2022 Deduct consumption\u2026 \u2014 manually after a print ends (when no dialog appeared)
\u2022 After a print the "Filament consumption" dialog usually appears (Cancel / Deduct)

Print with CFS
\u2022 Start and color matching: Creality Print (more reliable than starting from the app)
\u2022 TD Studio: show CFS slots, link spool, manual feed/retract
\u2022 Error TR0116: filament missing in extruder \u2192 thread it in Creality Print
\u2022 Error FR0121: CFS filament in extruder but job sliced for spool holder
  \u2192 retract in Creality Print or enable CFS in the slicer

CFS display (1A\u20131D)
\u2022 Colored boxes = filament color (black, blue, white \u2026), no status
\u2022 Orange border = filament "in use" (feed / reported by the printer)
\u2022 Text below: "In use: 1B" etc.
\u2022 \u2192 RFID \u2014 move the slot material to the RFID tab
\u2022 Feed / Retract \u2014 experimental (load/unload filament)
\u2022 \u21bb \u2014 request CFS data again

Camera / preview
\u2022 Live camera \u2014 picture in the preview (on every monitor); "Full screen" = separate Edge window
\u2022 Klipper / Web UI \u2014 browser to Moonraker/Klipper, if active

Control & temperatures
\u2022 Light, speed, home XY/Z
\u2022 Nozzle, bed, chamber \u2014 live display; set targets
\u2022 Fan \u2014 slider + "Set"


Tab: Model library
------------------
Your projects from Printables & Co.: STL/3MF, PDF manuals, images \u2014 not from the printer.

\u2022 Folders on the left \u2014 subfolders, rename, delete (with content), path "Library / \u2026"
\u2022 Parent folder \u2014 jump one level up
\u2022 Rename \u2014 folder (left) or file (top / F2)
\u2022 Move to folder \u2014 put the file into another folder (or drag & drop: drag file onto folder)
\u2022 Import file \u2014 or drag from Windows Explorer onto the tab (drag & drop)
\u2022 Supported: STL, 3MF, PDF, images, TXT \u2026, ZIP (everything inside, with folders), whole folders
\u2022 Link \u2014 only remember the path (the file stays e.g. in Downloads)
\u2022 STL \u2014 built-in 3D preview (rotate/zoom); "3D external\u2026" = Windows 3D Viewer
\u2022 Import folder / Save as with subfolders \u00b7 backup/load the library (ZIP)
\u2022 Done \u2713 \u2014 click the "\u2713" column or the check in the details (green = done/printed, persists)
\u2022 Details \u2014 name, source URL, note
\u2022 Search / Only open \u2014 filter the file list
\u2022 Save as\u2026 \u2014 single file: save dialog; multiple (Ctrl+click) or only folder on the left: pick target folder
\u2022 Open in Explorer \u2014 show the file or folder


Tab: My spools
--------------
Local inventory (data/spools.json): list on the left, edit on the right.
\u2022 "From material DB\u2026" \u2014 pick a profile (label always "Brand \u2014 Material", printer e.g. K2 Pro instead of F008)
\u2022 List: CFS 1A\u20131D on top (slot field or note CFS-S1\u2026), then alphabetically
\u2022 Color: "Color\u2026" (Windows color picker) or "Presets" \u2014 not only typing hex
\u2022 Double click or "\u2192 RFID tab" \u2014 use the spool for tag writing (important:
  the filament ID in the spool helps; then "Write tag")
\u2022 CFS slot (1A\u20131D) \u2014 only used for print/deduction, not required to write tags from PC
\u2022 RFID chips: main UID + extra chips; "Remove chip" / "Disconnect all"
\u2022 Remaining weight, deduct consumption, history \u2014 grams are logged
\u2022 Duplicate \u2014 copy a spool (new tag possible)
\u2022 Warning \u2014 remaining below threshold (settings) is highlighted

Tab: Printer \u2192 Filament
------------------------
\u2022 Live CFS 1A\u20131D with color and linked spool from "My spools"
\u2022 Spool \u2014 assign an inventory spool to a slot (auto by RFID ID when possible)
\u2022 RFID \u2014 use the slot material in the RFID tab
\u2022 After print end \u2014 ask for consumption; grams from slicer comment (G-code file in data/gcode_cache/ or Downloads)
\u2022 Unrealistic printer values (<4 g) are ignored \u2014 the slicer header is used instead


Tab: Settings
-------------
\u2022 Automation (read, write, batch mode) \u2014 same as RFID tab
\u2022 Launch with Creality Print \u2014 background watcher opens TD Filament Studio when Creality Print runs
\u2022 Serial number \u2014 fixed or auto-incrementing
\u2022 NFC reader \u2014 preferred reader name (empty = first found)
\u2022 DB merge \u2014 on conflict keep local or cloud (protected profiles excluded)
\u2022 First-time setup\u2026 \u2014 show the start checklist again
\u2022 Spools & CFS \u2014 remaining-warning threshold; pin spool to 1A\u20131D for correct deduction
\u2022 Ask filament after print \u2014 automatic deduction dialog (settings tab)
\u2022 Tag protection \u2014 warn before overwriting (settings tab)
\u2022 Multi color \u2014 multiple rows in the deduction dialog (one per color with consumption > 0 g)
\u2022 Check for updates on start \u2014 compares with the GitHub releases of your repo (Navigation \u2192 Check for updates)
\u2022 Error log \u2014 data/app.log on crashes

First-time setup
----------------
On first launch: checklist (smartcard, reader, database, tag type).
"Done" without "show on every start" stores the completion in app_settings.json.


Tab: Help
---------
\u2022 Program guide \u2014 this text
\u2022 JSON kvParam \u2014 every field of the material database (searchable)
\u2022 G-code M commands \u2014 reference (Marlin/Klipper, Creality macros)


Status bar (bottom)
-------------------
\u2022 Short messages (Ready, Connected, Error \u2026)
\u2022 Log \u2014 toggle the message history (optional)
\u2022 Settings, manual (smartcard), start smartcard


Supported printers
------------------
TD Filament Studio is designed for the Creality K2 with CFS (open K2 RFID format).

Fully supported (RFID tags, CFS, live control WebSocket :9999, material DB):
\u2022 K2 Pro
\u2022 K2 Plus
\u2022 K2
\u2022 K2 Max
\u2022 K2 SE

Not supported by this app (different RFID/UI world):
\u2022 K1 / K1 Max / K1C / K1 SE
\u2022 Creality Hi / other vendors without K2 CFS

Dropdowns and "Manage printers" only offer the K2 models above.


Manage printers (Extras menu)
-----------------------------
Store multiple printers: name, IP, model (K2 list only), SSH password.
"Apply" sets IP, password and model in the app.


Smartcard service (Windows)
---------------------------
Without the running "Smart Card" service (SCardSvr) NFC will not work.
\u2022 Win+R \u2192 services.msc \u2192 Smart Card \u2192 Restart
\u2022 Or in the status bar: "Restart (UAC)" / "Start smartcard"
The RFID reader is only required to read/write tags \u2014 not for the service test.


Printer SSH (K2)
----------------
User: root
Default password is often: creality_2024
On the printer: Settings \u2192 enable root account
DB path: /mnt/UDISK/creality/userdata/box/material_database.json
Display menu path: \u2026/material_options.json (brand list on the touchscreen)


RFID tag on the spool
---------------------
\u2022 Place the chip on the flange, about 25 mm from the outer rim \u2014 not on the hub
\u2022 1 tag is often enough; recommended: 2 tags (left + right), write both identically
\u2022 Write from the PC: pick the material in the app \u2014 no need to put the spool in the CFS
\u2022 For printing: thread into the CFS; enable RFID detection in Creality Print
\u2022 On the PC: place the tag flat on the NFC reader to read/write

3D holder (download)
--------------------
RFID tag tab \u2192 "Save tag holder STL\u2026"
Saves the bundled STL files (body + 1A\u20131D) for 25 mm MIFARE tags.

Tag holder (plastic spool) on Thingiverse:
  https://www.thingiverse.com/thing:7356949
on official Creality plastic spools (print 2x complete per spool).

RFID tag tab \u2192 "Tag holder (links)\u2026" (or Navigation \u2192 Tag holder (links)\u2026)
More models in the browser (download STL/3MF yourself):

\u2022 Creality spool Hex incl. RFID compartment \u2014 Printables (print the whole spool)
  https://www.printables.com/model/1204576-creality-cfs-rfid-reusable-spool-hex

\u2022 Creality cardboard spools (K2/CFS) \u2014 Printables (cardboard only, not plastic)
  https://www.printables.com/model/1159112-k2-cfs-rdif-tag-holder-for-creality-cardboard-spoo

\u2022 Creality Cloud \u2014 cardboard spools (3MF)
  https://www.crealitycloud.com/model-detail/rfid-cfs-tag-holders-cardboard-spools

\u2022 AMOYBABY / Flashforge spools \u2014 Printables
  https://www.printables.com/model/1220708-creality-cfs-rfid-spool-tab

\u2022 Extrudr spools \u2014 Printables
  https://www.printables.com/model/1151473-creality-cfs-rfid-tag-holder-for-extrudr-spools

\u2022 Universal (2x per spool, glue on) \u2014 Printables
  https://www.printables.com/model/1280735-cfs-rfid-tag-for-spools

Print 2x per spool (PLA/PETG, 0.2 mm). Insert or glue the tag after writing.


Updates (GitHub)
----------------
Navigation \u2192 "Check for updates" or Settings \u2192 "Check for updates on start".

The app queries the latest release on GitHub (repo in creality_nfc/config.py:
GITHUB_RELEASES_REPO). If a newer version is available, a dialog appears \u2014
"Open in browser" goes to the release page or direct download (setup EXE if
uploaded as a release asset).

On GitHub, create one release per version, tag e.g. v1.5.52-stable, asset:
installer_output/TD-Filament-Studio-Setup.exe (or dist/TD Filament Studio.exe).


Files (data/)
-------------
\u2022 k2_pro.json \u2014 material DB per printer model
\u2022 spools.json \u2014 my spools
\u2022 app_settings.json \u2014 app settings
\u2022 printers.json \u2014 saved printers
\u2022 printer_settings.json \u2014 last selected printer
"""


PROGRAM_HELP_EN_PRINTER_ONLY_REPLACEMENTS = [
    (
        "\u2022 Edit profile / New profile\u2026 / Load database\u2026",
        "\u2022 Edit profile (view) / Load database\u2026 \u2014 list only \"From printer (SSH)\"; no \"New profile\".",
    ),
    (
        """Tab: Filament profile
---------------------
Edit the print parameters in the material database (not on the RFID tag).
\u2022 Selection: \"RFID tag\" tab \u2192 brand and material (with ID in the list)
\u2022 Tabs: Basic (ID, brand, name, type, min/max \u00b0C), print parameters, JSON (kvParam)
\u2022 \"Protect from cloud/printer updates\" \u2014 keeps your own temperatures during cloud merge
\u2022 Save to database \u2014 local only (k2_pro.json); printer is not overwritten

Important: several profiles can share the same 5-digit ID (e.g. three \u00d7 \"06001\").
Always pick the exact material from the list (name \u00b7 ID), otherwise the temperatures will be wrong.""",
        """Tab: Filament profile
---------------------
Shows the print parameters from the material database (loaded via \"From printer\") \u2014 not on the RFID tag.
You change parameters in Creality Print / on the printer; in TD Studio the section is read-only (no save).

\u2022 Selection: \"RFID tag\" tab \u2192 brand and material (with ID in the list)
\u2022 Tabs: Basic, print parameters, JSON (kvParam) \u2014 view only, fields are locked

Important: several profiles can share the same 5-digit ID (e.g. three \u00d7 \"06001\").
Always pick the exact material from the list (name \u00b7 ID), otherwise the temperatures will be wrong.""",
    ),
    (
        """Tab: Material database
----------------------
\u2022 Cloud \u2014 official Creality profiles (internet)
\u2022 From printer \u2014 load from the K2 via SSH (read-only; enable root, same WiFi)
\u2022 Merge cloud \u2014 insert cloud profiles into the local DB
\u2022 Import slicer profiles\u2026 \u2014 Orca/Creality JSON (notes: {\"id\",\"vendor\",\"type\",\"name\"})
\u2022 Printer SSH \u2014 IP and password inside the tab
\u2022 Printer dashboard \u2014 status, compare DB, material_options.json, reboot

File menu
\u2022 Open DB / Save DB as\u2026""",
        """Tab: Material database
----------------------
Printer only (no cloud/file import in this version). Local copy: data/k2_pro.json.

Buttons
\u2022 \"From printer (SSH)\" \u2014 load material_database.json from the K2 (enable root, same WiFi).
  Creality Print sync alone is not enough \u2014 still run \"From printer (SSH)\" afterwards.
\u2022 \"Change material ID\u2026\" \u2014 pick profile in the dropdown, new 5-digit ID, optionally write to the K2.
  Important when IDs collide (e.g. CR-PETG and custom profile both 06001): assign a unique ID.
\u2022 \"Clear local & reload\" \u2014 deletes only k2_pro.json, then fresh SSH load (printer unchanged).
\u2022 \"Clear printer DB\u2026\" \u2014 deletes all profiles on the K2 (two warnings); then sync from Creality Print.
\u2022 Import CFS-RFID ZIP \u2014 backup with an older database.

Profile list
\u2022 Click a row \u2192 green highlight, label above \"Selected: brand \u2014 name (ID \u2026)\".
\u2022 Clear search or entries may be hidden. Double-click = use profile on RFID tab.
\u2022 \"Use for RFID\" / \"Edit profile (view)\".

Creality Print \u2014 custom filaments
\u2022 Create under \"Custom filaments\"; sync to the K2 in Creality Print.
\u2022 They appear in TD Studio only after \"From printer (SSH)\".
\u2022 JSON notes in Creality are often unreliable \u2014 prefer \"Change material ID\u2026\" in TD Studio.

\"Printer\" tab / SSH
\u2022 IP, password (K2 often creality_2024), dashboard: compare DB, reboot.

File menu
\u2022 No \"Open DB\" / \"Save DB as\" for the material DB.""",
    ),
    (
        """Tab: My spools
--------------
Local inventory (data/spools.json): list on the left, edit on the right.
\u2022 \"From material DB\u2026\" \u2014 pick a profile (label always \"Brand \u2014 Material\", printer e.g. K2 Pro instead of F008)
\u2022 List: CFS 1A\u20131D on top (slot field or note CFS-S1\u2026), then alphabetically
\u2022 Color: \"Color\u2026\" (Windows color picker) or \"Presets\" \u2014 not only typing hex
\u2022 Double click or \"\u2192 RFID tab\" \u2014 use the spool for tag writing (important:
  the filament ID in the spool helps; then \"Write tag\")
\u2022 CFS slot (1A\u20131D) \u2014 only used for print/deduction, not required to write tags from PC
\u2022 RFID chips: main UID + extra chips; \"Remove chip\" / \"Disconnect all\"
\u2022 Remaining weight, deduct consumption, history \u2014 grams are logged
\u2022 Duplicate \u2014 copy a spool (new tag possible)
\u2022 Warning \u2014 remaining below threshold (settings) is highlighted""",
        """Tab: My spools
---------------
Local inventory (data/spools.json): scrollable list left, edit right.

List (all columns readable)
\u2022 Columns: color, CFS, label, brand, material, ID, weight, rest g, serial, tag UID, notes.
\u2022 Scroll horizontally at the bottom if the window is narrow.
\u2022 ID column = 5-digit filament ID (update here and in the form after \"Change material ID\u2026\").
\u2022 CFS 1A\u20131D sorted on top; green row = selection.

Editing
\u2022 \"From material DB\u2026\" \u2014 pick a profile.
\u2022 Filament ID (5 digits) in the form \u2014 must match RFID tag and printer DB.
\u2022 Color: \"Color\u2026\" or presets.
\u2022 Double-click or \"\u2192 RFID tab\" \u2014 prepare tag write.
\u2022 CFS slot, multiple tag UIDs, remaining weight, deduct usage, log, duplicate.""",
    ),
    (
        "\u2022 DB merge \u2014 on conflict keep local or cloud (protected profiles excluded)",
        "\u2022 Material DB from the printer only (no cloud merge in this version)",
    ),
    (
        """Updates (GitHub)
----------------
Navigation \u2192 \"Check for updates\" or Settings \u2192 \"Check for updates on startup\".

The app queries the latest GitHub release (repo in creality_nfc/config.py:
GITHUB_RELEASES_REPO). If a newer version is available, a dialog appears \u2014
\"Open in browser\" opens the release page or direct download (setup EXE when uploaded).

Create a GitHub release per version, tag e.g. v1.5.52-stable, asset:
installer_output/TD-Filament-Studio-Setup.exe (or dist/TD Filament Studio.exe).""",
        """Updates (GitHub)
----------------
Navigation \u2192 \"Check for updates\" (only when newer) or \"Re-download setup (repair)\".

\u2022 Download & install: single setup window; version is verified on download.
\u2022 Setup also in %LOCALAPPDATA%\\TD Filament Studio\\Updates\\
\u2022 Settings \u2192 \"Check for updates on startup\"

Releases: github.com/thorsten76dudd-cloud/td-filament-studio (tag e.g. v1.5.148-stable).""",
    ),
]
