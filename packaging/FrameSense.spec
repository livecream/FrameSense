# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("mediapipe") + collect_data_files("cv2")
hiddenimports = (
    collect_submodules("mediapipe")
    + collect_submodules("cv2")
    + ["PIL._tkinter_finder"]
)

a = Analysis(
    ["../src/gui.py"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FrameSense",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="FrameSense",
)

app = BUNDLE(
    coll,
    name="FrameSense.app",
    bundle_identifier="com.framesense.app",
)
