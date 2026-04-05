import json
import os
import time
from pathlib import Path

import playwright.sync_api


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
        """返回 (BrowserContext, Browser)。内部决定 headless / headed。"""
        if self.is_cookie_valid():
            # headless + 加载已有 session
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(self.state_file))
            page = context.new_page()
            page.goto(target_url)
            # 短暂等待后检查是否仍在 Cloudflare 页面（cookie 可能已失效）
            page.wait_for_timeout(3000)
            if page.title() not in ("Just a moment...", "请稍候…"):
                return context, browser
            # Cookie 失效，关闭 headless 改用 headed 重新验证
            browser.close()

        # headed，用户手动通过 Cloudflare 验证
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(target_url)
        # 等待 Cloudflare checkbox 出现并点击
        try:
            page.wait_for_selector(
                "input[type='checkbox']", timeout=10000
            )
            page.click("input[type='checkbox']")
        except Exception:
            pass  # 没有 checkbox，继续等待 video
        # 等待视频元素出现（验证完成）
        try:
            page.wait_for_selector("video", timeout=30000)
        except Exception:
            raise VideoParseError(
                "Cloudflare 验证超时，请重试"
            )
        # 保存 session
        context.storage_state(path=str(self.state_file))
        return context, browser
