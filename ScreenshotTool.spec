# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PIL._tkinter_finder',
        'win32api',
        'win32con',
        'win32gui',
        'win32ui',
        'win32clipboard',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['keyboard', 'pystray'],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ScreenshotTool',
    debug=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    uac_admin=True,
    icon=None,
)
