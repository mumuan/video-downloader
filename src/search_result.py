from dataclasses import dataclass


@dataclass
class SearchResult:
    video_id: str
    title: str
    thumbnail: str
    duration: int  # in seconds
    detail_url: str

    @property
    def formatted_duration(self) -> str:
        """Return duration in HH:MM:SS or MM:SS format."""
        d = int(self.duration)
        if d == 0:
            return "0:00"
        hours, remainder = divmod(d, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
