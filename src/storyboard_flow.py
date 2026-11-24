"""A small, explicit-approval storyboard workflow for the new local UI."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import threading


ROOT = Path(__file__).resolve().parents[1] / "workspace" / "storyboards"
MAX_IMAGE_BYTES = 5_000_000
MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
PNG = b"\x89PNG\r\n\x1a\n"
MOTIONS = {"zoom_in", "zoom_out", "pan_left", "pan_right"}


def image_type(raw: bytes) -> str:
    if raw.startswith(PNG):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("PNG, JPEG, WebP 이미지만 첨부할 수 있습니다.")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class StoryboardService:
    def __init__(self, provider, *, root: Path = ROOT, renderer=None):
        self.provider = provider
        self.root = Path(root)
        self.renderer = renderer
        self.lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise ValueError("작업 ID가 올바르지 않습니다.")
        folder = self.root / job_id
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("작업을 찾을 수 없습니다.")
        return folder

    def _read(self, job_id: str) -> dict:
        folder = self._dir(job_id)
        job = json.loads((folder / "state.json").read_text(encoding="utf-8"))
        if job.get("id") != job_id or job.get("version") != 1:
            raise ValueError("작업 기록이 올바르지 않습니다.")
        if job["source"]:
            if (job["source"].get("mime") not in MIME_EXT or
                    job["source"].get("file") != "source." + MIME_EXT[job["source"]["mime"]]):
                raise ValueError("첨부 이미지 기록이 올바르지 않습니다.")
            source = folder / job["source"]["file"]
            if source.is_symlink() or digest(source.read_bytes()) != job["source"]["sha256"]:
                raise ValueError("첨부 이미지가 변경됐습니다.")
        segments = job.get("segments", [])
        if (not isinstance(segments, list) or len(segments) > 3 or
                any(not isinstance(segment, dict) or segment.get("start") != index * 10 or
                    segment.get("end") != (index + 1) * 10 or
                    segment.get("motion") not in MOTIONS or
                    not isinstance(segment.get("prompt"), str)
                    for index, segment in enumerate(segments))):
            raise ValueError("구간 기록이 올바르지 않습니다.")
        for index, segment in enumerate(segments, start=1):
            if segment.get("preview"):
                if segment["preview"].get("file") != f"preview-{index:02d}.png":
                    raise ValueError("예시 이미지 경로가 올바르지 않습니다.")
                image = folder / segment["preview"]["file"]
                if image.is_symlink() or digest(image.read_bytes()) != segment["preview"]["sha256"]:
                    raise ValueError("예시 이미지가 변경됐습니다.")
        if job.get("approval_sha256"):
            approved = {"prompt": job["prompt"], "seconds": job["seconds"],
                        "source": job["source"]["sha256"] if job["source"] else None,
                        "enhanced_prompt": job["enhanced_prompt"], "segments": segments}
            if digest(_json_bytes(approved)) != job["approval_sha256"]:
                raise ValueError("승인된 내용이 변경됐습니다.")
        if job.get("video"):
            if job["video"].get("file") != "video.mp4":
                raise ValueError("영상 경로가 올바르지 않습니다.")
            video = folder / "video.mp4"
            if video.is_symlink() or digest(video.read_bytes()) != job["video"]["sha256"]:
                raise ValueError("영상 파일이 변경됐습니다.")
        return job

    def _write(self, job: dict) -> None:
        folder = self._dir(job["id"])
        temp = folder / "state.new"
        temp.write_bytes(_json_bytes(job))
        temp.replace(folder / "state.json")

    @staticmethod
    def public(job: dict) -> dict:
        data = {key: value for key, value in job.items() if key not in {"source"}}
        data["source_url"] = f"/media/{job['id']}/{job['source']['file']}" if job["source"] else None
        data["segments"] = [
            {**segment, "preview_url": f"/media/{job['id']}/{segment['preview']['file']}" if segment.get("preview") else None}
            for segment in job.get("segments", [])
        ]
        for segment in data["segments"]:
            segment.pop("preview", None)
        data["video_url"] = f"/media/{job['id']}/video.mp4" if job["stage"] == "ready" else None
        data.pop("video", None)
        data.pop("approval_sha256", None)
        return data

    def get(self, job_id: str) -> dict:
        with self.lock:
            return self.public(self._read(job_id))

    def create(self, prompt: str, seconds: int, image_b64: str | None = None) -> dict:
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 2000 or "\x00" in prompt:
            raise ValueError("프롬프트는 1~2000자로 입력하세요.")
        if type(seconds) is not int or seconds not in (10, 20, 30):
            raise ValueError("영상 길이는 10초, 20초, 30초 중에서 선택하세요.")
        raw = None
        if image_b64 is not None:
            if not isinstance(image_b64, str) or len(image_b64) > 6_800_000:
                raise ValueError("첨부 이미지가 너무 큽니다.")
            try:
                raw = base64.b64decode(image_b64, validate=True)
            except (ValueError, base64.binascii.Error):
                raise ValueError("첨부 이미지를 읽을 수 없습니다.") from None
            if not 0 < len(raw) <= MAX_IMAGE_BYTES:
                raise ValueError("첨부 이미지는 최대 5MB입니다.")
        with self.lock:
            job_id = secrets.token_hex(16)
            folder = self.root / job_id
            folder.mkdir(mode=0o700)
            source = None
            if raw is not None:
                mime = image_type(raw)
                filename = "source." + MIME_EXT[mime]
                (folder / filename).write_bytes(raw)
                source = {"file": filename, "mime": mime, "sha256": digest(raw)}
            job = {"version": 1, "id": job_id, "prompt": prompt.strip(), "seconds": seconds,
                   "source": source, "stage": "draft", "enhanced_prompt": None,
                   "segments": [], "approval_sha256": None, "video": None}
            self._write(job)
            return self.public(job)

    def plan(self, job_id: str) -> dict:
        with self.lock:
            job = self._read(job_id)
            if job["stage"] != "draft":
                raise ValueError("새 프롬프트 분석은 새 작업에서 시작하세요.")
            job["stage"] = "planning"
            self._write(job)
        try:
            source = (self._dir(job_id) / job["source"]["file"]).read_bytes() if job["source"] else None
            output = self.provider.enhance(job["prompt"], job["seconds"], source,
                                           job["source"]["mime"] if job["source"] else None)
            if not isinstance(output, dict) or set(output) != {"enhanced_prompt", "segments"}:
                raise ValueError("모델의 프롬프트 형식이 올바르지 않습니다.")
            enhanced = output["enhanced_prompt"]
            prompts = output["segments"]
            if (not isinstance(enhanced, str) or not 1 <= len(enhanced.strip()) <= 4000 or
                    not isinstance(prompts, list) or len(prompts) != job["seconds"] // 10 or
                    any(not isinstance(item, dict) or set(item) != {"prompt", "motion"} or
                        not isinstance(item["prompt"], str) or not 1 <= len(item["prompt"].strip()) <= 2000 or
                        item["motion"] not in MOTIONS for item in prompts)):
                raise ValueError("모델의 구간 프롬프트가 올바르지 않습니다.")
            with self.lock:
                job = self._read(job_id)
                if job["stage"] != "planning":
                    raise ValueError("작업 상태가 변경됐습니다.")
                job["enhanced_prompt"] = enhanced.strip()
                job["segments"] = [{"start": index * 10, "end": (index + 1) * 10,
                                    "prompt": item["prompt"].strip(), "motion": item["motion"],
                                    "preview": None} for index, item in enumerate(prompts)]
                job["stage"] = "planned"
                self._write(job)
                return self.public(job)
        except Exception:
            with self.lock:
                job = self._read(job_id)
                if job["stage"] == "planning":
                    job["stage"] = "plan_failed"
                    self._write(job)
            raise

    def previews(self, job_id: str) -> dict:
        with self.lock:
            job = self._read(job_id)
            if job["stage"] != "planned":
                raise ValueError("구간 프롬프트를 먼저 확인하세요.")
            job["stage"] = "previewing"
            self._write(job)
        try:
            source = (self._dir(job_id) / job["source"]["file"]).read_bytes() if job["source"] else None
            mime = job["source"]["mime"] if job["source"] else None
            for index, segment in enumerate(job["segments"], start=1):
                raw = self.provider.image(segment["prompt"], source, mime)
                if not isinstance(raw, bytes) or not raw.startswith(PNG) or len(raw) > 10_000_000:
                    raise ValueError("예시 이미지 응답이 올바르지 않습니다.")
                filename = f"preview-{index:02d}.png"
                with (self._dir(job_id) / filename).open("xb") as stream:
                    stream.write(raw)
                segment["preview"] = {"file": filename, "sha256": digest(raw)}
                with self.lock:
                    self._write(job)
            with self.lock:
                job["stage"] = "preview_ready"
                self._write(job)
                return self.public(job)
        except Exception:
            with self.lock:
                job = self._read(job_id)
                if job["stage"] == "previewing":
                    job["stage"] = "preview_failed"
                    self._write(job)
            raise

    def decline(self, job_id: str) -> dict:
        with self.lock:
            job = self._read(job_id)
            if job["stage"] not in {"planned", "preview_ready"}:
                raise ValueError("현재 작업은 미생성을 선택할 수 없습니다.")
            job["stage"] = "declined"
            self._write(job)
            return self.public(job)

    def approve_and_render(self, job_id: str) -> dict:
        if self.renderer is None:
            raise ValueError("영상 제작 도구가 준비되지 않았습니다.")
        with self.lock:
            job = self._read(job_id)
            if job["stage"] != "preview_ready" or any(not item["preview"] for item in job["segments"]):
                raise ValueError("모든 예시 이미지와 프롬프트를 먼저 확인하세요.")
            approved = {"prompt": job["prompt"], "seconds": job["seconds"],
                        "source": job["source"]["sha256"] if job["source"] else None,
                        "enhanced_prompt": job["enhanced_prompt"], "segments": job["segments"]}
            job["approval_sha256"] = digest(_json_bytes(approved))
            job["stage"] = "rendering"
            self._write(job)
        try:
            raw = self.renderer(self._dir(job_id), job["segments"], job["seconds"])
            if not isinstance(raw, bytes) or len(raw) < 128 or b"ftyp" not in raw[:32]:
                raise ValueError("MP4 결과가 올바르지 않습니다.")
            with self.lock:
                job = self._read(job_id)
                if job["stage"] != "rendering":
                    raise ValueError("작업 상태가 변경됐습니다.")
                file = self._dir(job_id) / "video.mp4"
                if not file.exists():
                    file.write_bytes(raw)
                job["video"] = {"file": "video.mp4", "sha256": digest(raw)}
                job["stage"] = "ready"
                self._write(job)
                return self.public(job)
        except Exception:
            with self.lock:
                job = self._read(job_id)
                if job["stage"] == "rendering":
                    job["stage"] = "render_failed"
                    self._write(job)
            raise

    def media(self, job_id: str, filename: str) -> tuple[bytes, str]:
        with self.lock:
            job = self._read(job_id)
            allowed = {}
            if job["source"]:
                allowed[job["source"]["file"]] = job["source"]["mime"]
            if job["stage"] in {"preview_ready", "approved", "rendering", "ready"}:
                allowed.update({item["preview"]["file"]: "image/png" for item in job["segments"] if item["preview"]})
            if job["stage"] == "ready" and job["video"]:
                allowed[job["video"]["file"]] = "video/mp4"
            if filename not in allowed:
                raise ValueError("파일을 찾을 수 없습니다.")
            file = self._dir(job_id) / filename
            if file.is_symlink():
                raise ValueError("파일 경로가 올바르지 않습니다.")
            return file.read_bytes(), allowed[filename]
