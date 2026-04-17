"""PyInstaller spec — one-file windowed Windows build.

Invoke via ``python packaging/build.py`` (recommended) or directly:

    pyinstaller dj-auto-sort.spec --noconfirm

``SPECPATH`` is injected by PyInstaller and points at the directory
containing this file.
"""
from __future__ import annotations

import os

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = SPECPATH  # noqa: F821 -- SPECPATH is a PyInstaller global
ENTRY = os.path.join(PROJECT_ROOT, "dj_auto_sort", "main.py")

# Our own package plus a few libs whose imports happen behind lazy probes
# that PyInstaller's static scan misses.
hidden = [
    *collect_submodules("dj_auto_sort"),
    "librosa",
    "soundfile",
    "mutagen",
    "lxml",
    "lxml.etree",
    "pyrekordbox",
]

# Heavyweights the base .exe never needs — analysis-full users install them
# into a separate Python env.
excludes = [
    "essentia",
    "essentia_tensorflow",
    "tensorflow",
    "torch",
    "pytest",
    "pytest_qt",
    "IPython",
    "matplotlib",
    "notebook",
]

a = Analysis(  # noqa: F821
    [ENTRY],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="dj-auto-sort",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
