import copy
import json
import math
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


if __name__ == "__main__":
    unittest.main()
