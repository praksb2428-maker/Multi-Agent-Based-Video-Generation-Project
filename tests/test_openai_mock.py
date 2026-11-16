"""Local transport contract checks; a socket or credential read fails the test."""

from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.openai_mock import CREATIVE_SCHEMA, MOCK_URL, MODEL, create_mock_draft, synthetic_response
from src.shorts import approve_plan, is_approved


ROOT = Path(__file__).resolve().parents[1]
BRIEF = json.loads((ROOT / "examples/shorts_brief.json").read_text(encoding="utf-8"))


def replace_creative(response, change):
    creative = json.loads(response["output"][0]["content"][0]["text"])
    change(creative)
    response["output"][0]["content"][0]["text"] = json.dumps(creative)
    return response


class MockPlanningTests(unittest.TestCase):
    def setUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo"):
            self.guards.enter_context(patch(target, side_effect=AssertionError("network forbidden")))

    def test_real_sdk_serializes_one_request_without_network_or_key_reads(self):
        requests = []
        env_type = type(os.environ)
        original_getitem = env_type.__getitem__

        def guarded_getitem(environment, key):
            if key.startswith("OPENAI_") or key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                raise AssertionError("credential/proxy environment read forbidden")
            return original_getitem(environment, key)

        with patch.object(env_type, "__getitem__", guarded_getitem):
            plan = create_mock_draft(BRIEF, request_log=requests)
        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request["url"], MOCK_URL + "responses")
        self.assertEqual(request["method"], "POST")
        body = request["body"]
        self.assertEqual(body["model"], MODEL)
        self.assertFalse(body["store"])
        self.assertEqual(body["max_output_tokens"], 4096)
        self.assertEqual(json.loads(body["input"]), BRIEF)
        self.assertEqual(body["text"]["format"], {
            "type": "json_schema", "name": "shorts_creative_v1", "strict": True,
            "schema": CREATIVE_SCHEMA})
        self.assertEqual(plan["source"], "openai_mock")
        self.assertEqual(plan["brief"], BRIEF)
        self.assertEqual(plan["status"], "draft")
        self.assertIsNone(plan["approval"])
        self.assertIsNone(plan["cost_estimate"])
        self.assertTrue(is_approved(json.loads(json.dumps(approve_plan(plan)))))

    def test_invalid_brief_is_rejected_before_sdk_request(self):
        requests = []
        with self.assertRaisesRegex(ValueError, "missing brief"):
            create_mock_draft({"topic": "test"}, request_log=requests)
        self.assertEqual(requests, [])

    def test_refusal_is_not_replaced_with_template(self):
        response = json.loads((ROOT / "examples/mock_refusal.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "refused"):
            create_mock_draft(BRIEF, response_body=response)

    def test_explicit_null_fixture_is_rejected_before_sdk_request(self):
        requests = []
        with self.assertRaisesRegex(ValueError, "fixture must be an object"):
            create_mock_draft(BRIEF, response_body=None, request_log=requests)
        self.assertEqual(requests, [])

    def test_incomplete_failed_and_missing_envelopes_are_rejected(self):
        for status in ("incomplete", "failed", "in_progress", None):
            response = synthetic_response(BRIEF)
            response["status"] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                create_mock_draft(BRIEF, response_body=response)
        for field in ("output", "status"):
            response = synthetic_response(BRIEF)
            del response[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                create_mock_draft(BRIEF, response_body=response)
        response = synthetic_response(BRIEF)
        response["incomplete_details"] = {"reason": "max_output_tokens"}
        with self.assertRaises(ValueError):
            create_mock_draft(BRIEF, response_body=response)

    def test_empty_invalid_and_duplicate_json_are_rejected(self):
        for text in ("", "{", "[]", "null", '{"hook":"one","hook":"two"}',
                     '{"hook":NaN,"story":"test","scenes":[]}'):
            response = synthetic_response(BRIEF)
            response["output"][0]["content"][0]["text"] = text
            with self.subTest(text=text), self.assertRaises(ValueError):
                create_mock_draft(BRIEF, response_body=response)

    def test_response_cannot_set_approval_constraints_provenance_or_cost(self):
        for field, value in (("approval", {"approved": True}), ("status", "approved"),
                             ("brief", BRIEF), ("source", "openai_live"), ("cost_estimate", 0)):
            response = replace_creative(synthetic_response(BRIEF),
                                        lambda data: data.update({field: value}))
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "only hook"):
                create_mock_draft(BRIEF, response_body=response)

    def test_creative_contract_and_project_validation_are_enforced(self):
        changes = (
            lambda data: data.pop("hook"),
            lambda data: data.update(hook=""),
            lambda data: data.update(scenes=[]),
            lambda data: data["scenes"][0].pop("camera"),
            lambda data: data["scenes"][0].update(extra="not allowed"),
            lambda data: data["scenes"][0].update(number=2),
            lambda data: data["scenes"][0].update(duration_seconds=100),
            lambda data: data["scenes"][0].update(duration_seconds=True),
            lambda data: data.update(hook="과장 광고"),
        )
        for index, change in enumerate(changes):
            response = replace_creative(synthetic_response(BRIEF), change)
            with self.subTest(case=index), self.assertRaises(ValueError):
                create_mock_draft(BRIEF, response_body=response)

    def test_http_errors_are_not_retried_or_fallback(self):
        for status in (401, 429, 500):
            requests = []
            with self.subTest(status=status), self.assertRaisesRegex(ValueError, "no live fallback"):
                create_mock_draft(BRIEF, status_code=status,
                                  response_body={"error": {"message": "synthetic failure"}},
                                  request_log=requests)
            self.assertEqual(len(requests), 1)

    def test_unsupported_or_empty_output_is_rejected(self):
        responses = []
        for output in ([], [{"type": "function_call", "name": "unexpected"}]):
            response = synthetic_response(BRIEF)
            response["output"] = output
            responses.append(response)
        for content in ([], [{"type": "output_text"}]):
            response = synthetic_response(BRIEF)
            response["output"][0]["content"] = content
            responses.append(response)
        for index, response in enumerate(responses):
            with self.subTest(case=index), self.assertRaises(ValueError):
                create_mock_draft(BRIEF, response_body=response)

    def test_approval_is_invalidated_by_mock_content_change(self):
        approved = approve_plan(create_mock_draft(BRIEF))
        for field in ("hook", "source"):
            changed = copy.deepcopy(approved)
            changed[field] += " changed"
            self.assertFalse(is_approved(changed))


class MockCliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    def test_cli_mock_draft_approval_and_file_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            draft, approved = Path(directory) / "draft.json", Path(directory) / "approved.json"
            result = self.run_cli("draft-mock", ROOT / "examples/shorts_brief.json", draft)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = json.loads(draft.read_text(encoding="utf-8"))
            self.assertEqual(saved["source"], "openai_mock")
            result = self.run_cli("approve", draft, approved)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(is_approved(json.loads(approved.read_text(encoding="utf-8"))))
            original = draft.read_bytes()
            result = self.run_cli("draft-mock", ROOT / "examples/shorts_brief.json", draft)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(draft.read_bytes(), original)

    def test_cli_refusal_and_bad_fixture_do_not_write_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "must_not_exist.json"
            for fixture in (ROOT / "examples/mock_refusal.json", ROOT / "examples/shorts_brief.json"):
                result = self.run_cli("draft-mock", ROOT / "examples/shorts_brief.json", output,
                                      "--mock-response", fixture)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(output.exists())

    def test_cli_null_fixture_does_not_fall_back_to_success(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "null.json"
            output = Path(directory) / "must_not_exist.json"
            fixture.write_text("null", encoding="utf-8")
            result = self.run_cli("draft-mock", ROOT / "examples/shorts_brief.json", output,
                                  "--mock-response", fixture)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("fixture must be an object", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
