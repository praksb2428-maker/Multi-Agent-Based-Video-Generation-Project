"""GUI API-key contract rehearsals: synthetic credentials and no external calls."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch

from shorts_web import LocalServer
from src.gui_workflow import Workflow
from src.mock_media import WORKSPACE
from src.openai_mock import create_mock_draft
from src.shorts import create_draft
from test_shorts import BRIEF
import test_web


class GuiApiMockTests(unittest.TestCase):
    request = test_web.WebTests.request

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gui-api-tests-", dir=WORKSPACE)
        self.base = Path(self.temp.name)
        self.workflow = Workflow(self.base)
        self.server = LocalServer(0, self.workflow)
        self.thread = Thread(target=self.server.serve_forever)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())
        self.temp.cleanup()

    def create(self, mode="openai_mock"):
        code, raw = self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": mode})
        self.assertEqual(code, 200, raw)
        return json.loads(raw)

    def action(self, state, action, payload=None, expected=200):
        code, raw = self.request("POST", f"/api/jobs/{state['id']}/action", {
            "sequence": state["sequence"], "action": action,
            "payload": {} if payload is None else payload})
        self.assertEqual(code, expected, raw)
        return json.loads(raw)

    def snapshot(self):
        return {p.relative_to(self.base).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in self.base.rglob("*") if p.is_file()}

    def test_sdk_mode_keeps_two_approvals_revision_and_saved_original_separate(self):
        requests = []
        def provider(brief):
            return create_mock_draft(brief, request_log=requests)
        with patch("src.gui_workflow.create_mock_draft", side_effect=provider) as mocked, \
                patch("src.gui_workflow.create_local_draft", side_effect=AssertionError("real inference")), \
                patch("src.gui_workflow.produce_mock_media", side_effect=AssertionError("implicit render")) as render:
            state = self.create()
            self.assertEqual(state["status"], "draft")
            self.assertEqual(state["draft"]["source"], "openai_mock")
            self.assertIsNone(state["draft"]["approval"])
            self.assertIsNone(state["draft"]["cost_estimate"])
            self.assertFalse(state["real_execution_allowed"])
            original = self.snapshot()
            self.action(state, "prepare", expected=400)
            self.action(state, "produce", expected=400)
            self.assertEqual(self.snapshot(), original)
            state = self.action(state, "approve_plan")
            state = self.action(state, "prepare")
            self.assertEqual(state["status"], "prepared")
            self.assertNotIn("produce", state["actions"])
            self.action(state, "produce", expected=400)
            state = self.action(state, "approve_production", {
                "approved_by": "synthetic API GUI tester", "reason": "separate mock-only approval"})
            self.assertEqual(state["status"], "production_approved")
            self.assertFalse(state["real_execution_allowed"])
            self.assertEqual(Workflow(self.base).view(state["id"])["status"], "production_approved")
            self.assertEqual(self.request("GET", "/api/bootstrap")[0], 200)
            self.assertEqual(self.request("GET", f"/api/jobs/{state['id']}")[0], 200)
            # A second draft exercises explicit editing before approval, without inference.
            draft = self.create()
            before = self.snapshot()
            revised = self.action(draft, "revise_draft", {"schema_version": 1,
                "feedback": "explicit synthetic edit", "changes": {"hook": "수정된 도입 문구"}})
            self.assertEqual((revised["revision"], revised["status"]), (2, "draft"))
            self.assertIsNone(revised["draft"]["approval"])
            self.assertNotIn("prepare", revised["actions"])
            self.action(revised, "prepare", expected=400)
            for name, digest in before.items():
                self.assertEqual(sha256((self.base/name).read_bytes()).hexdigest(), digest)
            revised = self.action(revised, "approve_plan")
            revised = self.action(revised, "prepare")
            self.assertEqual(revised["status"], "prepared")
            self.action(revised, "produce", expected=400)
            self.assertEqual(mocked.call_count, 2)
            self.assertEqual(len(requests), 2)
            self.assertTrue(all(not r["body"]["store"] for r in requests))
            render.assert_not_called()

    def test_external_network_and_credential_reads_are_blocked_for_gui_provider(self):
        env_type = type(os.environ)
        original = env_type.__getitem__
        def guarded(environment, key):
            if key.startswith("OPENAI_") or key in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
                raise AssertionError("credential/proxy read forbidden")
            return original(environment, key)
        with ExitStack() as guards:
            for target in ("socket.socket.connect", "socket.socket.connect_ex",
                           "socket.create_connection", "socket.getaddrinfo"):
                guards.enter_context(patch(target, side_effect=AssertionError("network forbidden")))
            guards.enter_context(patch.object(env_type, "__getitem__", guarded))
            state = self.workflow.create(deepcopy(BRIEF), "openai_mock")
            self.assertEqual(state["draft"]["source"], "openai_mock")
            self.assertIsNone(state["draft"]["approval"])

    def test_live_endpoints_keys_and_forged_modes_are_rejected_before_sdk(self):
        with patch("src.gui_workflow.create_mock_draft", side_effect=AssertionError("unexpected SDK")) as mocked:
            payloads = [{"brief": BRIEF, "mode": mode} for mode in
                        ("openai_live", "codex", "live", "https://api.openai.com/v1", None, [])]
            payloads += [dict(brief=BRIEF, mode="openai_mock", **{key: value}) for key, value in
                         (("api_key", "synthetic-do-not-use"), ("endpoint", "https://example.invalid"),
                          ("live", True), ("response_body", None))]
            payloads += [{"mode": "openai_mock", "brief": dict(BRIEF, api_key="synthetic-do-not-use")}]
            for payload in payloads:
                with self.subTest(payload=payload):
                    self.assertEqual(self.request("POST", "/api/jobs", payload)[0], 400)
            self.assertEqual(list(self.base.iterdir()), [])
            mocked.assert_not_called()

    def test_mock_errors_preserve_jobs_and_recover_only_on_explicit_request(self):
        old = self.create("local_template")
        before = self.snapshot()
        with patch("src.gui_workflow.create_mock_draft", side_effect=ValueError("synthetic failure")) as mocked:
            code, raw = self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": "openai_mock"})
            self.assertEqual(code, 400)
            error = json.loads(raw)["error"]
            self.assertIn("API 모의 응답", error)
            self.assertIn("기존 작업", error)
            self.assertNotIn("synthetic failure", error)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.workflow.view(old["id"])["status"], "draft")
            mocked.assert_called_once()
        new = self.create()
        self.assertNotEqual(old["id"], new["id"])
        for name, digest in before.items():
            self.assertEqual(sha256((self.base/name).read_bytes()).hexdigest(), digest)

    def test_malformed_mock_result_cannot_change_application_owned_fields(self):
        values = [None]
        for key, value in (("status", "approved"), ("approval", {"forged": True}),
                           ("cost_estimate", 0), ("source", "codex_live"),
                           ("brief", dict(BRIEF, topic="different"))):
            draft = create_draft(deepcopy(BRIEF))
            draft["source"] = "openai_mock"
            draft[key] = value
            values.append(draft)
        for value in values:
            with self.subTest(value=value), patch("src.gui_workflow.create_mock_draft", return_value=value):
                code, _ = self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": "openai_mock"})
                self.assertEqual(code, 400)
                self.assertEqual(list(self.base.iterdir()), [])

    def test_gui_mock_requests_serialize_across_workflows_without_blocking_reads(self):
        started, release, second_entered = Event(), Event(), Event()
        calls = []
        def slow(brief):
            calls.append(1)
            if len(calls) == 1:
                started.set()
                if not release.wait(5):
                    raise ValueError("synthetic timeout")
            else:
                second_entered.set()
            return create_mock_draft(brief)
        other = Workflow(self.base / "second-instance")
        with patch("src.gui_workflow.create_mock_draft", side_effect=slow):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(self.workflow.create, deepcopy(BRIEF), "openai_mock")
                self.assertTrue(started.wait(3))
                second = pool.submit(other.create, deepcopy(BRIEF), "openai_mock")
                try:
                    self.assertFalse(second_entered.wait(0.1))
                    self.assertEqual(self.request("GET", "/api/bootstrap")[0], 200)
                    self.assertEqual(self.workflow.list_jobs(), [])
                finally:
                    release.set()
                self.assertEqual(first.result(10)["draft"]["source"], "openai_mock")
                self.assertEqual(second.result(10)["draft"]["source"], "openai_mock")
        self.assertTrue(second_entered.is_set())


if __name__ == "__main__":
    unittest.main()
