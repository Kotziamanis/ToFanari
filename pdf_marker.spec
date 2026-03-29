# -*- mode: python ; coding: utf-8 -*-
"""
PDF Marker Tool — PyInstaller spec.

- macOS: onedir + BUNDLE → dist/PDF Marker Tool.app (recommended for Gatekeeper).
- Windows: onefile → dist/PDFMarkerTool.exe (build_pdf_marker_windows.bat).
"""

import os
import sys

try:
    _script_dir = os.path.dirname(os.path.abspath(SPEC))
except NameError:
    _script_dir = os.path.abspath(os.curdir)

a = Analysis(
    ['main.py'],
    pathex=[_script_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.ttk',
        'fitz',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='PDFMarkerTool',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=True,
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
        name='PDFMarkerTool',
    )
    app = BUNDLE(
        coll,
        name='PDF Marker Tool.app',
        icon=None,
        bundle_identifier='cy.com.tofanari.pdfmarkertool',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'CFBundleName': 'PDF Marker Tool',
            'CFBundleDisplayName': 'PDF Marker Tool',
            'CFBundleVersion': '1.0.1',
            'CFBundleShortVersionString': '1.0.1',
            'CFBundleDocumentTypes': [
                {
                    'CFBundleTypeName': 'PDF Document',
                    'CFBundleTypeRole': 'Editor',
                    'CFBundleTypeExtensions': ['pdf'],
                    'LSHandlerRank': 'Alternate',
                },
            ],
        },
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='PDFMarkerTool',
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
    )
