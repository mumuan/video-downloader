import re

from src.i18n import _
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
            raise InvalidVideoURLError(_("Input is empty"))
        if "missav.live" in raw or "missav.ws" in raw:
            return "missav"
        if "bilibili.com" in raw or raw.startswith("BV"):
            return "bilibili"
        raise InvalidVideoURLError(_("Unsupported site, only Bilibili and missav.ws are supported"))

    def parse(self, raw_input: str):
        site = self._detect_site(raw_input)
        if site == "bilibili":
            return BilibiliParser().parse(raw_input)
        elif site == "missav":
            return MissavParser().parse(raw_input)
        else:
            raise InvalidVideoURLError(_("Unsupported site"))
