---
title: "Unknown format code 'd' for object of type 'float' in formatted_duration"
date: 2026-04-05
category: docs/solutions/runtime-errors
module: bilibili-video-downloader
problem_type: runtime_error
component: tooling
symptoms:
  - "Unknown format code 'd' for object of type 'float' when parsing Bilibili video URL"
  - "GUI shows error popup: 解析时发生错误：Unknown format code 'd' for object of type 'float'"
root_cause: logic_error
resolution_type: code_fix
severity: medium
tags: [yt-dlp, duration, float, dataclass, bilibili]
---

# "Unknown format code 'd' for object of type 'float'" in formatted_duration

## Problem

When parsing a Bilibili video URL in the PyQt6 GUI, the application crashed with the error:

```
解析时发生错误：Unknown format code 'd' for object of type 'float'
```

The error appeared immediately after yt-dlp extracted video metadata and the app attempted to display the video info panel.

## Symptoms

- Error popup in GUI: "解析时发生错误：Unknown format code 'd' for object of type 'float'"
- Parsing succeeded in CLI test but failed when displaying in the GUI
- yt-dlp extracted duration as a float (e.g., `4869.48`) for real Bilibili videos

## What Didn't Work

- The dataclass field `duration: int` was correct as a type annotation
- yt-dlp correctly returns duration as a float — this is expected behavior
- The CLI test with integer duration passed, masking the issue

## Solution

Cast `self.duration` to `int` in `formatted_duration` before performing divmod arithmetic:

```python
# src/video_info.py — BEFORE (broken)
@property
def formatted_duration(self) -> str:
    if self.duration == 0:
        return "0:00"
    hours, remainder = divmod(self.duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

# AFTER (fixed)
@property
def formatted_duration(self) -> str:
    duration = int(self.duration)  # ← cast float to int
    if duration == 0:
        return "0:00"
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"
```

Also add tests to catch float durations:

```python
# tests/test_video_info.py
def test_formatted_duration_float():
    # yt-dlp returns duration as float (e.g. 4869.48)
    info = VideoInfo(bv_id="BV1", title="t", duration=4869.48, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "1:21:09"

def test_formatted_duration_hours():
    info = VideoInfo(bv_id="BV1", title="t", duration=3661, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "1:01:01"
```

## Why This Works

`divmod()` with a float argument produces float results. The f-string then tried to apply `%02d` (integer format) to those float values, causing `"Unknown format code 'd' for object of type 'float'"`. Casting to `int` first ensures the divmod chain operates on integers, producing the correct string format.

## Prevention

- Always test dataclass properties with the actual data types returned by external libraries (yt-dlp in this case), not just the annotated types
- Add boundary-value tests: zero, seconds, minutes, hours, and fractional values for time/duration fields
- yt-dlp's `duration` field is documented as a float — assume any external library returns floats for numeric fields unless explicitly documented otherwise
