"""Real API adapter exercised with synthetic keys and in-memory HTTP only."""

from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from src import openai_api as api
from src.openai_mock import synthetic_response
from src.research_mock import search_mock
from src.shorts import is_approved
from test_shorts import BRIEF
import test_gui_openai_mock as gui_mock


REAL_CLIENT = httpx.Client
SYNTHETIC_KEY = "sk-synthetic-api-test-only"


@contextmanager
def transport(body=None, status=200, failure=None):
    seen = []
    def handle(request):
        seen.append(request)
        if failure:
            raise failure
        return httpx.Response(status, json=synthetic_response(BRIEF) if body is None else body)
    def client(**options):
        return REAL_CLIENT(transport=httpx.MockTransport(handle), **options)
    with patch.object(api, "_api_key", return_value=SYNTHETIC_KEY), \
            patch.object(api.httpx, "Client", side_effect=client):
        yield seen


class ApiProviderTests(unittest.TestCase):
    def test_single_fixed_request_and_reasoning_response_produce_unapproved_plan(self):
        body = synthetic_response(BRIEF)
        body["output"].insert(0, {"type": "reasoning", "summary": []})
        with transport(body) as seen, patch("socket.socket.connect", side_effect=AssertionError("external network")):
            result = api.create_api_draft(BRIEF)
        self.assertEqual(len(seen), 1)
        request = seen[0]
        self.assertEqual(str(request.url), api.API_URL)
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer " + SYNTHETIC_KEY)
        data = json.loads(request.content)
        self.assertEqual(data["model"], "gpt-6.1-sol")
        self.assertFalse(data["store"])
        self.assertEqual(data["max_output_tokens"], 4096)
        self.assertTrue(data["text"]["format"]["strict"])
        self.assertEqual(json.loads(data["input"]), BRIEF)
        self.assertEqual(result["source"], api.SOURCE)
        self.assertIsNone(result["approval"])
        self.assertFalse(is_approved(result))
        self.assertNotIn(SYNTHETIC_KEY, json.dumps(result))

    def test_research_is_sent_as_untrusted_data_and_preserved(self):
        research = search_mock(BRIEF)
        before = deepcopy(research)
        with transport() as seen:
            result = api.create_api_draft(BRIEF, research=research)
        sent = json.loads(json.loads(seen[0].content)["input"])
        self.assertEqual(sent["reference_data"]["sources"], research["sources"])
        self.assertEqual(result["research"], before)
        self.assertEqual(research, before)

    def test_invalid_or_oversized_input_never_reads_credentials_or_calls(self):
        invalid = dict(BRIEF, target_seconds=0)
        large = dict(BRIEF, topic="가" * 20_000)
        with patch.object(api, "_api_key", side_effect=AssertionError("key read")):
            for brief in (invalid, large):
                with self.subTest(brief_size=len(brief["topic"])), self.assertRaises(ValueError):
                    api.create_api_draft(brief)

    def test_env_file_key_and_environment_precedence_without_global_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / ".env"
            config.write_text('# comment\nOPENAI_API_KEY="sk-file-test-only"\n', encoding="utf-8-sig")
            with patch.object(api, "ENV_FILE", config), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(api._api_key(), "sk-file-test-only")
                self.assertNotIn("OPENAI_API_KEY", os.environ)
                with patch.dict(os.environ, {"OPENAI_API_KEY": SYNTHETIC_KEY}):
                    self.assertEqual(api._api_key(), SYNTHETIC_KEY)

    def test_missing_duplicate_malformed_or_oversized_key_is_rejected_locally(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / ".env"
            with patch.object(api, "ENV_FILE", config), patch.dict(os.environ, {}, clear=True), \
                    patch.object(api.httpx, "Client", side_effect=AssertionError("unexpected client")):
                with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
                    api.create_api_draft(BRIEF)
                for value in ("OPENAI_API_KEY=", "OPENAI_API_KEY=sk-한글", "OPENAI_API_KEY=sk-a b",
                              "OPENAI_API_KEY=sk-one\nOPENAI_API_KEY=sk-two", "x" * 17_000):
                    config.write_text(value, encoding="utf-8")
                    with self.subTest(size=len(value)), self.assertRaises(ValueError):
                        api.create_api_draft(BRIEF)

    def test_errors_redirects_and_timeouts_never_retry_or_expose_response(self):
        for status in (301, 401, 403, 404, 429, 500):
            with self.subTest(status=status), transport({"error": SYNTHETIC_KEY}, status) as seen:
                with self.assertRaises(ValueError) as caught:
                    api.create_api_draft(BRIEF)
                self.assertNotIn(SYNTHETIC_KEY, str(caught.exception))
                self.assertEqual(len(seen), 1)
        with transport(failure=httpx.ReadTimeout(SYNTHETIC_KEY)) as seen:
            with self.assertRaises(ValueError) as caught:
                api.create_api_draft(BRIEF)
            self.assertNotIn(SYNTHETIC_KEY, str(caught.exception))
            self.assertEqual(len(seen), 1)

    def test_refusal_incomplete_tool_calls_and_invalid_creative_cannot_be_saved(self):
        cases = []
        incomplete = synthetic_response(BRIEF)
        incomplete["status"] = "incomplete"
        cases.append(incomplete)
        refusal = synthetic_response(BRIEF)
        refusal["output"][0]["content"] = [{"type": "refusal", "refusal": "synthetic refusal"}]
        cases.append(refusal)
        tools = synthetic_response(BRIEF)
        tools["output"].append({"type": "function_call"})
        cases.append(tools)
        for mutation in (lambda p: p.update(approval={"forged": True}),
                         lambda p: p.update(hook="과장 광고"),
                         lambda p: p["scenes"][0].update(duration_seconds=1000)):
            body = synthetic_response(BRIEF)
            content = body["output"][0]["content"][0]
            creative = json.loads(content["text"])
            mutation(creative)
            content["text"] = json.dumps(creative)
            cases.append(body)
        for text in ('{"hook":"x","hook":"y"}', '{"hook":NaN}', 'not JSON'):
            body = synthetic_response(BRIEF)
            body["output"][0]["content"][0]["text"] = text
            cases.append(body)
        for body in cases:
            with self.subTest(case=cases.index(body)), transport(body) as seen, self.assertRaises(ValueError):
                api.create_api_draft(BRIEF)
            self.assertEqual(len(seen), 1)

    def test_response_byte_limit(self):
        with transport({"padding": "a" * (api.MAX_RESPONSE_BYTES + 1)}), \
                self.assertRaisesRegex(ValueError, "크기"):
            api.create_api_draft(BRIEF)

    def test_slow_small_chunks_check_elapsed_budget_without_4096_byte_buffering(self):
        clock = [0]
        class SlowStream(httpx.SyncByteStream):
            def __iter__(self):
                for _ in range(4):
                    clock[0] += 40
                    yield b" " * 1024
        def handle(request):
            return httpx.Response(200, stream=SlowStream())
        def client(**options):
            self.assertEqual(options["timeout"].read, 120)
            self.assertEqual(options["timeout"].connect, 10)
            return REAL_CLIENT(transport=httpx.MockTransport(handle), **options)
        with patch.object(api, "_api_key", return_value=SYNTHETIC_KEY), \
                patch.object(api.httpx, "Client", side_effect=client), \
                patch.object(api.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(ValueError, "時間|시간"):
                api.create_api_draft(BRIEF)
        self.assertEqual(clock[0], 120)


class GuiApiTests(unittest.TestCase):
    setUp = gui_mock.GuiApiMockTests.setUp
    tearDown = gui_mock.GuiApiMockTests.tearDown
    request = gui_mock.GuiApiMockTests.request
    create = gui_mock.GuiApiMockTests.create
    action = gui_mock.GuiApiMockTests.action
    snapshot = gui_mock.GuiApiMockTests.snapshot

    def test_explicit_api_mode_and_existing_approvals_never_recall_provider(self):
        with transport() as seen, patch("src.gui_workflow.produce_mock_media", side_effect=AssertionError("implicit render")):
            state = self.create("openai_api")
            self.assertEqual(state["draft"]["source"], api.SOURCE)
            self.assertEqual(state["status"], "draft")
            self.assertIsNone(state["draft"]["approval"])
            self.assertEqual(self.request("GET", "/api/bootstrap")[0], 200)
            self.assertEqual(self.request("GET", f"/api/jobs/{state['id']}")[0], 200)
            self.workflow.__class__(self.base).view(state["id"])
            self.action(state, "produce", expected=400)
            state = self.action(state, "approve_plan")
            state = self.action(state, "prepare")
            self.action(state, "produce", expected=400)
            state = self.action(state, "approve_production", {"approved_by": "synthetic test", "reason": "test only"})
            self.assertEqual(state["status"], "production_approved")
            self.assertFalse(state["real_execution_allowed"])
            self.assertEqual(len(seen), 1)

    def test_missing_key_and_provider_failures_preserve_all_existing_files(self):
        old = self.create("local_template")
        before = self.snapshot()
        with patch("src.gui_workflow.create_api_draft", side_effect=ValueError("API 키가 없습니다.")) as mocked:
            code, raw = self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": "openai_api"})
            self.assertEqual(code, 400)
            self.assertIn("API 키", json.loads(raw)["error"])
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.workflow.view(old["id"])["status"], "draft")
            mocked.assert_called_once()

    def test_web_cannot_supply_credentials_model_endpoint_or_live_switch(self):
        with patch("src.gui_workflow.create_api_draft", side_effect=AssertionError("unexpected API")):
            for key, value in (("api_key", SYNTHETIC_KEY), ("model", "other"),
                               ("endpoint", "https://example.invalid"), ("live", True)):
                code, _ = self.request("POST", "/api/jobs", dict(brief=BRIEF, mode="openai_api", **{key: value}))
                self.assertEqual(code, 400)
            code, _ = self.request("POST", "/api/jobs", {"brief": dict(BRIEF, api_key=SYNTHETIC_KEY), "mode": "openai_api"})
            self.assertEqual(code, 400)
            self.assertEqual(list(self.base.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
