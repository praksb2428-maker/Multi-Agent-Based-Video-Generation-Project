import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.shorts import approve_plan, create_draft, is_approved, revise_plan, validate_plan
from test_shorts import BRIEF


REQUEST = {"schema_version": 1, "feedback": "도입 질문을 쉽게 수정",
           "changes": {"hook": "오늘 분리배출을 해볼까요?"}}
ROOT = Path(__file__).resolve().parents[1]


class RevisionTests(unittest.TestCase):
    def test_draft_and_approved_revision_clear_approval_and_preserve_original(self):
        for original in (create_draft(BRIEF), approve_plan(create_draft(BRIEF))):
            saved = copy.deepcopy(original)
            request = copy.deepcopy(REQUEST)
            with patch("socket.socket.connect", side_effect=AssertionError("no network")):
                revised = revise_plan(original, request)
            self.assertEqual(original, saved)
            self.assertEqual(request, REQUEST)
            self.assertEqual(revised["status"], "draft")
            self.assertIsNone(revised["approval"])
            self.assertFalse(is_approved(revised))
            self.assertEqual(revised["brief"], original["brief"])
            self.assertEqual(revised["source"], original["source"])
            self.assertEqual(revised["revision"]["number"], 1)
            self.assertTrue(is_approved(json.loads(json.dumps(approve_plan(revised)))))

    def test_legacy_digest_stays_compatible(self):
        plan = create_draft(BRIEF)
        fields = ("schema_version", "source", "brief", "hook", "story", "scenes")
        digest = hashlib.sha256(json.dumps({key: plan[key] for key in fields},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(approve_plan(plan)["approval"]["content_sha256"], digest)

    def test_revision_history_is_bound_to_approval_and_next_parent(self):
        first = approve_plan(revise_plan(create_draft(BRIEF), REQUEST))
        for field, value in {"feedback": "다른 사유", "number": 2,
                             "changed_fields": ["story"], "parent_content_sha256": "0" * 64}.items():
            changed = copy.deepcopy(first)
            changed["revision"][field] = value
            self.assertFalse(is_approved(changed), field)
        second = revise_plan(first, {"schema_version": 1, "feedback": "요약 순서 수정",
                                    "changes": {"story": "질문 → 예시 → 실천"}})
        self.assertEqual(second["revision"]["number"], 2)
        self.assertEqual(second["revision"]["parent_content_sha256"], first["approval"]["content_sha256"])
        self.assertTrue(is_approved(approve_plan(second)))

    def test_tampered_approved_and_stale_draft_are_rejected(self):
        original = approve_plan(create_draft(BRIEF))
        original["hook"] += " 변조"
        with self.assertRaisesRegex(ValueError, "invalid approved"):
            revise_plan(original, REQUEST)
        original["status"] = "draft"
        with self.assertRaisesRegex(ValueError, "must not carry"):
            revise_plan(original, REQUEST)

    def test_invalid_request_and_protected_fields_are_rejected(self):
        for request in (None, [], {}, {**REQUEST, "extra": True},
                        {**REQUEST, "schema_version": True}, {**REQUEST, "schema_version": 2},
                        {**REQUEST, "feedback": " "}, {**REQUEST, "feedback": 1},
                        {**REQUEST, "changes": None}, {**REQUEST, "changes": {}},
                        {**REQUEST, "changes": {"hook": None}},
                        {**REQUEST, "changes": {"story": " "}}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                revise_plan(create_draft(BRIEF), request)
        for field in ("brief", "source", "status", "approval", "cost_estimate", "revision", "unknown"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                revise_plan(create_draft(BRIEF), {**REQUEST, "changes": {field: {}}})

    def test_noop_is_rejected_and_feedback_is_not_creative_content(self):
        plan = create_draft(BRIEF)
        with self.assertRaisesRegex(ValueError, "must change"):
            revise_plan(plan, {**REQUEST, "changes": {"hook": plan["hook"]}})
        revised = revise_plan(plan, {**REQUEST, "feedback": "과장 광고 문구를 쓰지 말 것"})
        self.assertEqual(revised["hook"], REQUEST["changes"]["hook"])
        self.assertTrue(is_approved(approve_plan(revised)))

    def test_replacement_scenes_are_deep_copied_and_validated(self):
        plan = create_draft(BRIEF)
        scenes = copy.deepcopy(plan["scenes"])
        scenes[0]["script"] = "분리배출 첫 단계입니다."
        revised = revise_plan(plan, {**REQUEST, "changes": {"scenes": scenes}})
        scenes[0]["script"] = "외부 변경"
        self.assertNotEqual(revised["scenes"][0]["script"], "외부 변경")
        for mutation in ("missing", "extra", "duration", "number", "forbidden"):
            scenes = copy.deepcopy(plan["scenes"])
            if mutation == "missing":
                del scenes[0]["camera"]
            elif mutation == "extra":
                scenes[0]["approval"] = True
            elif mutation == "duration":
                scenes[0]["duration_seconds"] = 100
            elif mutation == "number":
                scenes[0]["number"] = True
            else:
                scenes[0]["script"] = "과장 광고"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                revise_plan(plan, {**REQUEST, "changes": {"scenes": scenes}})

    def test_invalid_history_is_rejected(self):
        plan = revise_plan(create_draft(BRIEF), REQUEST)
        for value in (None, {}, {**plan["revision"], "schema_version": 2},
                      {**plan["revision"], "number": True},
                      {**plan["revision"], "parent_content_sha256": "bad"},
                      {**plan["revision"], "changed_fields": ["hook", "hook"]},
                      {**plan["revision"], "changed_fields": [None]}):
            changed = copy.deepcopy(plan)
            changed["revision"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_plan(changed)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    def test_cli_revision_reapproval_roundtrip_and_file_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            original, request = folder / "original.json", folder / "request.json"
            revised, approved = folder / "revised.json", folder / "approved.json"
            original.write_text(json.dumps(approve_plan(create_draft(BRIEF))), encoding="utf-8")
            request.write_text(json.dumps(REQUEST), encoding="utf-8")
            before = original.read_bytes(), request.read_bytes()
            for args in (("revise", original, request, revised), ("approve", revised, approved)):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(is_approved(json.loads(approved.read_text(encoding="utf-8"))))
            self.assertEqual(before, (original.read_bytes(), request.read_bytes()))
            before_revised = revised.read_bytes()
            result = self.run_cli("revise", original, request, revised)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(revised.read_bytes(), before_revised)
            result = self.run_cli("revise", original, request, original)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(original.read_bytes(), before[0])

    def test_cli_rejects_malformed_requests_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            original, request, target = (folder / name for name in ("original.json", "request.json", "out.json"))
            original.write_text(json.dumps(create_draft(BRIEF)), encoding="utf-8")
            bad_values = ("null", "{", json.dumps({**REQUEST, "changes": {"status": "approved"}}),
                '{"schema_version":1,"feedback":"x","changes":{"hook":"first","hook":"second"}}',
                '{"schema_version":1,"feedback":"x","changes":{"hook":NaN}}')
            for content in bad_values:
                request.write_text(content, encoding="utf-8")
                result = self.run_cli("revise", original, request, target)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
