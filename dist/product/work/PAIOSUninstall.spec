# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\installer\\paios_installer\\__main__.py'],
    pathex=['C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\installer'],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='PAIOSUninstall',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\dist\\product\\work\\version_resource.txt',
    icon=['C:\\Users\\GBSBHL1261\\Documents\\Playwright\\Project\\PAIOS\\assets\\paios.ico'],
)
