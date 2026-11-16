"""Local synthetic media only: color cards, silent audio, sidecar subtitles.

No model, TTS, external media, credentials, or paid production is connected.
The existing mock approval gates this explicitly requested local exercise only.
"""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from src.direction import _canonical
from src.mock_production import _digest, _timestamp, validate_mock_approval


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT / "workspace"
SOURCE = "local_mock_synthetic"
FPS = 24
PAYLOADS = ("video.mp4", "subtitles.srt", "scenes.json", "quality.json")
INPUT_NAMES = ("plan", "direction", "prompts", "pricing", "quote", "approval")


class MockResultValidationError(ValueError):
    """Stable phase information for advisory routing, not an execution grant."""

    def __init__(self, message, check_id, target_stage, next_action):
        super().__init__(message)
        self.check_id = check_id
        self.target_stage = target_stage
        self.next_action = next_action


@contextmanager
def _result_step(check_id, target_stage, next_action):
    try:
        yield
    except MockResultValidationError:
        raise
    except (OSError, ValueError) as error:
        raise MockResultValidationError(str(error), check_id, target_stage, next_action) from error


COLORS = ((28, 65, 112), (73, 43, 99), (28, 90, 68), (108, 49, 35))
GLYPHS = {
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
}


def _linked(path):
    return path.is_symlink() or path.is_junction()


def _result_dir(value, *, new=False):
    path = Path(value)
    if ".." in path.parts:
        raise ValueError("result paths cannot contain parent traversal")
    path = path.absolute()
    base = WORKSPACE.absolute()
    if _linked(base) or not path.is_relative_to(base) or path == base:
        raise ValueError("result directory must be below the project workspace")
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError("result path escapes the workspace")
    for candidate in (path, *path.parents):
        if _linked(candidate):
            raise ValueError("linked result paths are not allowed")
        if candidate == base:
            break
    if new and path.exists():
        raise ValueError("result directory already exists; use a new path")
    if not new and not path.is_dir():
        raise ValueError("result directory is missing")
    return path


def _file(folder, name):
    path = folder / name
    if _linked(path) or not path.is_file() or path.resolve().parent != folder.resolve():
        raise ValueError(f"missing, linked, or unsafe result file: {name}")
    if not 0 < path.stat().st_size <= (100_000_000 if name == "video.mp4" else 2_000_000):
        raise ValueError(f"invalid result file size: {name}")
    return path


def _reject_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate result JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("non-finite result JSON")


def _json_read(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_pairs,
                      parse_constant=_reject_constant)


def _json_write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _run(args, *, cwd=None, binary=False):
    try:
        result = subprocess.run([str(arg) for arg in args], cwd=cwd, shell=False,
                                stdin=subprocess.DEVNULL, capture_output=True,
                                text=not binary, encoding=None if binary else "utf-8",
                                errors=None if binary else "replace", timeout=60,
                                env={"SystemRoot": "C:\\Windows", "WINDIR": "C:\\Windows"})
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("local media tool failed or timed out; no automatic retry") from error
    if result.returncode:
        detail = result.stderr.decode("utf-8", errors="replace") if binary else result.stderr
        raise ValueError("local media tool rejected the input: " + detail[-1000:])
    return result.stdout


def _tools():
    paths = {name: shutil.which(name) for name in ("ffmpeg", "ffprobe")}
    if any(not path for path in paths.values()):
        raise ValueError("local ffmpeg and ffprobe are required; no install or fallback")
    paths = {name: str(Path(path).resolve()) for name, path in paths.items()}
    versions = {name: _run([path, "-version"]).splitlines()[0] for name, path in paths.items()}
    return paths, versions


def _ms(frame):
    return int((Decimal(frame) * 1000 / FPS).to_integral_value(rounding=ROUND_HALF_UP))


