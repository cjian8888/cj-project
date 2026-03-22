# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys


project_root = Path(SPECPATH).resolve()
sys.path.insert(0, str(project_root))

from build_windows_package import get_pyinstaller_datas, get_pyinstaller_hiddenimports


datas = get_pyinstaller_datas(project_root)
hiddenimports = get_pyinstaller_hiddenimports()


a = Analysis(
    [str(project_root / "api_server.py")],
    pathex=[str(project_root)],
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
    name="fpas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="fpas-offline",
)
