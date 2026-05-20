# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = [
    'smartcard.scard',
    'smartcard.CardMonitoring',
    'app.paths',
    'app.constants',
    'app.main_window',
    'ui.panels.filament_editor_panel',
    'ui.panels.spool_panel',
    'ui.panels.help_panel',
    'ui.panels.settings_panel',
    'ui.panels.printer_panel',
    'ui.panels.printer_device_panel',
    'ui.panels.cfs_dashboard',
    'ui.rfid_placement_help',
    'creality_nfc.db_compare',
    'creality_nfc.printer_camera',
    'ui.messaging',
    'ui.theme',
    'ui.components',
    'ui.dialog_theme',
    'ui.help_content',
    'ui.tk_root',
    'ui.dnd_files',
    'tkinterdnd2',
    'creality_nfc.kvparam_docs',
]
hiddenimports += collect_submodules('smartcard')
hiddenimports += collect_submodules('creality_nfc')
hiddenimports += collect_submodules('ui')
hiddenimports += collect_submodules('app')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data'), ('assets', 'assets')] + collect_data_files('tkinterdnd2'),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['vtk', 'vtkmodules', 'pyglet'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TD Filament Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/app_icon.ico',
)
