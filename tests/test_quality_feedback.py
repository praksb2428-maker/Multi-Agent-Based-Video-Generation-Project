import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import socket
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.mock_media import WORKSPACE, MockResultValidationError, produce_mock_media
from src.mock_production import _digest
from src.quality_feedback import (inspect_mock_result, review_mock_result,
                                  validate_mock_inspection, validate_mock_review)
from test_mock_media import values


ROOT = Path(__file__).resolve().parents[1]
ACCEPT = {"schema_version": 1, "reviewer": "synthetic test reviewer",
          "decision": "accept", "notes": "Explicit test self-report only; no final user acceptance.",
          "issues": []}
CHANGES = {**ACCEPT, "decision": "request_changes", "issues": [
    {"category": "content", "scene_number": 1, "note": "Revise the opening in a separate new plan."}]}


def reseal(value):
    value["content_sha256"] = _digest({key: item for key, item in value.items()
                                       if key != "content_sha256"})
    return value


class QualityFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="feedback-tests-", dir=WORKSPACE)
        cls.base = Path(cls.temp.name)
        cls.values = values()
        cls.result = cls.base / "result"
        produce_mock_media(*cls.values, cls.result)
        cls.inspection = inspect_mock_result(*cls.values, cls.result)
        cls.originals = copy.deepcopy(cls.values)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_pass_explicit_accept_roundtrip_and_originals_remain_unchanged(self):
        before = {path.name: sha256(path.read_bytes()).hexdigest()
                  for path in self.result.iterdir() if path.is_file()}
        review = review_mock_result(*self.values, self.result, self.inspection, ACCEPT)
        saved = json.loads(json.dumps(review))
        self.assertEqual(validate_mock_review(saved, *self.values, self.result, self.inspection), saved)
        self.assertEqual(saved["status"], "accepted_mock_result")
        self.assertIs(saved["real_execution_allowed"], False)
        self.assertEqual(saved["routes"], [])
        self.assertEqual(self.values, self.originals)
        self.assertEqual(before, {path.name: sha256(path.read_bytes()).hexdigest()
                                 for path in self.result.iterdir() if path.is_file()})

    def test_manual_issue_categories_have_fixed_nonexecuting_routes(self):
        issues = [{"category": category, "scene_number": 1, "note": "Explicit caller issue"}
                  for category in ("content", "visual", "timing", "subtitle")]
        review = review_mock_result(*self.values, self.result, self.inspection,
                                    {**CHANGES, "issues": issues})
        self.assertEqual(review["status"], "changes_requested")
        self.assertEqual([route["target_stage"] for route in review["routes"]],
                         ["planning", "direction_prompt", "production_editing", "production_editing"])
        self.assertTrue(all(route["auto_execute"] is False for route in review["routes"]))

    def test_failure_reports_are_routed_and_cannot_be_accepted(self):
        broken = self.base / "broken"
        shutil.copytree(self.result, broken)
        with (broken / "subtitles.srt").open("a", encoding="utf-8") as stream:
            stream.write("changed")
        inspection = inspect_mock_result(*self.values, broken)
        self.assertEqual(inspection["status"], "rework_required")
        self.assertEqual(inspection["failure"]["check_id"], "result_integrity")
        self.assertEqual(inspection["routes"][0]["target_stage"], "production_editing")
        with self.assertRaisesRegex(ValueError, "cannot be accepted"):
            review_mock_result(*self.values, broken, inspection, ACCEPT)
        review = review_mock_result(*self.values, broken, inspection, CHANGES)
        self.assertEqual(validate_mock_review(review, *self.values, broken, inspection), review)
        missing = inspect_mock_result(*self.values, self.base / "missing")
        self.assertEqual(missing["status"], "blocked")
        self.assertEqual(missing["failure"]["check_id"], "result_location")

    def test_input_approval_and_unknown_failures_are_conservative(self):
        changed = list(copy.deepcopy(self.values))
        changed[0]["hook"] += " changed"
        inspection = inspect_mock_result(*changed, self.result)
        self.assertEqual(inspection["status"], "blocked")
        self.assertEqual(inspection["routes"][0]["target_stage"], "input_approval")
        with patch("src.quality_feedback.validate_mock_result", side_effect=RuntimeError("not a diagnosis")):
            unknown = inspect_mock_result(*self.values, self.result)
        self.assertEqual(unknown["failure"]["check_id"], "unknown_validation_failure")
        self.assertEqual(unknown["routes"][0]["next_action"], "needs_manual_triage")

    def test_native_diagnostic_changes_preserve_failure_review_and_strict_binding(self):
        def error(address):
            return MockResultValidationError(f"ffprobe [mov @ {address}] invalid data",
                                             "media_and_subtitle_checks", "production_editing",
                                             "rebuild_after_approval")
        with patch("src.quality_feedback.validate_mock_result", side_effect=error("000001")):
            inspection = inspect_mock_result(*self.values, self.result)
        with patch("src.quality_feedback.validate_mock_result", side_effect=error("000002")):
            self.assertEqual(validate_mock_inspection(inspection, *self.values, self.result), inspection)
            review = review_mock_result(*self.values, self.result, inspection, CHANGES)
            self.assertEqual(validate_mock_review(review, *self.values, self.result, inspection), review)
            self.assertIn("000001", inspection["failure"]["message"])
            with self.assertRaisesRegex(ValueError, "cannot be accepted"):
                review_mock_result(*self.values, self.result, inspection, ACCEPT)
            changed = copy.deepcopy(inspection)
            changed["failure"]["message"] = "tampered"
            with self.assertRaisesRegex(ValueError, "content has changed"):
                validate_mock_inspection(changed, *self.values, self.result)
            for failure in ({"check_id": "media_and_subtitle_checks", "message": None},
                            {"check_id": "media_and_subtitle_checks", "message": "raw", "extra": 1},
                            {"check_id": True, "message": "raw"}):
                changed = reseal({**inspection, "failure": failure})
                with self.assertRaises(ValueError):
                    validate_mock_inspection(changed, *self.values, self.result)
            for field, value in (("status", "technical_pass"),
                                 ("failure", {"check_id": "other_check", "message": "raw"}),
                                 ("routes", []), ("failure", None)):
                changed = reseal({**inspection, field: value})
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "stale"):
                    validate_mock_inspection(changed, *self.values, self.result)

    def test_native_corrupt_mp4_can_record_and_revalidate_changes(self):
        broken = self.base / "native-corrupt"
        shutil.copytree(self.result, broken)
        video = broken / "video.mp4"
        video.write_bytes(video.read_bytes()[:32])
        manifest_path = broken / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["video.mp4"] = {"sha256": sha256(video.read_bytes()).hexdigest(), "bytes": 32}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        inspection = inspect_mock_result(*self.values, broken)
        self.assertEqual(inspection["failure"]["check_id"], "media_and_subtitle_checks")
        before = copy.deepcopy(inspection["result_snapshot"])
        review = review_mock_result(*self.values, broken, inspection, CHANGES)
        self.assertEqual(validate_mock_review(review, *self.values, broken, inspection), review)
        self.assertEqual(inspect_mock_result(*self.values, broken)["result_snapshot"], before)
        with self.assertRaisesRegex(ValueError, "cannot be accepted"):
            review_mock_result(*self.values, broken, inspection, ACCEPT)

    def test_reports_and_reviews_reject_tampered_fields_and_routes(self):
        review = review_mock_result(*self.values, self.result, self.inspection, CHANGES)
        for field in ("status", "routes", "content_sha256", "scope", "real_execution_allowed"):
            changed = copy.deepcopy(review)
            changed[field] = "changed"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_mock_review(changed, *self.values, self.result, self.inspection)
        changed = copy.deepcopy(self.inspection)
        changed["status"] = "technical_failure"
        reseal(changed)
        with self.assertRaisesRegex(ValueError, "stale"):
            validate_mock_inspection(changed, *self.values, self.result)
        changed = copy.deepcopy(review)
        changed["routes"][0]["auto_execute"] = True
        reseal(changed)
        with self.assertRaises(ValueError):
            validate_mock_review(changed, *self.values, self.result, self.inspection)

    def test_stale_inputs_payload_and_different_result_location_reject_review(self):
        review = review_mock_result(*self.values, self.result, self.inspection, ACCEPT)
        changed = list(copy.deepcopy(self.values))
        changed[3]["assembly_fixed"] += 1
        with self.assertRaises(ValueError):
            validate_mock_review(review, *changed, self.result, self.inspection)
        other = self.base / "other"
        shutil.copytree(self.result, other)
        with self.assertRaises(ValueError):
            validate_mock_review(review, *self.values, other, self.inspection)
        with (other / "video.mp4").open("ab") as stream:
            stream.write(b"modified")
        with self.assertRaises(ValueError):
            validate_mock_inspection(self.inspection, *self.values, other)

    def test_invalid_review_requests_versions_and_times_are_rejected(self):
        candidates = [None, [], {**ACCEPT, "schema_version": True}, {**ACCEPT, "schema_version": 2},
                      {**ACCEPT, "reviewer": " "}, {**ACCEPT, "notes": None},
                      {**ACCEPT, "auto_execute": True}, {**ACCEPT, "issues": CHANGES["issues"]},
                      {**CHANGES, "issues": []}, {**ACCEPT, "decision": "approve_spending"}]
        for scene in (True, 0, 999, 1.0):
            candidates.append({**CHANGES, "issues": [{**CHANGES["issues"][0], "scene_number": scene}]})
        candidates.append({**CHANGES, "issues": [{**CHANGES["issues"][0], "category": "execute"}]})
        for request in candidates:
            with self.subTest(request=request), self.assertRaises(ValueError):
                review_mock_result(*self.values, self.result, self.inspection, request)
        review = review_mock_result(*self.values, self.result, self.inspection, ACCEPT)
        for timestamp in ("no time", "2026-10-30T00:00:00",
                          (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                          "2000-01-01T00:00:00+00:00"):
            changed = reseal({**review, "reviewed_at": timestamp})
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                validate_mock_review(changed, *self.values, self.result, self.inspection)

    def test_inspection_and_review_work_with_network_and_key_access_blocked(self):
        safe = {key: os.environ.get(key, "") for key in ("PATH", "PATHEXT", "SystemRoot", "WINDIR")}
        class Guard(dict):
            def get(self, key, default=None):
                if key.startswith("OPENAI_") or "PROXY" in key.upper():
                    raise AssertionError("credential or proxy access")
                return super().get(key, default)

            def __getitem__(self, key):
                if key.startswith("OPENAI_") or "PROXY" in key.upper():
                    raise AssertionError("credential or proxy access")
                return super().__getitem__(key)
        with patch("socket.socket.connect", side_effect=AssertionError("no network")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")), \
                patch("os.environ", Guard(safe)):
            for key in ("OPENAI_API_KEY", "HTTPS_PROXY"):
                with self.assertRaises(AssertionError):
                    os.environ.get(key)
            with self.assertRaises(AssertionError):
                socket.getaddrinfo("sentinel.invalid", 443)
            with self.assertRaises(AssertionError):
                socket.socket.connect(None, ("127.0.0.1", 1))
            inspection = inspect_mock_result(*self.values, self.result)
            review = review_mock_result(*self.values, self.result, inspection, CHANGES)
            self.assertEqual(validate_mock_review(review, *self.values, self.result, inspection), review)

    def test_cli_inspect_review_check_preserves_outputs_and_explicit_failed_report(self):
        folder = self.base / "cli"
        folder.mkdir()
        inputs = []
        for index, value in enumerate(self.values):
            path = folder / f"input-{index}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            inputs.append(str(path))
        inspection, review, request = (folder / name for name in ("inspection.json", "review.json", "request.json"))
        request.write_text(json.dumps(ACCEPT), encoding="utf-8")
        def run(name, *extra, result=self.result):
            return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", name,
                                   *inputs, str(result), *map(str, extra)], cwd=ROOT,
                                  capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(run("inspect-result-mock", inspection).returncode, 0)
        self.assertEqual(run("review-result-mock", inspection, request, review).returncode, 0)
        checked = run("check-result-review-mock", inspection, review)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(json.loads(checked.stdout)["status"], "accepted_mock_result")
        preserved = review.read_bytes()
        self.assertEqual(run("review-result-mock", inspection, request, review).returncode, 2)
        self.assertEqual(review.read_bytes(), preserved)
        failed_report, forbidden_accept = folder / "failed.json", folder / "must-not-exist.json"
        self.assertEqual(run("inspect-result-mock", failed_report, result=self.base / "absent").returncode, 2)
        self.assertEqual(json.loads(failed_report.read_text())["status"], "blocked")
        self.assertEqual(run("review-result-mock", failed_report, request, forbidden_accept,
                             result=self.base / "absent").returncode, 2)
        self.assertFalse(forbidden_accept.exists())

    def test_cli_strict_json_does_not_create_review(self):
        folder = self.base / "strict-cli"
        folder.mkdir()
        inputs = []
        for index, value in enumerate(self.values):
            path = folder / f"input-{index}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            inputs.append(str(path))
        inspection = folder / "inspection.json"
        inspection.write_text(json.dumps(self.inspection), encoding="utf-8")
        for index, text in enumerate(("null", '{"schema_version":1,"schema_version":1}',
                                      '{"schema_version":NaN}', '{"schema_version":1,"extra":true}')):
            request, output = folder / f"bad-{index}.json", folder / f"out-{index}.json"
            request.write_text(text, encoding="utf-8")
            result = subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", "review-result-mock",
                                     *inputs, str(self.result), str(inspection), str(request), str(output)],
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
