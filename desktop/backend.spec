# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'desktop_backend.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'frontend' / 'dist'), 'frontend/dist')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.asyncio',
                   'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan.on'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'ruff', 'enchant'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='vocove-backend',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='vocove-backend')
