from dataclasses import dataclass


@dataclass
class VideoInfo:
    bv_id: str
    title: str
    duration: int  # in seconds
    thumbnail: str
    output_filename: str

    @property
    def formatted_duration(self) -> str:
        """Return duration in HH:MM:SS or MM:SS format."""
        duration = int(self.duration)
        if duration == 0:
            return "0:00"

        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
