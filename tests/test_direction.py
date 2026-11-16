import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.direction import create_direction, create_prompts, validate_direction
from src.shorts import approve_plan, create_draft, revise_plan
from test_shorts import BRIEF
from test_plan_revision import REQUEST


ROOT = Path(__file__).resolve().parents[1]


class NoEnvironmentReads(dict):
    def get(self, *args, **kwargs):
        raise AssertionError("environment read is forbidden")

    def __getitem__(self, key):
        raise AssertionError("environment read is forbidden")


class DirectionTests(unittest.TestCase):
    def test_approved_legacy_and_revision_plans_generate_without_network_or_keys(self):
        plans = (approve_plan(create_draft(BRIEF)),
                 approve_plan(revise_plan(create_draft(BRIEF), REQUEST)))
        for plan in plans:
            before = copy.deepcopy(plan)
            with patch("socket.socket.connect", side_effect=AssertionError("no network")), \
                    patch("socket.create_connection", side_effect=AssertionError("no network")), \
                    patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")), \
                    patch("os.environ", NoEnvironmentReads()), \
                    patch("os.getenv", side_effect=AssertionError("no environment")):
                direction = create_direction(plan)
                prompts = create_prompts(plan, json.loads(json.dumps(direction)))
            self.assertEqual(plan, before)
            self.assertEqual(direction["plan_sha256"], plan["approval"]["content_sha256"])
            self.assertEqual(prompts["plan_sha256"], direction["plan_sha256"])
            self.assertEqual(prompts["source"], "local_rule_template")
            for field in ("provider", "model", "cost_estimate", "production_approval"):
                self.assertIsNone(prompts[field])
            self.assertEqual(prompts["status"], "draft")

    def test_scene_conditions_and_prompt_trace_are_preserved(self):
        plan = approve_plan(create_draft(BRIEF))
        direction = create_direction(plan)
        prompts = create_prompts(plan, direction)
        self.assertEqual(direction["conditions"], plan["brief"])
        self.assertEqual(prompts["must_avoid"], BRIEF["forbidden"])
        self.assertEqual(prompts["context"], {"hook": plan["hook"], "story": plan["story"]})
        for original, derived, rendered in zip(plan["scenes"], direction["scenes"], prompts["scenes"]):
            for field, value in original.items():
                self.assertEqual(derived[field], value)
            self.assertEqual(derived["lighting"]["origin"], "local_default")
            self.assertEqual(derived["audio"]["origin"], "local_default")
            self.assertIsNone(derived["audio"]["background_music"])
            for value in (original["script"], original["background"], original["action"],
                          original["camera"], str(original["duration_seconds"]),
                          BRIEF["aspect_ratio"], BRIEF["style"], BRIEF["audience"],
                          plan["hook"], plan["story"],
                          derived["lighting"]["value"]):
                self.assertIn(value, rendered["prompt"])
            for term in BRIEF["forbidden"]:
                self.assertNotIn(term, rendered["prompt"])
        canonical = json.dumps(direction, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.assertEqual(prompts["direction_sha256"], sha256(canonical).hexdigest())

    def test_unapproved_revised_and_tampered_plans_are_rejected(self):
        approved = approve_plan(create_draft(BRIEF))
        tampered = copy.deepcopy(approved)
        tampered["hook"] += " 변경"
        for plan in (None, create_draft(BRIEF), revise_plan(approved, REQUEST), tampered):
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, "approved plan"):
                create_direction(plan)
            with self.assertRaisesRegex(ValueError, "approved plan"):
                create_prompts(plan, {})

    def test_stale_and_wrong_parent_directions_are_rejected(self):
        first = approve_plan(create_draft(BRIEF))
        direction = create_direction(first)
        second = approve_plan(revise_plan(first, REQUEST))
        with self.assertRaisesRegex(ValueError, "does not match"):
            create_prompts(second, direction)
        direction["plan_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match"):
            create_prompts(first, direction)

    def test_modified_direction_fields_and_conditions_are_rejected(self):
        plan = approve_plan(create_draft(BRIEF))
        original = create_direction(plan)
        for mutation in ("missing", "extra", "number", "duration", "script", "lighting", "audio", "conditions", "source", "nan"):
            direction = copy.deepcopy(original)
            if mutation == "missing":
                del direction["scenes"][0]["camera"]
            elif mutation == "extra":
                direction["approved"] = True
            elif mutation == "conditions":
                direction["conditions"]["max_budget"] += 1
            elif mutation == "source":
                direction["source"] = "actual_ai"
            else:
                scene = direction["scenes"][0]
                if mutation == "number": scene["number"] = True
                elif mutation == "duration": scene["duration_seconds"] += 100
                elif mutation == "script": scene["script"] = "과장 광고"
                elif mutation == "lighting": scene["lighting"]["value"] = "임의 수정"
                elif mutation == "audio": scene["audio"]["background_music"] = "임의 음악"
                else: scene["duration_seconds"] = float("nan")
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                create_prompts(plan, direction)

    def test_direction_unknown_schema_and_nonobjects_are_rejected(self):
        plan = approve_plan(create_draft(BRIEF))
        for value in (None, [], {}, {**create_direction(plan), "schema_version": True},
                      {**create_direction(plan), "schema_version": 2}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_direction(value, plan)

    def test_forbidden_terms_do_not_enter_default_or_positive_prompt(self):
        plan = approve_plan(create_draft(dict(BRIEF, forbidden=["기본 조명"])))
        with self.assertRaisesRegex(ValueError, "forbidden"):
            create_direction(plan)
        plan = approve_plan(create_draft(dict(BRIEF, style="과장 광고 스타일")))
        direction = create_direction(plan)
        with self.assertRaisesRegex(ValueError, "forbidden"):
            create_prompts(plan, direction)

    def test_returned_artifacts_do_not_alias_input(self):
        plan = approve_plan(create_draft(BRIEF))
        direction = create_direction(plan)
        saved = copy.deepcopy(direction)
        prompts = create_prompts(plan, direction)
        prompts["must_avoid"].append("추가")
        self.assertEqual(direction, saved)
        direction["conditions"]["style"] = "변경"
        direction["scenes"][0]["script"] = "변경"
        self.assertEqual(plan["brief"]["style"], BRIEF["style"])
        self.assertNotEqual(plan["scenes"][0]["script"], "변경")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    def test_cli_direction_prompts_reload_and_preserve_input_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            plan_file, direction_file, prompt_file = (folder / name for name in ("plan.json", "direction.json", "prompts.json"))
            plan = approve_plan(revise_plan(create_draft(BRIEF), REQUEST))
            plan_file.write_text(json.dumps(plan), encoding="utf-8")
            original_bytes = plan_file.read_bytes()
            for args in (("direct", plan_file, direction_file), ("prompts", plan_file, direction_file, prompt_file)):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(prompt_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["plan_sha256"], plan["approval"]["content_sha256"])
            for args, file in ((("direct", plan_file, direction_file), direction_file),
                               (("prompts", plan_file, direction_file, prompt_file), prompt_file),
                               (("direct", plan_file, plan_file), plan_file)):
                before = file.read_bytes()
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(file.read_bytes(), before)
            self.assertEqual(plan_file.read_bytes(), original_bytes)

    def test_cli_rejection_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            plan_file, direction_file, target = (folder / name for name in ("plan.json", "direction.json", "out.json"))
            approved = approve_plan(create_draft(BRIEF))
            plan_file.write_text(json.dumps(create_draft(BRIEF)), encoding="utf-8")
            result = self.run_cli("direct", plan_file, target)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(target.exists())
            plan_file.write_text(json.dumps(approved), encoding="utf-8")
            for text in ("null", "{", '{"schema_version":1,"schema_version":2}',
                         '{"schema_version":1,"scenes":[NaN]}',
                         json.dumps({**create_direction(approved), "plan_sha256": "0" * 64})):
                direction_file.write_text(text, encoding="utf-8")
                result = self.run_cli("prompts", plan_file, direction_file, target)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
