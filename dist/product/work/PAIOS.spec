# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules('paios')
hiddenimports += collect_submodules('paios_gui')
hiddenimports += collect_submodules('paios_launcher')
hiddenimports += collect_submodules('segno')


a = Analysis(
    ['C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\launcher\\paios_launcher\\__main__.py'],
    pathex=['C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\backend', 'C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\frontend\\desktop', 'C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\launcher', 'C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\updater'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PAIOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\dist\\product\\work\\version_resource.txt',
    icon=['C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\assets\\paios.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PAIOS',
)
