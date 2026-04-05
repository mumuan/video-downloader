import re

from src.parsers.bilibili_parser import BilibiliParser
from src.parsers.missav_parser import MissavParser


class InvalidVideoURLError(ValueError):
    pass


class VideoParser:
    """Factory that routes to the appropriate site-specific parser."""

    def _detect_site(self, raw: str) -> str:
        """Detect site from raw URL or input. Returns 'bilibili', 'missav', or raises InvalidVideoURLError."""
        raw = raw.strip()
        if not raw:
            raise InvalidVideoURLError("输入为空")
        if "missav.live" in raw:
            return "missav"
        if "bilibili.com" in raw or raw.startswith("BV"):
            return "bilibili"
        raise InvalidVideoURLError("不支持的网站，仅支持 Bilibili 和 missav.live")

    def parse(self, raw_input: str):
        site = self._detect_site(raw_input)
        if site == "bilibili":
            return BilibiliParser().parse(raw_input)
        elif site == "missav":
            return MissavParser().parse(raw_input)
        else:
            raise InvalidVideoURLError("不支持的网站")
