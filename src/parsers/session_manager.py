import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from curl_cffi import requests as curl_requests


class VideoParseError(Exception):
    """解析视频信息时出错"""
    pass


def _get_system_playwright_browsers_path() -> Path | None:
    """获取系统已安装的 Playwright 浏览器路径（如果有）"""
    base = Path(os.path.expanduser("~")) / "AppData" / "Local" / "ms-playwright"
    if base.exists():
        for sub in ["chromium_headless_shell-1208", "chromium-1208"]:
            if (base / sub).exists():
                return base
    return None


def _find_python_site_packages() -> Path | None:
    """从系统 Python 找到 site-packages 路径"""
    # 方法1: 尝试从 sys.executable 推断（如果当前是 Python）
    python_exe = sys.executable
    if python_exe and Path(python_exe).name == "python.exe":
        # py.exe 或 python.exe 安装的 Python
        ver = Path(python_exe).parent.name  # e.g. "Python312"
        sp = Path(python_exe).parent / "Lib" / "site-packages"
        if sp.exists():
            return sp

    # 方法2: 搜索常见路径
    user = Path(os.path.expanduser("~"))
    common_bases = [
        user / "AppData" / "Local" / "Programs" / "Python",
        user / "AppData" / "Local" / "Programs",
        Path("C:\\Python312"),
    ]
    for base in common_bases:
        if not base.exists():
            continue
        for py_ver in ["Python312", "Python311", "Python310"]:
            sp = base / py_ver / "Lib" / "site-packages"
            if sp.exists():
                # 验证 playwright 存在
                if (sp / "playwright").exists():
                    return sp
                # 也检查 user site-packages
            user_sp = user / "AppData" / "Roaming" / "Python" / py_ver / "site-packages"
            if user_sp.exists() and (user_sp / "playwright").exists():
                return user_sp

    return None


def _ensure_playwright_importable():
    """将系统 Python 的 site-packages 接入 sys.path"""
    sp = _find_python_site_packages()
    if sp and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))


def _is_playwright_python_installed() -> bool:
    """检查 playwright Python 包是否已安装"""
    sp = _find_python_site_packages()
    return sp is not None and (sp / "playwright").exists()


class CurlSessionManager:
    """使用 curl_cffi 模拟浏览器指纹的 Cloudflare bypass"""

    def __init__(self):
        app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
        self.cookie_dir = Path(app_data) / "missav-downloader" / "cookies"
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = self.cookie_dir / "cookies.json"

    def _load_cookies(self) -> dict:
        if not self.cookie_file.exists():
            return {}
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_cookies(self, cookies: dict):
        self.cookie_file.write_text(json.dumps(cookies, ensure_ascii=False), encoding="utf-8")

    def is_cookie_valid(self) -> bool:
        cookies = self._load_cookies()
        for domain_cookies in cookies.values():
            for cookie in domain_cookies:
                if cookie.get("name") == "cf_clearance":
                    expires = cookie.get("expires", 0)
                    if expires - time.time() > 3600:
                        return True
        return False

    def get_session(self, target_url: str) -> curl_requests.Session | None:
        """返回一个 curl_cffi Session，自动绕过 Cloudflare。失败返回 None。"""
        session = curl_requests.Session(impersonate="chrome", timeout=30)

        if self.is_cookie_valid():
            cookies = self._load_cookies()
            for domain, domain_cookies in cookies.items():
                for cookie in domain_cookies:
                    session.cookies.set(
                        cookie["name"],
                        cookie["value"],
                        domain=domain if domain != "current" else None,
                        path=cookie.get("path", "/"),
                    )
            try:
                resp = session.get(target_url)
                if resp.status_code == 200 and "cloudflare" not in resp.text.lower():
                    return session
            except Exception:
                pass

        for attempt in range(3):
            try:
                resp = session.get(target_url)
                if resp.status_code == 200 and "cloudflare" not in resp.text.lower():
                    saved = {}
                    for name, value in session.cookies.items():
                        saved[name] = {"name": name, "value": value, "domain": "current", "path": "/"}
                    self._save_cookies(saved)
                    return session
            except Exception:
                if attempt == 2:
                    break
                time.sleep(2)
                session = curl_requests.Session(impersonate="chrome", timeout=30)
                continue

        return None


class PlaywrightSessionManager:
    """当 curl_cffi 失败时，使用系统已安装的 Playwright 浏览器"""

    def __init__(self):
        app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
        self.cookie_dir = Path(app_data) / "missav-downloader" / "cookies"
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.cookie_dir / "cloudflare_state.json"

    def is_available(self) -> bool:
        return (
            _get_system_playwright_browsers_path() is not None
            and _is_playwright_python_installed()
        )

    def is_cookie_valid(self) -> bool:
        if not self.state_file.exists():
            return False
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            for cookie in state.get("cookies", []):
                if cookie.get("name") == "cf_clearance":
                    expires = cookie.get("expires", 0)
                    if expires - time.time() > 3600:
                        return True
            return False
        except (json.JSONDecodeError, OSError):
            return False

    def get_browser(self, target_url: str):
        """返回 (context, browser, playwright)"""
        pw_path = _get_system_playwright_browsers_path()
        if pw_path:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_path)

        # 动态导入：将系统 site-packages 接入后再导入
        _ensure_playwright_importable()
        playwright = importlib.import_module("playwright.sync_api")
        stealth_module = importlib.import_module("playwright_stealth.stealth")

        p = playwright.sync_playwright().start()
        stealth_module.Stealth().hook_playwright_context(p)

        if self.is_cookie_valid():
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(self.state_file))
            page = context.new_page()
            page.goto(target_url)
            page.wait_for_timeout(3000)
            if page.title() not in ("Just a moment...", "请稍候…"):
                return context, browser, p
            browser.close()

        for attempt in range(3):
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(target_url)
            try:
                page.wait_for_selector("video", timeout=20000)
                context.storage_state(path=str(self.state_file))
                return context, browser, p
            except Exception:
                if attempt == 2:
                    browser.close()
                    raise VideoParseError("Cloudflare 验证失败，请稍后重试")
                page.wait_for_timeout(3000)
                browser.close()
                continue

        raise VideoParseError("Cloudflare 验证超时，请稍后重试")
