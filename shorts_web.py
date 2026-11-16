"""Local demonstration service; no optional runtime starts on import.

Run with .venv/Scripts/python.exe -X utf8 shorts_web.py and stop with Ctrl+C.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import re
import secrets
import socket
from urllib.parse import urlsplit

from src.gui_workflow import Workflow, WEB, fields, strict_json


MAX_BODY = 131_072
STATIC = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js", "/architecture.svg": "architecture.svg"}


class LocalServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, port=8765, workflow=None):
        self.workflow = workflow or Workflow()
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address


class Handler(BaseHTTPRequestHandler):
    server_version = "ShortsLocal/1"

    def log_message(self, format, *args):
        # Do not log payloads, CSRF tokens, user text, or absolute file paths.
        return

    def _headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()

    def _json(self, status, value):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(data))
        self.wfile.write(data)

    def _guard(self):
        if self.headers.get_all("Host") != [f"127.0.0.1:{self.server.server_port}"]:
            raise PermissionError("이 서비스의 localhost 주소로 접속하세요.")
        origins = self.headers.get_all("Origin")
        if origins is not None and origins != [self.server.origin]:
            raise PermissionError("다른 사이트에서 이 서비스를 조작할 수 없습니다.")
        if self.headers.get("Sec-Fetch-Site") in ("cross-site", "same-site"):
            raise PermissionError("이 서비스 화면에서 직접 실행하세요.")
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "%" in parsed.path:
            raise ValueError("지원하지 않는 요청 주소입니다.")
        return parsed.path

    def do_GET(self):
        try:
            path = self._guard()
            if path in STATIC:
                file = WEB / STATIC[path]
                data = file.read_bytes()
                mime = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".svg": "image/svg+xml"}[file.suffix]
                self._headers(200, mime + "; charset=utf-8", len(data))
                self.wfile.write(data)
            elif path == "/api/bootstrap":
                self._json(200, {"csrf": self.server.csrf, "jobs": self.server.workflow.list_jobs(),
                                 "real_execution_allowed": False, "local_model": "explicit_local_planning"})
            elif re.fullmatch(r"/api/jobs/[0-9a-f]{32}", path):
                self._json(200, self.server.workflow.view(path.rsplit("/", 1)[1]))
            elif match := re.fullmatch(r"/files/([0-9a-f]{32})/([1-9][0-9]*)/([a-z.0-9]+)", path):
                file = self.server.workflow.artifact(match[1], int(match[2]), match[3])
                # Artifact validation precedes serving; stream rather than loading an MP4.
                self._headers(200, mimetypes.guess_type(file.name)[0] or "application/octet-stream", file.stat().st_size)
                with file.open("rb") as stream:
                    while chunk := stream.read(65_536):
                        self.wfile.write(chunk)
            else:
                self._json(404, {"error": "해당 화면이나 파일을 찾을 수 없습니다."})
        except PermissionError as error:
            self._json(403, {"error": str(error)})
        except (ValueError, KeyError, OSError, TypeError) as error:
            self._json(400, {"error": "저장된 상태를 확인하세요: " + str(error)})

    def do_POST(self):
        try:
            path = self._guard()
            if self.headers.get_all("X-CSRF-Token") != [self.server.csrf]:
                raise PermissionError("화면을 새로 고친 뒤 다시 실행하세요.")
            if self.headers.get_all("Content-Type") != ["application/json"] or self.headers.get("Transfer-Encoding"):
                raise ValueError("application/json 요청만 지원합니다.")
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) != 1 or not lengths[0].isdigit() or not 0 < int(lengths[0]) <= MAX_BODY:
                raise ValueError("요청 크기가 올바르지 않습니다. 최대 128KB입니다.")
            size = int(lengths[0])
            data = self.rfile.read(size)
            if len(data) != size:
                raise ValueError("요청을 모두 받지 못했습니다.")
            payload = strict_json(data)
            if path == "/api/jobs":
                fields(payload, {"brief", "mode", "research_id"} if isinstance(payload, dict) and "research_id" in payload else {"brief", "mode"})
                result = self.server.workflow.create(**payload)
            elif path == "/api/research-mock":
                fields(payload, {"brief"})
                result = self.server.workflow.research(payload["brief"])
            elif match := re.fullmatch(r"/api/jobs/([0-9a-f]{32})/action", path):
                fields(payload, {"action", "payload", "sequence"})
                result = self.server.workflow.action(match[1], **payload)
            else:
                self._json(404, {"error": "지원하지 않는 실행 경로입니다."})
                return
            self._json(200, result)
        except PermissionError as error:
            self._json(403, {"error": str(error)})
        except (ValueError, KeyError, OSError, TypeError) as error:
            self._json(400, {"error": str(error)})
        except Exception:
            self._json(500, {"error": "실행이 중단됐습니다. 결과를 보존하고 저장된 작업을 다시 확인하세요."})


def main():
    parser = argparse.ArgumentParser(description="숏츠 에이전트팀 로컬 모의 제작 화면")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be from 1 to 65535")
    server = LocalServer(args.port)
    print(f"Local mock workspace: {server.origin} ; stop: Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
