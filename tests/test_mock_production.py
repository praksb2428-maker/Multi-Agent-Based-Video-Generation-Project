import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.direction import create_direction, create_prompts, _canonical
from src.mock_production import (create_mock_quote, validate_mock_quote,
                                 approve_mock_production, validate_mock_approval)
from src.shorts import approve_plan, create_draft, revise_plan
from test_direction import NoEnvironmentReads
from test_plan_revision import REQUEST
from test_shorts import BRIEF


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 30, 12, tzinfo=timezone.utc)
PRICING = {"schema_version": 1, "source": "fictional_test_only", "unit": "mock_credit",
           "video_per_second": 2, "narration_per_100_characters": 1, "assembly_fixed": 5}


def inputs(budget=10000, pricing=None):
    plan = approve_plan(create_draft(dict(BRIEF, max_budget=budget)))
    direction = create_direction(plan)
    prompts = create_prompts(plan, direction)
    return plan, direction, prompts, copy.deepcopy(PRICING if pricing is None else pricing)


def approval_for(values, quote, now=NOW):
    return approve_mock_production(*values, quote, approved_by="mock CLI tester",
                                   reason="합성 견적 확인", now=now)


class MockProductionTests(unittest.TestCase):
    def test_quote_and_approval_work_without_network_keys_or_input_mutation(self):
        values = inputs()
        before = copy.deepcopy(values)
        with patch("socket.socket.connect", side_effect=AssertionError("no network")), \
                patch("socket.create_connection", side_effect=AssertionError("no network")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("no DNS")), \
                patch("os.environ", NoEnvironmentReads()), \
                patch("os.getenv", side_effect=AssertionError("no environment")):
            quote = create_mock_quote(*values)
            approval = approval_for(values, quote)
            validate_mock_approval(json.loads(json.dumps(approval)), *values, quote, now=NOW)
        self.assertEqual(values, before)
        self.assertEqual(quote["total_units"], 68)
        self.assertEqual(quote["source"], "fictional_test_only")
        self.assertEqual(approval["scope"], "mock_only")
        self.assertIs(approval["real_execution_allowed"], False)
        self.assertIsNone(values[2]["production_approval"])

    def test_rounding_is_per_scene_second_and_unicode_100_character_block(self):
        draft = create_draft(BRIEF)
        for scene, seconds in zip(draft["scenes"], (0.1, 14.8, 15.1)):
            scene["duration_seconds"] = seconds
        draft["scenes"][0]["script"] = "가" * 101
        plan = approve_plan(draft)
        direction = create_direction(plan)
        quote = create_mock_quote(plan, direction, create_prompts(plan, direction), PRICING)
        self.assertEqual([line["billable_seconds"] for line in quote["lines"]], [1, 15, 16])
        self.assertEqual(quote["lines"][0]["narration_characters"], 101)
        self.assertEqual(quote["lines"][0]["narration_blocks"], 2)
        self.assertEqual(quote["total_units"], 73)

    def test_budget_below_equal_above_and_zero(self):
        for budget in (67, 68, 68.0, 69, 0):
            values = inputs(budget)
            quote = create_mock_quote(*values)
            self.assertEqual(quote["within_budget"], budget >= 68)
            if budget >= 68:
                validate_mock_approval(approval_for(values, quote), *values, quote, now=NOW)
            else:
                with self.assertRaisesRegex(ValueError, "budget"):
                    approval_for(values, quote)
        zero = {**PRICING, "video_per_second": 0, "narration_per_100_characters": 0, "assembly_fixed": 0}
        values = inputs(0, zero)
        quote = create_mock_quote(*values)
        self.assertEqual(quote["total_units"], 0)
        validate_mock_approval(approval_for(values, quote), *values, quote, now=NOW)

    def test_invalid_price_contract_and_rates_are_rejected(self):
        for field, value in (("schema_version", True), ("schema_version", 2), ("unit", "KRW"),
                             ("source", "real_provider"), ("video_per_second", -1),
                             ("assembly_fixed", True), ("video_per_second", 0.1),
                             ("narration_per_100_characters", float("nan")),
                             ("assembly_fixed", float("inf")), ("assembly_fixed", 1_000_000_001)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                create_mock_quote(*inputs(pricing={**PRICING, field: value}))
        for pricing in (None, [], {}, {**PRICING, "extra": 1}):
            values = list(inputs())
            values[3] = pricing
            with self.assertRaises(ValueError):
                create_mock_quote(*values)

    def test_current_plan_direction_and_prompts_are_required(self):
        values = inputs()
        quote = create_mock_quote(*values)
        for index in (0, 1, 2, 3):
            changed = copy.deepcopy(values)
            if index == 0: changed[index]["hook"] += " 수정"
            elif index == 1: changed[index]["scenes"][0]["camera"] = "변경"
            elif index == 2: changed[index]["production_approval"] = {"approved": True}
            else: changed[index]["video_per_second"] += 1
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_mock_quote(quote, *changed)
        new_plan = approve_plan(revise_plan(values[0], REQUEST))
        with self.assertRaises(ValueError):
            create_mock_quote(new_plan, *values[1:])
        for invalid in (create_draft(BRIEF), None):
            with self.assertRaises(ValueError):
                create_mock_quote(invalid, *values[1:])

    def test_quote_totals_flags_fields_and_hashes_are_not_trusted(self):
        values = inputs()
        quote = create_mock_quote(*values)
        for field, value in (("total_units", 0), ("within_budget", False), ("within_budget", 1),
                             ("budget_limit_units", "999999"), ("real_execution_allowed", True),
                             ("plan_sha256", "0" * 64), ("schema_version", True), ("extra", 1)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                approval_for(values, {**quote, field: value})
        for value in (None, [], values[0]["approval"]):
            with self.assertRaises(ValueError):
                approval_for(values, value)

    def test_approval_identity_metadata_and_digest_tampering_are_rejected(self):
        values = inputs()
        quote = create_mock_quote(*values)
        approval = approval_for(values, quote)
        for field, value in (("reason", "변경"), ("approved_by", "다른 표기"),
                             ("quote_sha256", "0" * 64), ("scope", "live"),
                             ("real_execution_allowed", True), ("schema_version", True),
                             ("policy_version", "unknown"), ("content_sha256", "0" * 64),
                             ("expires_at", "2030-01-01T00:00:00+00:00"), ("extra", 1)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_mock_approval({**approval, field: value}, *values, quote, now=NOW)
        with self.assertRaises(ValueError):
            validate_mock_approval(values[0]["approval"], *values, quote, now=NOW)
        for name in ("approved_by", "reason"):
            kwargs = {"approved_by": "tester", "reason": "test", name: " "}
            with self.assertRaises(ValueError):
                approve_mock_production(*values, quote, now=NOW, **kwargs)

    def test_expiry_future_naive_and_non_utc_timestamps_are_rejected(self):
        values = inputs()
        quote = create_mock_quote(*values)
        approval = approval_for(values, quote)
        for current in (NOW - timedelta(microseconds=1), NOW + timedelta(hours=1)):
            with self.assertRaisesRegex(ValueError, "future|expired"):
                validate_mock_approval(approval, *values, quote, now=current)
        for value in ("2026-10-30T12:00:00", "2026-10-30T12:00:00+09:00", "bad", None):
            changed = {**approval, "approved_at": value}
            changed["content_sha256"] = sha256(_canonical({key: val for key, val in changed.items()
                                                          if key != "content_sha256"})).hexdigest()
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_mock_approval(changed, *values, quote, now=NOW)
        with self.assertRaises(ValueError):
            approval_for(values, quote, now=NOW.replace(tzinfo=None))

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    def write_inputs(self, folder, values):
        paths = [folder / name for name in ("plan.json", "direction.json", "prompts.json", "pricing.json")]
        for path, value in zip(paths, values):
            path.write_text(json.dumps(value), encoding="utf-8")
        return paths

    def test_cli_quote_approve_check_reload_and_file_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            values = inputs()
            paths = self.write_inputs(folder, values)
            originals = [path.read_bytes() for path in paths]
            quote_path, approval_path = folder / "quote.json", folder / "approval.json"
            for args in (("quote-mock", *paths, quote_path),
                         ("approve-production-mock", *paths, quote_path, approval_path,
                          "--approved-by", "mock tester", "--reason", "모의 확인"),
                         ("check-production-mock", *paths, quote_path, approval_path)):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
            quote = json.loads(quote_path.read_text(encoding="utf-8"))
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            validate_mock_approval(approval, *values, quote)
            for args, path in ((("quote-mock", *paths, quote_path), quote_path),
                               (("approve-production-mock", *paths, quote_path, approval_path,
                                 "--approved-by", "tester", "--reason", "test"), approval_path)):
                before = path.read_bytes()
                self.assertEqual(self.run_cli(*args).returncode, 2)
                self.assertEqual(path.read_bytes(), before)
            self.assertEqual([path.read_bytes() for path in paths], originals)

    def test_cli_overbudget_invalid_pricing_and_tampering_do_not_create_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            paths = self.write_inputs(folder, inputs(0))
            quote_path, target = folder / "quote.json", folder / "approval.json"
            self.assertEqual(self.run_cli("quote-mock", *paths, quote_path).returncode, 0)
            result = self.run_cli("approve-production-mock", *paths, quote_path, target,
                                  "--approved-by", "tester", "--reason", "test")
            self.assertEqual(result.returncode, 2)
            self.assertFalse(target.exists())
            for content in ("null", "{", '{"schema_version":1,"schema_version":1}',
                            '{"schema_version":1,"video_per_second":NaN}'):
                paths[3].write_text(content, encoding="utf-8")
                result = self.run_cli("quote-mock", *paths, target)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