def _profile_and_scenes(plan):
    ratio = Fraction(plan["brief"]["aspect_ratio"].replace(":", "/"))
    factor = 640 // (2 * max(ratio.numerator, ratio.denominator))
    width, height = ratio.numerator * 2 * factor, ratio.denominator * 2 * factor
    if min(width, height) < 96 or len(plan["scenes"]) > 60:
        raise ValueError("mock profile supports even 96..640 pixel dimensions and at most 60 scenes")
    cumulative, previous, scenes = Decimal(0), 0, []
    for scene in plan["scenes"]:
        text = scene["script"]
        if "\r" in text or "\n\n" in text or text.startswith("\n") or text.endswith("\n"):
            raise ValueError("mock SRT scripts cannot contain carriage returns or blank edge/paragraph lines")
        cumulative += Decimal(str(scene["duration_seconds"]))
        end = int((cumulative * FPS).to_integral_value(rounding=ROUND_HALF_UP))
        if end <= previous:
            raise ValueError("every mock scene must occupy at least one frame")
        scenes.append({**deepcopy(scene), "start_frame": previous, "end_frame": end,
                       "start_ms": _ms(previous), "end_ms": _ms(end)})
        previous = end
    target = Decimal(str(plan["brief"]["target_seconds"]))
    if abs(Decimal(previous) / FPS - target) > target / 10:
        raise ValueError("quantized mock duration is outside the ±10% target")
    profile = {"schema_version": 1, "fps": FPS, "width": width, "height": height,
               "frame_count": previous, "duration_seconds": previous / FPS,
               "video_codec": "h264", "audio_codec": "aac", "audio_source": "synthetic_silence",
               "scene_rounding": "cumulative nearest frame, half up", "subtitle_rounding": "nearest millisecond"}
    return profile, {"schema_version": 1, "kind": "mock_scenes", "source": SOURCE,
                     "plan_sha256": _digest(plan), "profile": profile, "scenes": scenes}


