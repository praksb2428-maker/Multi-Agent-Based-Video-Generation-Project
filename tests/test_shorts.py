import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from src.shorts import approve_plan, create_draft, is_approved, validate_brief, validate_plan


BRIEF = {
    "topic": "재활용 분리배출의 기본",
    "target_seconds": 30,
    "aspect_ratio": "9:16",
    "style": "명확한 설명형",
    "audience": "처음 배우는 성인",
    "forbidden": ["과장 광고"],
    "max_budget": 10000,
}


class ShortsTests(unittest.TestCase):
    def run_cli(self, command, source, target):
        return subprocess.run(
            [sys.executable, "shorts_cli.py", command, str(source), str(target)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True,
            text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"))

    def test_draft_has_required_handoff_and_target_duration(self):
        plan = create_draft(BRIEF)
        self.assertEqual(plan["status"], "draft")
        self.assertEqual(plan["source"], "local_template")
        self.assertIsNone(plan["cost_estimate"])
        self.assertEqual(sum(scene["duration_seconds"] for scene in plan["scenes"]), 30)
        self.assertIs(validate_plan(plan), plan)

    def test_missing_and_forbidden_inputs_are_rejected(self):
        brief = dict(BRIEF)
        brief.pop("audience")
        with self.assertRaisesRegex(ValueError, "audience"):
            validate_brief(brief)
        brief = dict(BRIEF, forbidden=["재활용"])
        with self.assertRaisesRegex(ValueError, "forbidden"):
            create_draft(brief)
        for value in (math.nan, math.inf, True):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "target_seconds"):
                    create_draft(dict(BRIEF, target_seconds=value))

    def test_invalid_scene_and_duration_are_rejected(self):
        plan = create_draft(BRIEF)
        del plan["scenes"][0]["camera"]
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            approve_plan(plan)
        plan = create_draft(BRIEF)
        plan["scenes"][0]["duration_seconds"] = 15
        with self.assertRaisesRegex(ValueError, "tolerance"):
            approve_plan(plan)

    def test_approval_is_invalidated_by_content_change(self):
        approved = approve_plan(create_draft(BRIEF))
        self.assertTrue(is_approved(approved))
        changed = copy.deepcopy(approved)
        changed["hook"] += " 수정"
        self.assertFalse(is_approved(changed))
        with self.assertRaisesRegex(ValueError, "only draft"):
            approve_plan(approved)

    def test_cli_writes_draft_then_approved_json(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            brief = Path(directory) / "brief.json"
            draft = Path(directory) / "draft.json"
            approved = Path(directory) / "approved.json"
            brief.write_text(json.dumps(BRIEF, ensure_ascii=False), encoding="utf-8")
            for command, source, target in (("draft", brief, draft), ("approve", draft, approved)):
                result = subprocess.run([sys.executable, "shorts_cli.py", command, str(source), str(target)],
                                        cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(approved.read_text(encoding="utf-8"))
            self.assertTrue(is_approved(saved))

    def test_brief_numeric_and_ratio_boundaries(self):
        for seconds in (5, 180):
            self.assertEqual(create_draft(dict(BRIEF, target_seconds=seconds))["brief"]["target_seconds"], seconds)
        for field, values in {
            "target_seconds": (4.99, 180.01, "30", None),
            "max_budget": (-1, True, math.inf, math.nan, "10000"),
            "aspect_ratio": ("0:16", "9:0", "9/16", ""),
            "forbidden": ("term", [""], [123]),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_brief(dict(BRIEF, **{field: value}))

    def test_plan_schema_number_and_duration_contract(self):
        for version in (True, 1.0, 2, None):
            plan = create_draft(BRIEF)
            plan["schema_version"] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, "schema"):
                validate_plan(plan)
        for number in (True, 2, 1.0):
            plan = create_draft(BRIEF)
            plan["scenes"][0]["number"] = number
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, "sequential"):
                validate_plan(plan)
        for seconds in (0, -1, True, math.inf, math.nan):
            plan = create_draft(BRIEF)
            plan["scenes"][0]["duration_seconds"] = seconds
            with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, "positive"):
                validate_plan(plan)

    def test_duration_tolerance_boundaries(self):
        for delta in (-3, 3):
            plan = create_draft(BRIEF)
            plan["scenes"][1]["duration_seconds"] += delta
            self.assertIs(validate_plan(plan), plan)
        for delta in (-3.01, 3.01):
            plan = create_draft(BRIEF)
            plan["scenes"][1]["duration_seconds"] += delta
            with self.assertRaisesRegex(ValueError, "tolerance"):
                validate_plan(plan)

    def test_forbidden_terms_in_every_creative_field(self):
        for field in ("hook", "story", "script", "background", "action", "camera"):
            plan = create_draft(dict(BRIEF, forbidden=["blocked"]))
            target = plan if field in ("hook", "story") else plan["scenes"][0]
            target[field] += " BLOCKED"
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "forbidden"):
                approve_plan(plan)

    def test_approval_binds_content_and_survives_json_roundtrip(self):
        draft = create_draft(BRIEF)
        approved = approve_plan(draft)
        self.assertEqual(draft["status"], "draft")
        self.assertIsNone(draft["approval"])
        self.assertTrue(approved["approval"]["approved_at"])
        self.assertTrue(is_approved(json.loads(json.dumps(approved))))
        for field in ("source", "hook", "story", "brief", "scenes"):
            changed = copy.deepcopy(approved)
            if field == "brief":
                changed[field]["style"] += " 수정"
            elif field == "scenes":
                changed[field][0]["camera"] += " 수정"
            else:
                changed[field] += " 수정"
            with self.subTest(field=field):
                self.assertFalse(is_approved(changed))
        self.assertFalse(is_approved(draft))
        self.assertFalse(is_approved(None))

    def test_cli_rejects_invalid_input_without_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            target = Path(directory) / "output.json"
            for content in ("{", "[]", json.dumps({"topic": "test"})):
                source.write_text(content, encoding="utf-8")
                result = self.run_cli("draft", source, target)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(target.exists())
            result = self.run_cli("draft", Path(directory) / "missing.json", target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse(target.exists())

    def test_cli_preserves_existing_output_and_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            target = Path(directory) / "existing.json"
            source.write_text(json.dumps(BRIEF), encoding="utf-8")
            target.write_bytes(b"preserve existing output\n")
            source_bytes, target_bytes = source.read_bytes(), target.read_bytes()
            result = self.run_cli("draft", source, target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("output already exists", result.stderr)
            self.assertEqual(target.read_bytes(), target_bytes)
            result = self.run_cli("draft", source, source)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(source.read_bytes(), source_bytes)

    def test_cli_rejects_duplicate_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "approved.json"
            target = Path(directory) / "duplicate.json"
            approved = approve_plan(create_draft(BRIEF))
            source.write_text(json.dumps(approved), encoding="utf-8")
            result = self.run_cli("approve", source, target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("only draft", result.stderr)
            self.assertFalse(target.exists())

    def test_cli_rejects_missing_plan_source_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "draft.json"
            target = Path(directory) / "approved.json"
            plan = create_draft(BRIEF)
            del plan["source"]
            source.write_text(json.dumps(plan), encoding="utf-8")
            result = self.run_cli("approve", source, target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
