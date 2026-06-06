import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.parsers.session_manager import (
    _ensure_safe_playwright_driver,
    _get_safe_playwright_driver_dir,
)


def main() -> int:
    _ensure_safe_playwright_driver()
    driver_dir = _get_safe_playwright_driver_dir()
    runtime_dir = ROOT / ".runtime" / "playwright-install"
    safe_browsers_dir = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "xhub-playwright-browsers"
    target_browsers_dir = ROOT / ".playwright-browsers"
    if _has_required_browser_files(target_browsers_dir):
        return 0
    appdata_dir = runtime_dir / "AppData" / "Roaming"
    localappdata_dir = runtime_dir / "AppData" / "Local"
    for path in (runtime_dir, appdata_dir, localappdata_dir):
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(runtime_dir),
            "USERPROFILE": str(runtime_dir),
            "APPDATA": str(appdata_dir),
            "LOCALAPPDATA": str(localappdata_dir),
            "TEMP": str(runtime_dir),
            "TMP": str(runtime_dir),
            "HOMEDRIVE": "C:",
            "HOMEPATH": "\\ProgramData",
            "PLAYWRIGHT_BROWSERS_PATH": str(safe_browsers_dir),
        }
    )
    cmd = [
        str(driver_dir / "node.exe"),
        str(driver_dir / "package" / "cli.js"),
        "install",
        "chromium",
    ]
    code = subprocess.call(cmd, env=env, cwd=str(runtime_dir))
    if code != 0 and not _has_required_browser_files(safe_browsers_dir):
        return code
    target_browsers_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(safe_browsers_dir, target_browsers_dir, dirs_exist_ok=True)
    return 0


def _has_required_browser_files(path: Path) -> bool:
    return (
        path.exists()
        and any(child.name.startswith("chromium-") for child in path.iterdir())
        and any(child.name.startswith("chromium_headless_shell-") for child in path.iterdir())
        and any(child.name.startswith("ffmpeg-") for child in path.iterdir())
    )


if __name__ == "__main__":
    raise SystemExit(main())
