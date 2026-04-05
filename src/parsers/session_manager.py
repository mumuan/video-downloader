import json
import os
import time
from pathlib import Path

import playwright.sync_api
from playwright_stealth import stealth as stealth_module


class VideoParseError(Exception):
    """解析视频信息时出错"""
    pass


class SessionManager:
    """管理 missav.live 的 Cloudflare session cookies"""

    def __init__(self):
        app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
        self.cookie_dir = Path(app_data) / "missav-downloader" / "cookies"
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.cookie_dir / "cloudflare_state.json"

    def is_cookie_valid(self) -> bool:
        """检查 cf_clearance cookie 是否存在且未过期（剩余 >1小时）"""
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

    def get_verified_context(
        self, p: playwright.sync_api.Playwright, target_url: str
    ):
        """返回 (BrowserContext, Browser)。始终使用 stealth headless，自动通过 Cloudflare challenge。"""
        # 应用 stealth 到 playwright 实例（补丁在 p 的生命周期内永久生效）
        stealth_module.Stealth().hook_playwright_context(p)

        # 优先尝试使用已有 cookie
        if self.is_cookie_valid():
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(self.state_file))
            page = context.new_page()
            page.goto(target_url)
            page.wait_for_timeout(3000)
            if page.title() not in ("Just a moment...", "请稍候…"):
                return context, browser
            # challenge 仍在（cookie 实际已失效），关闭并进入重试流程
            browser.close()

        # 无有效 cookie 或 challenge 未通过 → stealth headless 重试
        for attempt in range(3):
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(target_url)
            try:
                page.wait_for_selector("video", timeout=20000)
            except Exception:
                if attempt == 2:
                    browser.close()
                    raise VideoParseError("Cloudflare 验证失败，请稍后重试")
                page.wait_for_timeout(3000)
                browser.close()
                continue
            # 验证通过，保存 session
            context.storage_state(path=str(self.state_file))
            return context, browser

        raise VideoParseError("Cloudflare 验证超时，请稍后重试")
