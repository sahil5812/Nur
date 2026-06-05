# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Abusahil\\OneDrive\\Desktop\\Nur-main\\desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Abusahil\\OneDrive\\Desktop\\Nur-main\\dashboard\\dist', 'dashboard/dist'), ('C:\\Users\\Abusahil\\OneDrive\\Desktop\\Nur-main\\rl\\models\\ppo_xauusd.zip', 'rl/models'), ('C:\\Users\\Abusahil\\OneDrive\\Desktop\\Nur-main\\.venv\\Lib\\site-packages\\stable_baselines3\\version.txt', 'stable_baselines3')],
    hiddenimports=['stable_baselines3', 'stable_baselines3.common.on_policy_algorithm', 'gymnasium', 'pystray', 'pystray._win32', 'pystray._util', 'pystray._util.win32', 'webview', 'pythonnet', 'clr_loader', 'PIL', 'PIL.ImageDraw', 'fastapi', 'fastapi.staticfiles', 'jwt', 'bcrypt', 'uvicorn', 'websockets', 'pandas', 'numpy', 'sqlite3', 'MetaTrader5'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6'],
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
    name='nur-bot-desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
