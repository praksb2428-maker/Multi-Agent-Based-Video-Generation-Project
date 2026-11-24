"""Minimal localhost UI for prompt, storyboard previews, approval, and MP4."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

from src.storyboard_flow import StoryboardService
from src.storyboard_openai import OpenAIStoryboardProvider, IMAGE_MODEL, TEXT_MODEL
from src.storyboard_render import render, tools as ffmpeg_tools


WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 6_900_000
STATIC = {"/": ("storyboard.html", "text/html"),
          "/storyboard.css": ("storyboard.css", "text/css"),
          "/storyboard.js": ("storyboard.js", "text/javascript")}


def strict_json(raw: bytes) -> dict:
    def pairs(items):
        data = {}
        for key, value in items:
            if key in data:
                raise ValueError("중복 JSON 필드는 허용하지 않습니다.")
            data[key] = value
        return data
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("숫자 형식이 올바르지 않습니다.")))
    if not isinstance(value, dict):
        raise ValueError("JSON 객체가 필요합니다.")
    return value


class LocalServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, port: int = 8766, service=None):
        self.service = service or StoryboardService(OpenAIStoryboardProvider(), renderer=render)
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(30)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    server_version = "StoryboardLocal/1"

    def log_message(self, format, *args):
        return  # Do not log prompts, uploaded images, tokens, or local paths.

    def _send(self, status: int, data: bytes, content_type: str, *, download=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if download:
            self.send_header("Content-Disposition", 'attachment; filename="storyboard.mp4"')
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, value: dict):
        self._send(status, json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _path(self) -> str:
        if self.headers.get_all("Host") != [f"127.0.0.1:{self.server.server_port}"]:
            raise PermissionError("127.0.0.1 주소로 접속하세요.")
        origin = self.headers.get_all("Origin")
        if origin is not None and origin != [self.server.origin]:
            raise PermissionError("다른 사이트의 요청은 허용하지 않습니다.")
        if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
            raise PermissionError("이 화면에서 직접 실행하세요.")
        url = urlsplit(self.path)
        if url.scheme or url.netloc or url.query or url.fragment or "%" in url.path:
            raise ValueError("요청 주소가 올바르지 않습니다.")
        return url.path

    def do_GET(self):
        try:
            path = self._path()
            if path in STATIC:
                name, mime = STATIC[path]
                self._send(200, (WEB / name).read_bytes(), mime + "; charset=utf-8")
            elif path == "/api/bootstrap":
                try:
                    ffmpeg_tools()
                    ready = True
                except ValueError:
                    ready = False
                self._json(200, {"csrf": self.server.csrf, "text_model": TEXT_MODEL,
                                 "image_model": IMAGE_MODEL, "ffmpeg_ready": ready,
                                 "preview_output_estimate_usd_each": 0.041})
            elif match := re.fullmatch(r"/api/jobs/([0-9a-f]{32})", path):
                self._json(200, self.server.service.get(match[1]))
            elif match := re.fullmatch(r"/media/([0-9a-f]{32})/([a-z0-9.-]+)", path):
                data, mime = self.server.service.media(match[1], match[2])
                self._send(200, data, mime, download=(mime == "video/mp4"))
            else:
                self._json(404, {"error": "화면이나 파일을 찾을 수 없습니다."})
        except PermissionError as error:
            self._json(403, {"error": str(error)})
        except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})

    def do_POST(self):
        try:
            path = self._path()
            if self.headers.get_all("X-CSRF-Token") != [self.server.csrf]:
                raise PermissionError("화면을 새로 고쳐 다시 실행하세요.")
            if self.headers.get_all("Content-Type") != ["application/json"] or self.headers.get("Transfer-Encoding"):
                raise ValueError("application/json 요청만 지원합니다.")
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_BODY:
                raise ValueError("요청 크기가 올바르지 않습니다.")
            size = int(lengths[0])
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("요청을 모두 받지 못했습니다.")
            body = strict_json(raw)
            if path == "/api/jobs":
                if set(body) not in ({"prompt", "seconds"}, {"prompt", "seconds", "image_b64"}):
                    raise ValueError("입력 필드가 올바르지 않습니다.")
                result = self.server.service.create(**body)
            elif match := re.fullmatch(r"/api/jobs/([0-9a-f]{32})/(plan|previews|decline|render)", path):
                if body:
                    raise ValueError("이 동작에는 추가 입력이 필요하지 않습니다.")
                action = {"plan": "plan", "previews": "previews", "decline": "decline",
                          "render": "approve_and_render"}[match[2]]
                result = getattr(self.server.service, action)(match[1])
            else:
                self._json(404, {"error": "실행 경로를 찾을 수 없습니다."})
                return
            self._json(200, result)
        except PermissionError as error:
            self._json(403, {"error": str(error)})
        except (ValueError, KeyError, OSError, TypeError, json.JSONDecodeError) as error:
            self._json(400, {"error": str(error)})
        except Exception:
            self._json(500, {"error": "작업이 중단됐습니다. 저장 상태와 API 사용 내역을 확인하세요."})


def main():
    parser = argparse.ArgumentParser(description="간결한 숏츠 스토리보드 작업실")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be from 1 to 65535")
    server = LocalServer(args.port)
    print(f"Storyboard: {server.origin} ; stop: Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
