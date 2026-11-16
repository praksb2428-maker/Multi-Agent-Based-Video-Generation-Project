import copy
import gc
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch

from src.direction import _canonical, create_direction, create_prompts
from src.mock_media import (WORKSPACE, _file_record, _inspect, _profile_and_scenes,
                            _result_dir, _tools, produce_mock_media, validate_mock_result)
from src.mock_production import create_mock_quote, approve_mock_production
from src.shorts import approve_plan, create_draft
from test_shorts import BRIEF
from test_mock_production import PRICING


ROOT = Path(__file__).resolve().parents[1]


def values(seconds=5):
    plan = approve_plan(create_draft(dict(BRIEF, target_seconds=seconds)))
    direction = create_direction(plan)
    prompts = create_prompts(plan, direction)
    pricing = copy.deepcopy(PRICING)
    quote = create_mock_quote(plan, direction, prompts, pricing)
    approval = approve_mock_production(plan, direction, prompts, pricing, quote,
                                       approved_by="synthetic media tester", reason="local fixture only")
    return plan, direction, prompts, pricing, quote, approval


class MockMediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORKSPACE.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix="media-tests-", dir=WORKSPACE)
        cls.base = Path(cls.temp.name)
        cls.values = values()
        cls.result = cls.base / "fixture"
        cls.originals = copy.deepcopy(cls.values)
        cls.manifest = produce_mock_media(*cls.values, cls.result)
        cls.tools, _ = _tools()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def copy_result(self, label):
        destination = self.base / label
        shutil.copytree(self.result, destination)
        return destination

    def rewrite_manifest_record(self, folder, name):
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"][name] = _file_record(folder / name)
        (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_real_ffmpeg_result_probe_decode_srt_and_approval_at_creation(self):
        report = validate_mock_result(*self.values, self.result)
        self.assertEqual(report["status"], "technical_pass")
        self.assertEqual(report["observed"]["frames"], 120)
        self.assertEqual((report["observed"]["width"], report["observed"]["height"]), (360, 640))
        self.assertEqual(self.values, self.originals)
        self.assertIs(self.manifest["real_execution_allowed"], False)
        self.assertEqual(report["human_review"], "pending_visual_confirmation_of_synthetic_cards")
        # Historical QA remains meaningful after the test-only approval expires.
        with patch("src.mock_media.datetime") as clock:
            clock.now.return_value = datetime.now(timezone.utc) + timedelta(hours=2)
            self.assertEqual(validate_mock_result(*self.values, self.result)["status"], "technical_pass")

    def test_validation_closes_mp4_header_without_resource_warning(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            self.assertEqual(validate_mock_result(*self.values, self.result)["status"], "technical_pass")
            gc.collect()
        self.assertEqual([item for item in caught if issubclass(item.category, ResourceWarning)], [])

    def test_invalid_or_expired_approval_does_not_create_directory_or_run_tools(self):
        for index, edit in enumerate(("missing", "expired", "tampered", "real")):
            changed = list(copy.deepcopy(self.values))
            if edit == "missing": changed[-1] = None
            elif edit == "expired":
                changed[-1] = approve_mock_production(*changed[:5], approved_by="test", reason="test",
                                    now=datetime.now(timezone.utc) - timedelta(hours=2))
            elif edit == "tampered": changed[-1]["reason"] += " changed"
            else: changed[-1]["real_execution_allowed"] = True
            output = self.base / f"denied-{index}"
            with patch("src.mock_media._tools", side_effect=AssertionError("must not launch")):
                with self.subTest(edit=edit), self.assertRaises(ValueError):
                    produce_mock_media(*changed, output)
            self.assertFalse(output.exists())

    def test_existing_directory_and_unsafe_paths_are_rejected(self):
        manifest = (self.result / "manifest.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            produce_mock_media(*self.values, self.result)
        self.assertEqual((self.result / "manifest.json").read_bytes(), manifest)
        for path in (ROOT / "not-workspace", WORKSPACE, WORKSPACE / "x" / ".." / "escape"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                _result_dir(path, new=True)
        link = self.base / "linked"
        try:
            link.symlink_to(self.result, target_is_directory=True)
        except OSError:
            return  # Windows privilege unavailable; direct containment is still checked above.
        with self.assertRaisesRegex(ValueError, "linked"):
            _result_dir(link)

    def test_frame_quantization_and_unsupported_profile_or_srt_are_explicit(self):
        draft = create_draft(dict(BRIEF, target_seconds=5))
        for scene, duration in zip(draft["scenes"], (0.101, 2.477, 2.422)):
            scene["duration_seconds"] = duration
        profile, scenes = _profile_and_scenes(approve_plan(draft))
        self.assertEqual(profile["frame_count"], 120)
        for original, quantized in zip(draft["scenes"], scenes["scenes"]):
            self.assertLessEqual(abs((quantized["end_frame"] - quantized["start_frame"]) / 24 -
                                     original["duration_seconds"]), 1 / 24)
        for edit in ("ratio", "tiny", "paragraph"):
            changed = create_draft(dict(BRIEF, target_seconds=5))
            if edit == "ratio": changed["brief"]["aspect_ratio"] = "99999:1"
            elif edit == "tiny":
                changed["scenes"][0]["duration_seconds"] = 0.00001
                changed["scenes"][1]["duration_seconds"] += 0.99999
            else: changed["scenes"][0]["script"] += "\n\nparagraph"
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                _profile_and_scenes(approve_plan(changed))

    def test_stale_inputs_manifest_schema_file_names_and_missing_payload_rejected(self):
        changed = copy.deepcopy(self.values)
        changed[0]["hook"] += " changed"
        with self.assertRaises(ValueError):
            validate_mock_result(*changed, self.result)
        for index, edit in enumerate(("version", "name", "flag", "missing")):
            folder = self.copy_result(f"manifest-{index}")
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            if edit == "version": manifest["schema_version"] = True
            elif edit == "name": manifest["files"]["../outside.mp4"] = manifest["files"].pop("video.mp4")
            elif edit == "flag": manifest["real_execution_allowed"] = True
            else: (folder / "subtitles.srt").rename(folder / "missing.srt")
            (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                validate_mock_result(*self.values, folder)

    def test_payload_hash_tamper_and_rehashed_srt_or_scene_tamper_rejected(self):
        for index, edit in enumerate(("video", "subtitle", "scene", "quality")):
            folder = self.copy_result(f"payload-{index}")
            if edit == "video":
                with (folder / "video.mp4").open("ab") as stream: stream.write(b"changed")
            elif edit == "subtitle":
                (folder / "subtitles.srt").write_text("1\n00:00:04,000 --> 00:00:09,000\nwrong\n", encoding="utf-8")
                self.rewrite_manifest_record(folder, "subtitles.srt")
            elif edit == "scene":
                scene = json.loads((folder / "scenes.json").read_text(encoding="utf-8"))
                scene["scenes"][0]["start_frame"] = 10
                (folder / "scenes.json").write_text(json.dumps(scene), encoding="utf-8")
                self.rewrite_manifest_record(folder, "scenes.json")
            else:
                quality = json.loads((folder / "quality.json").read_text(encoding="utf-8"))
                quality["status"] = "all_content_approved"
                (folder / "quality.json").write_text(json.dumps(quality), encoding="utf-8")
                self.rewrite_manifest_record(folder, "quality.json")
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                validate_mock_result(*self.values, folder)

    def test_wrong_media_duration_and_resolution_are_probed_not_only_hashed(self):
        for label, size, seconds in (("duration", "360x640", "1"), ("resolution", "320x240", "5")):
            folder = self.copy_result(f"media-{label}")
            destination = folder / "wrong.mp4"
            command = [self.tools["ffmpeg"], "-v", "error", "-nostdin", "-n", "-f", "lavfi", "-i",
                       f"color=c=blue:s={size}:r=24", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                       "-t", seconds, "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1",
                       "-pix_fmt", "yuv420p", "-c:a", "aac", str(destination)]
            subprocess.run(command, check=True, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
            destination.replace(folder / "video.mp4")
            self.rewrite_manifest_record(folder, "video.mp4")
            with self.assertRaisesRegex(ValueError, "duration|resolution"):
                validate_mock_result(*self.values, folder)

    def test_broken_rehashed_media_is_rejected_by_probe(self):
        folder = self.copy_result("broken-media")
        data = (folder / "video.mp4").read_bytes()
        (folder / "video.mp4").write_bytes(data[:32])
        self.rewrite_manifest_record(folder, "video.mp4")
        with self.assertRaisesRegex(ValueError, "media tool"):
            validate_mock_result(*self.values, folder)

    def test_missing_tools_and_timeout_fail_without_success_manifest(self):
        output = self.base / "no-tools"
        with patch("src.mock_media.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "required"):
                produce_mock_media(*self.values, output)
        self.assertFalse(output.exists())
        output = self.base / "timeout"
        with patch("src.mock_media._tools", return_value=(self.tools, {"ffmpeg": "test", "ffprobe": "test"})), \
                patch("src.mock_media.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 60)):
            with self.assertRaisesRegex(ValueError, "timed out"):
                produce_mock_media(*self.values, output)
        self.assertFalse((output / "manifest.json").exists())
        self.assertEqual(json.loads((output / "failure.json").read_text())["status"], "failed")

    def test_real_local_render_works_under_network_and_key_read_sentinels(self):
        output = self.base / "no-network"
        safe_environment = {name: os.environ.get(name, "")
                            for name in ("PATH", "PATHEXT", "SystemRoot", "WINDIR")}
        class SafeEnvironment(dict):
            def __getitem__(self, key):
                if key.startswith("OPENAI_") or "PROXY" in key.upper():
                    raise AssertionError("credential or proxy environment read")
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key.startswith("OPENAI_") or "PROXY" in key.upper():
                    raise AssertionError("credential or proxy environment read")
                return super().get(key, default)
        with patch("socket.socket.connect", side_effect=AssertionError("no network")), \
                patch("socket.create_connection", side_effect=AssertionError("no network")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")), \
                patch("os.environ", SafeEnvironment(safe_environment)):
            produce_mock_media(*self.values, output)
            self.assertEqual(validate_mock_result(*self.values, output)["status"], "technical_pass")

    def test_cli_produce_validate_and_refuse_existing_output(self):
        folder = self.base / "cli"
        folder.mkdir()
        paths = []
        for index, value in enumerate(self.values):
            path = folder / f"input-{index}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths.append(str(path))
        originals = [Path(path).read_bytes() for path in paths]
        output = folder / "result"
        def run(name):
            return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", name, *paths, str(output)],
                                  cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
        for command in ("produce-mock", "validate-result-mock"):
            result = run(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(json.loads(result.stdout)["status"], ("complete", "technical_pass"))
        before = (output / "video.mp4").read_bytes()
        self.assertEqual(run("produce-mock").returncode, 2)
        self.assertEqual((output / "video.mp4").read_bytes(), before)
        self.assertEqual([Path(path).read_bytes() for path in paths], originals)


if __name__ == "__main__":
    unittest.main()
