"""Offline contracts for the new prompt → preview → approval → MP4 path."""

import base64
import http.client
import json
import os
from pathlib import Path
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
import zlib

from src import storyboard_openai
from src.storyboard_flow import PNG, StoryboardService
from src.storyboard_openai import OpenAIStoryboardProvider
from src.storyboard_render import render, tools
from storyboard_web import LocalServer

import httpx


def png(width=4, height=6):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    pixels = b"".join(b"\x00" + b"\x88\x99\xaa" * width for _ in range(height))
    return PNG + chunk(b"IHDR", struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


class FakeProvider:
    def __init__(self):
        self.calls = []

    def enhance(self, prompt, seconds, source, mime):
        self.calls.append(("enhance", source, mime))
        return {"enhanced_prompt": "구체화한 " + prompt,
                "segments": [{"prompt": f"장면 {i+1}", "motion": "zoom_in"} for i in range(seconds // 10)]}

    def image(self, prompt, source, mime):
        self.calls.append(("image", source, mime))
        return png()


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.provider = FakeProvider()
        self.rendered = []
        def fake_render(folder, segments, seconds):
            self.rendered.append((segments, seconds))
            return b"\x00\x00\x00\x18ftypisom" + b"\0" * 140
        self.service = StoryboardService(self.provider, root=Path(self.temp.name), renderer=fake_render)

    def test_ten_second_boundaries_and_explicit_actions(self):
        for seconds in (10, 20, 30):
            before = len(self.provider.calls)
            job = self.service.create("비 오는 거리", seconds)
            self.assertEqual(job["stage"], "draft")
            self.assertEqual(len(self.provider.calls), before)
            with self.assertRaises(ValueError):
                self.service.approve_and_render(job["id"])
            planned = self.service.plan(job["id"])
            self.assertEqual([(s["start"], s["end"]) for s in planned["segments"]],
                             [(i * 10, (i + 1) * 10) for i in range(seconds // 10)])
            with self.assertRaises(ValueError):
                self.service.approve_and_render(job["id"])
            ready = self.service.previews(job["id"])
            self.assertEqual(len([s for s in ready["segments"] if s["preview_url"]]), seconds // 10)
            done = self.service.approve_and_render(job["id"])
            self.assertEqual(done["stage"], "ready")
            self.assertEqual(done["video_url"], f"/media/{job['id']}/video.mp4")
            self.assertEqual(self.rendered[-1][1], seconds)
            with self.assertRaises(ValueError):
                self.service.approve_and_render(job["id"])

    def test_source_image_is_used_and_tampering_blocks_actions(self):
        source = png()
        job = self.service.create("원본 이미지 유지", 20, base64.b64encode(source).decode())
        self.service.plan(job["id"])
        self.service.previews(job["id"])
        self.assertTrue(all(call[1] == source and call[2] == "image/png" for call in self.provider.calls))
        folder = Path(self.temp.name) / job["id"]
        (folder / "preview-01.png").write_bytes(png(5, 6))
        with self.assertRaisesRegex(ValueError, "변경"):
            self.service.approve_and_render(job["id"])
        self.assertFalse(self.rendered)

    def test_state_path_or_approval_change_blocks_download(self):
        job = self.service.create("불빛", 10)
        self.service.plan(job["id"])
        self.service.previews(job["id"])
        self.service.approve_and_render(job["id"])
        state_file = Path(self.temp.name) / job["id"] / "state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        state["segments"][0]["prompt"] = "승인 후 바꾼 내용"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "승인된 내용"):
            self.service.media(job["id"], "video.mp4")
        state["segments"][0]["prompt"] = "장면 1"
        state["segments"][0]["preview"]["file"] = "../../outside.png"
        state_file.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "경로"):
            self.service.get(job["id"])

    def test_decline_and_bad_inputs_never_render(self):
        with self.assertRaises(ValueError):
            self.service.create(" ", 10)
        with self.assertRaises(ValueError):
            self.service.create("장면", 15)
        with self.assertRaises(ValueError):
            self.service.create("장면", 10, base64.b64encode(b"<svg></svg>").decode())
        job = self.service.create("장면", 10)
        self.service.plan(job["id"])
        self.service.decline(job["id"])
        with self.assertRaises(ValueError):
            self.service.previews(job["id"])
        with self.assertRaises(ValueError):
            self.service.approve_and_render(job["id"])
        self.assertFalse(self.rendered)

    def test_provider_failure_is_not_retried(self):
        class Broken(FakeProvider):
            def image(self, prompt, source, mime):
                self.calls.append(("image", source, mime))
                raise ValueError("서비스 오류")
        broken = Broken()
        service = StoryboardService(broken, root=Path(self.temp.name))
        job = service.create("장면", 10)
        service.plan(job["id"])
        with self.assertRaises(ValueError):
            service.previews(job["id"])
        self.assertEqual(service.get(job["id"])["stage"], "preview_failed")
        self.assertEqual(len([item for item in broken.calls if item[0] == "image"]), 1)
        with self.assertRaises(ValueError):
            service.previews(job["id"])

    def test_local_http_requires_csrf_and_reaches_download(self):
        server = LocalServer(0, self.service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join(timeout=5)))
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=20)
        self.addCleanup(connection.close)
        connection.request("GET", "/api/bootstrap")
        token = json.loads(connection.getresponse().read())["csrf"]
        headers = {"Content-Type": "application/json", "Origin": server.origin}
        connection.request("POST", "/api/jobs", b'{"prompt":"x","seconds":10}', headers)
        denied = connection.getresponse()
        self.assertEqual(denied.status, 403)
        denied.read()
        headers["X-CSRF-Token"] = token
        connection.request("POST", "/api/jobs", b'{"prompt":"x","seconds":10}', headers)
        job = json.loads(connection.getresponse().read())
        for action in ("plan", "previews", "render"):
            connection.request("POST", f"/api/jobs/{job['id']}/{action}", b"{}", headers)
            response = connection.getresponse()
            self.assertEqual(response.status, 200, response.read())
            response.read()
        connection.request("GET", f"/media/{job['id']}/video.mp4")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "video/mp4")
        response.read()


class OpenAIBoundaryTests(unittest.TestCase):
    def test_server_key_reader_is_independent_of_legacy_app(self):
        with tempfile.TemporaryDirectory() as temp:
            env_file = Path(temp) / ".env"
            env_file.write_text("OPENAI_API_KEY=sk-file-key\n", encoding="utf-8")
            with patch.object(storyboard_openai, "ENV_FILE", env_file):
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(storyboard_openai._api_key(), "sk-file-key")
                with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-server-key"}, clear=True):
                    self.assertEqual(storyboard_openai._api_key(), "sk-server-key")
                env_file.write_text("OPENAI_API_KEY=sk-a\nOPENAI_API_KEY=sk-b\n", encoding="utf-8")
                with patch.dict(os.environ, {}, clear=True):
                    with self.assertRaisesRegex(ValueError, "한 번만"):
                        storyboard_openai._api_key()

    def test_provider_uses_only_expected_endpoints_and_models(self):
        calls = []
        picture = base64.b64encode(png()).decode()
        def handler(request):
            calls.append(request)
            self.assertEqual(request.headers["authorization"], "Bearer sk-test")
            if request.url.path == "/v1/responses":
                body = json.loads(request.content)
                self.assertEqual(body["model"], "gpt-6.1-sol")
                payload = json.dumps({"enhanced_prompt": "상세", "segments": [{"prompt": "장면", "motion": "zoom_in"}]})
                return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": payload}]}]})
            self.assertEqual(request.url.path, "/v1/images/generations")
            self.assertEqual(json.loads(request.content)["model"], "gpt-image-2")
            return httpx.Response(200, json={"data": [{"b64_json": picture}]})
        provider = OpenAIStoryboardProvider(key_getter=lambda: "sk-test", transport=httpx.MockTransport(handler))
        self.assertEqual(provider.enhance("장면", 10, None, None)["enhanced_prompt"], "상세")
        self.assertEqual(provider.image("장면", None, None), png())
        self.assertEqual(len(calls), 2)

    def test_attached_image_uses_edit_endpoint(self):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/images/edits")
            self.assertIn("multipart/form-data", request.headers["content-type"])
            self.assertIn(b"source.png", request.content)
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png()).decode()}]})
        provider = OpenAIStoryboardProvider(key_getter=lambda: "sk-test", transport=httpx.MockTransport(handler))
        self.assertEqual(provider.image("장면", png(), "image/png"), png())


class RendererTests(unittest.TestCase):
    def test_real_ffmpeg_creates_thirty_second_mp4_when_available(self):
        try:
            tools()
        except ValueError:
            self.skipTest("FFmpeg/FFprobe not configured")
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            segments = []
            for index, motion in enumerate(("zoom_in", "zoom_out", "pan_right"), start=1):
                filename = f"preview-{index:02d}.png"
                (folder / filename).write_bytes(png(64, 96))
                segments.append({"preview": {"file": filename}, "motion": motion})
            raw = render(folder, segments, 30)
            self.assertIn(b"ftyp", raw[:32])
            self.assertGreater(len(raw), 128)


if __name__ == "__main__":
    unittest.main()
