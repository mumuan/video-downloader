import importlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

from curl_cffi import requests as curl_requests

from src.i18n import _


class VideoParseError(Exception):
    pass


def _get_bundled_playwright_browsers_path() -> Path | None:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "ms-playwright"
        if candidate.exists():
            return candidate
    return None


def _get_system_playwright_browsers_path() -> Path | None:
    env_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate

    bundled = _get_bundled_playwright_browsers_path()
    if bundled is not None:
        return bundled

    base = Path(os.path.expanduser("~")) / "AppData" / "Local" / "ms-playwright"
    if not base.exists():
        return None

    if any(path.name.startswith("chromium") for path in base.iterdir()):
        return base
    return None


def _find_python_site_packages() -> Path | None:
    if getattr(sys, "frozen", False):
        return None

    candidates: list[Path] = []
    current = Path(sys.executable)
    if current.name.lower() == "python.exe":
        candidates.append(current.parent / "Lib" / "site-packages")

    user = Path(os.path.expanduser("~"))
    candidates.extend(
        [
            user / "AppData" / "Local" / "Programs" / "Python" / "Python312" / "Lib" / "site-packages",
            user / "AppData" / "Local" / "Programs" / "Python" / "Python311" / "Lib" / "site-packages",
            user / "AppData" / "Local" / "Programs" / "Python" / "Python310" / "Lib" / "site-packages",
            user / "AppData" / "Roaming" / "Python" / "Python312" / "site-packages",
            user / "AppData" / "Roaming" / "Python" / "Python311" / "site-packages",
            user / "AppData" / "Roaming" / "Python" / "Python310" / "site-packages",
            Path("C:/Python312/Lib/site-packages"),
            Path("C:/Python311/Lib/site-packages"),
            Path("C:/Python310/Lib/site-packages"),
        ]
    )

    for candidate in candidates:
        if candidate.exists() and (candidate / "playwright").exists():
            return candidate
    return None


def _ensure_playwright_importable():
    if importlib.util.find_spec("playwright") is not None:
        return
    site_packages = _find_python_site_packages()
    if site_packages and str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))


def _is_playwright_python_installed() -> bool:
    if importlib.util.find_spec("playwright") is not None:
        return True
    if getattr(sys, "frozen", False):
        return True
    site_packages = _find_python_site_packages()
    return site_packages is not None and (site_packages / "playwright").exists()


class CurlSessionManager:
    def __init__(self):
        app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
        self.cookie_dir = Path(app_data) / "missav-downloader" / "cookies"
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = self.cookie_dir / "cookies.json"

    def _load_cookies(self) -> dict[str, list[dict]]:
        if not self.cookie_file.exists():
            return {}
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return {}

        if not isinstance(data, dict):
            return {}

        normalized: dict[str, list[dict]] = {}
        for domain, value in data.items():
            if isinstance(value, list):
                normalized[domain] = value
            elif isinstance(value, dict):
                normalized.setdefault("current", []).append(value)
        return normalized

    def _save_cookies(self, cookies: dict[str, list[dict]]):
        self.cookie_file.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")

    def is_cookie_valid(self) -> bool:
        cookies = self._load_cookies()
        for domain_cookies in cookies.values():
            for cookie in domain_cookies:
                if cookie.get("name") == "cf_clearance":
                    expires = cookie.get("expires", 0) or 0
                    if expires - time.time() > 3600:
                        return True
        return False

    def get_session(self, target_url: str) -> curl_requests.Session | None:
        session = curl_requests.Session(impersonate="chrome", timeout=30)

        if self.is_cookie_valid():
            cookies = self._load_cookies()
            for domain, domain_cookies in cookies.items():
                for cookie in domain_cookies:
                    session.cookies.set(
                        cookie["name"],
                        cookie["value"],
                        domain=None if domain == "current" else domain,
                        path=cookie.get("path", "/"),
                    )
            try:
                response = session.get(target_url)
                if response.status_code == 200 and "cloudflare" not in response.text.lower():
                    return session
            except Exception:
                pass

        for attempt in range(3):
            try:
                response = session.get(target_url)
                if response.status_code == 200 and "cloudflare" not in response.text.lower():
                    saved = {"current": []}
                    for name, value in session.cookies.items():
                        saved["current"].append(
                            {"name": name, "value": value, "domain": "current", "path": "/"}
                        )
                    self._save_cookies(saved)
                    return session
            except Exception:
                pass

            if attempt < 2:
                time.sleep(2)
                session = curl_requests.Session(impersonate="chrome", timeout=30)

        return None


class PlaywrightSessionManager:
    def __init__(self):
        app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
        self.cookie_dir = Path(app_data) / "missav-downloader" / "cookies"
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.cookie_dir / "cloudflare_state.json"

    def is_available(self) -> bool:
        return _get_system_playwright_browsers_path() is not None and _is_playwright_python_installed()

    def is_cookie_valid(self) -> bool:
        if not self.state_file.exists():
            return False
        try:
            with open(self.state_file, "r", encoding="utf-8") as handle:
                state = json.load(handle)
        except (json.JSONDecodeError, OSError):
            return False

        for cookie in state.get("cookies", []):
            if cookie.get("name") == "cf_clearance":
                expires = cookie.get("expires", 0) or 0
                if expires - time.time() > 3600:
                    return True
        return False

    def get_browser(self, target_url: str):
        import asyncio

        asyncio.set_event_loop(None)

        browsers_path = _get_system_playwright_browsers_path()
        if browsers_path:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)

        _ensure_playwright_importable()
        playwright = importlib.import_module("playwright.sync_api")
        p = playwright.sync_playwright().start()

        launch_options = {"headless": True}
        chromium_path = self._find_chromium_executable(browsers_path)
        if chromium_path is not None:
            launch_options["executable_path"] = str(chromium_path)

        try:
            stealth_module = importlib.import_module("playwright_stealth.stealth")
            stealth_module.Stealth().hook_playwright_context(p)
        except Exception:
            pass

        if self.is_cookie_valid():
            browser = p.chromium.launch(**launch_options)
            context = browser.new_context(storage_state=str(self.state_file))
            page = context.new_page()
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000)
                if page.title() not in ("Just a moment...", "请稍候…"):
                    return context, browser, p
            except Exception:
                pass
            browser.close()

        for attempt in range(5):
            browser = p.chromium.launch(headless=True, **launch_options)
            context = browser.new_context()
            page = context.new_page()
            try:
                # Use domcontentloaded for Cloudflare pages
                page.goto(target_url, wait_until="domcontentloaded", timeout=90000)
                # Wait for Cloudflare challenge to resolve
                page.wait_for_load_state("networkidle", timeout=60000)
                context.storage_state(path=str(self.state_file))
                return context, browser, p
            except Exception:
                if attempt == 4:
                    browser.close()
                    raise VideoParseError(_("Cloudflare verification failed, please try again later"))
                page.wait_for_timeout(5000)
                try:
                    browser.close()
                except Exception:
                    pass
                continue

        raise VideoParseError(_("Cloudflare verification timed out, please try again later"))

    @staticmethod
    def _find_chromium_executable(browsers_path: Path | None) -> Path | None:
        if browsers_path is None or not browsers_path.exists():
            return None

        for subdir in sorted(browsers_path.iterdir(), reverse=True):
            if not subdir.is_dir() or not subdir.name.startswith("chromium-"):
                continue
            if "headless" in subdir.name:
                continue

            candidates = [
                subdir / "chrome-win" / "chrome.exe",
                subdir / "chrome-win64" / "chrome.exe",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
        return None
