# scripts/build_windows_exe.py
import sys
import os
from pathlib import Path

# Fix Intel OpenMP duplicate runtime dll conflict
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import PyInstaller.__main__

def build_exe():
    print("============================================================")
    print("   NUR TRADING BOT — DESKTOP COMPILATION (PyInstaller)")
    print("============================================================")
    
    # Verify required assets exist
    dist_dir = PROJECT_ROOT / "dashboard" / "dist"
    model_file = PROJECT_ROOT / "rl" / "models" / "ppo_xauusd.zip"
    
    if not dist_dir.exists():
        print(f"Error: Production React Dashboard build not found at: {dist_dir}")
        print("Please run 'npm run build' inside the 'dashboard' folder first.")
        sys.exit(1)
        
    if not model_file.exists():
        print(f"Error: RL model zip not found at: {model_file}")
        sys.exit(1)

    import stable_baselines3
    sb3_dir = Path(stable_baselines3.__file__).parent
    sb3_version_file = sb3_dir / "version.txt"

    print("Bundling resources:")
    print(f"  - React static files: {dist_dir} -> dashboard/dist")
    print(f"  - RL Model: {model_file} -> rl/models/ppo_xauusd.zip")
    print(f"  - SB3 Version: {sb3_version_file} -> stable_baselines3/version.txt")
    print("Running PyInstaller compiler...")

    # PyInstaller arguments
    pyinstaller_args = [
        str(PROJECT_ROOT / 'desktop_app.py'),
        '--onefile',
        '--noconsole',
        '--name=nur-bot-desktop',
        f'--add-data={dist_dir};dashboard/dist',
        f'--add-data={model_file};rl/models',
        f'--add-data={sb3_version_file};stable_baselines3',
        '--hidden-import=stable_baselines3',
        '--hidden-import=stable_baselines3.common.on_policy_algorithm',
        '--hidden-import=gymnasium',
        '--hidden-import=pystray',
        '--hidden-import=pystray._win32',
        '--hidden-import=pystray._util',
        '--hidden-import=pystray._util.win32',
        '--hidden-import=webview',
        '--hidden-import=pythonnet',
        '--hidden-import=clr_loader',
        '--hidden-import=PIL',
        '--hidden-import=PIL.ImageDraw',
        '--hidden-import=fastapi',
        '--hidden-import=fastapi.staticfiles',
        '--hidden-import=jwt',
        '--hidden-import=bcrypt',
        '--hidden-import=uvicorn',
        '--hidden-import=websockets',
        '--hidden-import=pandas',
        '--hidden-import=numpy',
        '--hidden-import=sqlite3',
        '--hidden-import=MetaTrader5',
        '--exclude-module=PyQt5',
        '--exclude-module=PyQt6',
        '--exclude-module=PySide2',
        '--exclude-module=PySide6',
    ]

    try:
        PyInstaller.__main__.run(pyinstaller_args)
        print("\n============================================================")
        print("   COMPILATION SUCCESSFUL!")
        print("   Executable located at: dist/nur-bot-desktop.exe")
        print("============================================================")
    except Exception as exc:
        print(f"\nCompilation failed: {exc}")
        sys.exit(1)

if __name__ == '__main__':
    build_exe()
