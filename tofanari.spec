# -*- mode: python ; coding: utf-8 -*-
"""ToFanari PyInstaller spec. Uses onedir mode for reliable startup."""

import os
_block_cipher = None
try:
    script_dir = os.path.dirname(os.path.abspath(SPEC))
except NameError:
    script_dir = os.path.abspath(os.curdir)

a = Analysis(
    ['app.py'],
    pathex=[script_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'config',  # version source of truth
        'marker_matching',  # PDF/audio workflow + JSON (ensure bundled if graph misses)
        'bunny_preparation',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, cipher=_block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ToFanari',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX can cause "Failed to start embedded python interpreter" on Windows
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ToFanari',
)
