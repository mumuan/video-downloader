import yt_dlp
from src.video_info import VideoInfo

class YoutubeParser:
    def _normalize_url(self, raw: str) -> str:
        # Accept youtu.be/ID, youtube.com/watch?v=ID, or bare ID
        raw = raw.strip()
        if raw.startswith("youtu.be/"):
            return f"https://www.youtube.com/watch?v={raw.split('/')[-1]}"
        if raw.startswith("https://www.youtube.com/watch?v="):
            return raw
        if raw.startswith("https://youtube.com/watch?v="):
            return raw.replace("https://youtube.com", "https://www.youtube.com")
        # Assume it's a bare video ID
        if len(raw) == 11 and not raw.startswith("http"):
            return f"https://www.youtube.com/watch?v={raw}"
        return raw

    def parse(self, raw_input: str) -> VideoInfo:
        url = self._normalize_url(raw_input)
        ydl_opts = {'skip_download': True, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_id = info.get('id', '')
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', '')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        output_filename = f"{safe_title}_youtube_{video_id}.mp4"

        return VideoInfo(
            bv_id=video_id,
            title=title,
            duration=duration,
            thumbnail=thumbnail,
            output_filename=output_filename,
            source_site="youtube",
            direct_url=None,
        )