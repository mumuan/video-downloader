import re

import yt_dlp

from src.i18n import _
from src.video_info import VideoInfo


class BilibiliParser:
    def _normalize_bv_id(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            raise ValueError(_("Input is empty"))
        if raw.startswith("https://") or raw.startswith("http://"):
            if "bilibili.com" not in raw:
                raise ValueError(_("Unsupported site, only Bilibili and missav.ws are supported"))
            match = re.search(r'BV[\w]+', raw)
            if not match:
                raise ValueError(_("Unable to extract BV ID from URL"))
            return match.group(0)
        if raw.startswith("BV"):
            return raw
        raise ValueError(_("Please enter a valid BV ID or Bilibili video URL"))

    def parse(self, raw_input: str) -> VideoInfo:
        bv_id = self._normalize_bv_id(raw_input)
        url = f"https://www.bilibili.com/video/{bv_id}"
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError:
            raise ValueError(_("Download failed, please check if the link is valid"))
        except yt_dlp.utils.ExtractorError:
            raise ValueError(_("Unable to extract video info, please check if the link is valid"))
        if not info:
            raise ValueError(_("Unable to get video info, please check if the link is valid"))
        title = info.get('title', _("Unknown title"))
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', '')
        safe_title = "".join(c for c in title if c not in '<>:"/\\|?*')
        output_filename = f"{safe_title}_bilibili_{bv_id}.mp4"
        return VideoInfo(
            bv_id=bv_id,
            title=title,
            duration=duration,
            thumbnail=thumbnail,
            output_filename=output_filename,
            source_site="bilibili",
            direct_url=None,
        )