def _srt_time(value):
    hours, remainder = divmod(value, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def _srt_text(scenes):
    return "\n\n".join(f"{scene['number']}\n{_srt_time(scene['start_ms'])} --> "
                         f"{_srt_time(scene['end_ms'])}\n{scene['script']}"
                         for scene in scenes["scenes"]) + "\n"


def _check_srt(text, expected_scenes, duration):
    blocks = text.rstrip("\n").split("\n\n")
    previous = 0
    for index, block in enumerate(blocks, 1):
        lines = block.split("\n")
        if len(lines) < 3 or lines[0] != str(index):
            raise ValueError("invalid SRT sequence")
        match = re.fullmatch(r"(\d{2}):([0-5]\d):([0-5]\d),(\d{3}) --> (\d{2}):([0-5]\d):([0-5]\d),(\d{3})", lines[1])
        if not match:
            raise ValueError("invalid SRT timing")
        values = list(map(int, match.groups()))
        start = values[0] * 3_600_000 + values[1] * 60_000 + values[2] * 1000 + values[3]
        end = values[4] * 3_600_000 + values[5] * 60_000 + values[6] * 1000 + values[7]
        if start < previous or not start < end or end > duration * 1000 + 1:
            raise ValueError("SRT overlaps or exceeds the video")
        previous = end
    if text != _srt_text(expected_scenes):
        raise ValueError("SRT text or scene timing differs from the approved plan")


def _card(path, width, height, index):
    pixels = bytearray(bytes(COLORS[(index - 1) % len(COLORS)]) * (width * height))
    for row_number, text in enumerate(("MOCK", f"SCENE {index}")):
        scale = min(4, max(1, width // (len(text) * 6 + 2)))
        origin_x = (width - len(text) * 6 * scale) // 2
        origin_y = height // 2 + (row_number * 12 - 10) * scale
        for character_index, char in enumerate(text):
            for y, row in enumerate(GLYPHS.get(char, ("00000",) * 7)):
                for x, bit in enumerate(row):
                    if bit == "1":
                        for dy in range(scale):
                            for dx in range(scale):
                                px = origin_x + character_index * 6 * scale + x * scale + dx
                                py = origin_y + y * scale + dy
                                offset = (py * width + px) * 3
                                pixels[offset:offset + 3] = b"\xff\xff\xff"
    with path.open("xb") as stream:
        stream.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        stream.write(pixels)


def _file_record(path):
    return {"sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def _input_digests(values):
    return {name: _digest(value) for name, value in zip(INPUT_NAMES, values)}


def _inspect(folder, profile, scenes, paths, input_digests):
    video = _file(folder, "video.mp4")
    with video.open("rb") as stream:
        header = stream.read(12)
    if header[4:8] != b"ftyp":
        raise ValueError("result is not an MP4 file")
    raw = _run([paths["ffprobe"], "-v", "error", "-protocol_whitelist", "file,pipe",
                "-f", "mov", "-show_streams", "-show_format", "-of", "json", video])
    probe = json.loads(raw)
    streams = probe.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(streams) != 2 or len(videos) != 1 or len(audios) != 1:
        raise ValueError("mock video must contain one video and one silent audio stream")
    v, a = videos[0], audios[0]
    try:
        duration = float(v["duration"])
        container_duration = float(probe["format"]["duration"])
        rate = Fraction(v["avg_frame_rate"])
        frames = int(v["nb_frames"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        raise ValueError("invalid media probe metadata") from error
    if (not math.isfinite(duration) or not math.isfinite(container_duration) or
            abs(duration - profile["duration_seconds"]) > 1 / FPS or
            abs(container_duration - profile["duration_seconds"]) > 1 / FPS or
            frames != profile["frame_count"] or rate != FPS or
            v.get("width") != profile["width"] or v.get("height") != profile["height"] or
            v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p" or
            a.get("codec_name") != "aac" or a.get("sample_rate") != "48000"):
        raise ValueError("mock media duration, resolution, frame rate or codec differs from its profile")
    _run([paths["ffmpeg"], "-v", "error", "-nostdin", "-xerror", "-err_detect", "explode",
          "-protocol_whitelist", "file,pipe", "-f", "mov", "-i", video,
          "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-"])
    samples = _run([paths["ffmpeg"], "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                    "-f", "mov", "-i", video, "-map", "0:a:0", "-ac", "1", "-ar", "8000",
                    "-f", "s16le", "pipe:1"], binary=True)
    if not samples or any(samples):
        raise ValueError("mock audio must decode to silence")
    subtitle = _file(folder, "subtitles.srt")
    _check_srt(subtitle.read_text(encoding="utf-8"), scenes, duration)
    if _canonical(_json_read(_file(folder, "scenes.json"))) != _canonical(scenes):
        raise ValueError("scene data differs from the approved plan and timeline")
    return {"schema_version": 1, "kind": "mock_quality", "source": SOURCE,
            "status": "technical_pass", "real_execution_allowed": False,
            "inputs": input_digests,
            "payloads": {name: _file_record(_file(folder, name)) for name in PAYLOADS[:3]},
            "checks": {"mp4_probe": True, "full_decode": True, "synthetic_silence": True,
                       "profile_and_duration": True, "srt_timing_and_text": True, "scene_contract": True},
            "observed": {"video_duration_seconds": duration, "container_duration_seconds": container_duration,
                         "width": v["width"], "height": v["height"], "frames": frames, "fps": FPS},
            "human_review": "pending_visual_confirmation_of_synthetic_cards",
            "ai_content_quality": "not_applicable_to_synthetic_media",
            "speech_synchronization": "not_applicable_silent_audio"}


def produce_mock_media(plan, direction, prompts, pricing, quote, approval, output):
    values = (plan, direction, prompts, pricing, quote, approval)
    created = datetime.now(timezone.utc)
    validate_mock_approval(approval, plan, direction, prompts, pricing, quote, now=created)
    profile, scenes = _profile_and_scenes(plan)
    folder = _result_dir(output, new=True)
    paths, versions = _tools()
    folder.mkdir(parents=True, exist_ok=False)
    work = folder / ".work"
    work.mkdir()
    try:
        clips = []
        for scene in scenes["scenes"]:
            number = scene["number"]
            image, clip = work / f"scene_{number:03}.ppm", work / f"scene_{number:03}.mp4"
            _card(image, profile["width"], profile["height"], number)
            _run([paths["ffmpeg"], "-v", "error", "-nostdin", "-n", "-protocol_whitelist", "file,pipe",
                  "-loop", "1", "-framerate", str(FPS), "-f", "image2", "-i", image,
                  "-frames:v", str(scene["end_frame"] - scene["start_frame"]),
                  "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                  "-threads", "1", "-an", clip])
            clips.append(clip.name)
        listing = work / "concat.txt"
        with listing.open("x", encoding="ascii", newline="\n") as stream:
            stream.write("".join(f"file '{name}'\n" for name in clips))
        _run([paths["ffmpeg"], "-v", "error", "-nostdin", "-n", "-protocol_whitelist", "file,pipe",
              "-f", "concat", "-safe", "1", "-i", listing,
              "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
              "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
              "-t", f"{profile['duration_seconds']:.9f}", "-movflags", "+faststart", folder / "video.mp4"])
        with (folder / "subtitles.srt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(_srt_text(scenes))
        _json_write(folder / "scenes.json", scenes)
        inputs = _input_digests(values)
        quality = _inspect(folder, profile, scenes, paths, inputs)
        _json_write(folder / "quality.json", quality)
        manifest = {"schema_version": 1, "kind": "mock_media_result", "source": SOURCE,
                    "scope": "local_synthetic_only", "status": "complete", "real_execution_allowed": False,
                    "created_at": created.isoformat(), "inputs": inputs, "profile": profile,
                    "tools": versions, "files": {name: _file_record(folder / name) for name in PAYLOADS}}
        _json_write(folder / "manifest.json", manifest)
    except (OSError, ValueError) as error:
        _json_write(folder / "failure.json", {"schema_version": 1, "source": SOURCE,
                    "status": "failed", "error": str(error), "recovery": "preserve this attempt; use a new directory"})
        raise
    return manifest


def validate_mock_result(plan, direction, prompts, pricing, quote, approval, result):
    with _result_step("result_location", "result_validation", "check_result_location"):
        folder = _result_dir(result)
    with _result_step("result_manifest", "production_editing", "inspect_preserved_attempt"):
        manifest = _json_read(_file(folder, "manifest.json"))
        required = {"schema_version", "kind", "source", "scope", "status", "real_execution_allowed",
                    "created_at", "inputs", "profile", "tools", "files"}
        if (not isinstance(manifest, dict) or set(manifest) != required or
                type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or
                manifest["kind"] != "mock_media_result" or manifest["source"] != SOURCE or
                manifest["scope"] != "local_synthetic_only" or manifest["status"] != "complete" or
                manifest["real_execution_allowed"] is not False):
            raise ValueError("unsupported mock media manifest")
        if (folder / "failure.json").exists():
            raise ValueError("this media attempt is marked failed")
        created = _timestamp(manifest["created_at"])
        if created > datetime.now(timezone.utc):
            raise ValueError("media creation timestamp is in the future")
    with _result_step("input_approval_binding", "input_approval", "check_inputs_and_reapprove"):
        validate_mock_approval(approval, plan, direction, prompts, pricing, quote, now=created)
        expected_inputs = _input_digests((plan, direction, prompts, pricing, quote, approval))
        if _canonical(manifest["inputs"]) != _canonical(expected_inputs):
            raise ValueError("manifest input, profile, tool, or file contract mismatch")
    with _result_step("planning_timeline", "planning", "revise_then_reapprove"):
        profile, scenes = _profile_and_scenes(plan)
    with _result_step("result_integrity", "production_editing", "inspect_preserved_attempt"):
        if (_canonical(manifest["profile"]) != _canonical(profile) or
                not isinstance(manifest["tools"], dict) or set(manifest["tools"]) != {"ffmpeg", "ffprobe"} or
                any(not isinstance(value, str) or not value for value in manifest["tools"].values()) or
                not isinstance(manifest["files"], dict) or set(manifest["files"]) != set(PAYLOADS)):
            raise ValueError("manifest input, profile, tool, or file contract mismatch")
        for name in PAYLOADS:
            if _canonical(manifest["files"][name]) != _canonical(_file_record(_file(folder, name))):
                raise ValueError(f"result file integrity mismatch: {name}")
    with _result_step("local_tools", "local_environment", "check_local_tools"):
        paths, _ = _tools()
    with _result_step("media_and_subtitle_checks", "production_editing", "rebuild_after_approval"):
        report = _inspect(folder, profile, scenes, paths, expected_inputs)
        if _canonical(_json_read(folder / "quality.json")) != _canonical(report):
            raise ValueError("saved quality report differs from fresh technical checks")
    return report
