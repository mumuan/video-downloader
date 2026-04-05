import re

import yt_dlp

from src.video_info import VideoInfo


class InvalidVideoURLError(Exception):
    pass


class VideoParser:
    def _normalize_bv_id(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            raise InvalidVideoURLError("输入为空")
        if raw.startswith("https://") or raw.startswith("http://"):
            if "bilibili.com" not in raw:
                raise InvalidVideoURLError("不支持的网站，仅支持 Bilibili")
            match = re.search(r'BV[\w]+', raw)
            if not match:
                raise InvalidVideoURLError("无法从URL中提取BV号")
            return match.group(0)
        if raw.startswith("BV"):
            return raw
        raise InvalidVideoURLError("请输入有效的 BV号 或 Bilibili 视频链接")

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
            raise InvalidVideoURLError("下载失败，请检查链接是否有效")
        except yt_dlp.utils.ExtractorError:
            raise InvalidVideoURLError("无法提取视频信息，请检查链接是否有效")
        if not info:
            raise InvalidVideoURLError("无法获取视频信息，请检查链接是否有效")
        title = info.get('title', '未知标题')
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
        )