"""Render approved GPT storyboard frames into an MP4 with local FFmpeg.

The images are AI generated; the camera movement is local image animation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess


FPS = 24
FRAMES_PER_SEGMENT = 10 * FPS
SIZE = "720x1280"


def tools() -> tuple[str, str]:
    folder = os.environ.get("FFMPEG_BIN")
    if folder:
        path = Path(folder)
        ffmpeg = path / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        ffprobe = path / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if ffmpeg.is_file() and ffprobe.is_file():
            return str(ffmpeg), str(ffprobe)
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("FFmpeg와 FFprobe가 필요합니다. FFMPEG_BIN 또는 PATH를 설정하세요.")
    return ffmpeg, ffprobe


def _motion_filter(motion: str) -> str:
    if motion == "zoom_in":
        zoom, x = "1+on*0.00033", "iw/2-(iw/zoom/2)"
    elif motion == "zoom_out":
        zoom, x = "1.08-on*0.00033", "iw/2-(iw/zoom/2)"
    elif motion == "pan_left":
        zoom, x = "1.08", "(iw-iw/zoom)*(1-on/239)"
    elif motion == "pan_right":
        zoom, x = "1.08", "(iw-iw/zoom)*on/239"
    else:
        raise ValueError("허용되지 않은 화면 움직임입니다.")
    return (
        "scale=800:1422:force_original_aspect_ratio=increase,crop=800:1422,"
        f"zoompan=z='{zoom}':x='{x}':y='ih/2-(ih/zoom/2)':d=1:s={SIZE}:fps={FPS},"
        "format=yuv420p"
    )


def _run(args: list[str], *, cwd: Path) -> bytes:
    try:
        completed = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=240, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError("FFmpeg 실행이 중단됐습니다. 출력은 완료로 표시하지 않습니다.") from None
    if completed.returncode:
        raise ValueError("FFmpeg가 영상을 완성하지 못했습니다. 출력은 완료로 표시하지 않습니다.")
    return completed.stdout


def render(job_dir: Path, segments: list[dict], seconds: int) -> bytes:
    ffmpeg, ffprobe = tools()
    if len(segments) != seconds // 10 or seconds not in (10, 20, 30):
        raise ValueError("10초 구간 구성이 올바르지 않습니다.")
    parts = []
    for index, segment in enumerate(segments, start=1):
        image = job_dir / f"preview-{index:02d}.png"
        if segment.get("preview", {}).get("file") != image.name or not image.is_file() or image.is_symlink():
            raise ValueError("승인한 예시 이미지가 없습니다.")
        output = job_dir / f"part-{index:02d}.mp4"
        if output.exists():
            raise ValueError("기존 영상 조각을 덮어쓸 수 없습니다.")
        _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
              "-loop", "1", "-framerate", str(FPS), "-i", str(image),
              "-vf", _motion_filter(segment["motion"]), "-frames:v", str(FRAMES_PER_SEGMENT),
              "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
              "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)], cwd=job_dir)
        parts.append(output)
    listing = job_dir / "parts.txt"
    listing.write_text("".join(f"file '{item.name}'\n" for item in parts), encoding="utf-8")
    final = job_dir / "video.mp4"
    if final.exists():
        raise ValueError("기존 영상을 덮어쓸 수 없습니다.")
    _run([ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
          "-f", "concat", "-safe", "1", "-i", str(listing), "-c", "copy",
          "-movflags", "+faststart", str(final)], cwd=job_dir)
    raw = _run([ffprobe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height:format=duration",
                "-of", "json", str(final)], cwd=job_dir)
    try:
        info = json.loads(raw)
        stream = info["streams"][0]
        duration = float(info["format"]["duration"])
        if (stream["codec_name"] != "h264" or stream["width"] != 720 or
                stream["height"] != 1280 or abs(duration - seconds) > 0.05):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("완성 영상의 길이·크기·코덱이 목표와 다릅니다.") from None
    return final.read_bytes()
