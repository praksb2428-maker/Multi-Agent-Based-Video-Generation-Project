"""GUI integration checks with a fake provider; never invoke a real model."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch

from shorts_web import LocalServer
from src.gui_workflow import Workflow
from src.local_ollama import MODEL, MODEL_DIGEST
from src.mock_media import WORKSPACE
from src.shorts import create_draft
from test_shorts import BRIEF
import test_web


def fixture(brief):
    draft = create_draft(brief)
    draft["hook"] = "별빛 도서관에서 잃어버린 책을 찾아요."
    draft["source"] = f"ollama_local:{MODEL}@{MODEL_DIGEST}"
    return draft


class GuiLocalModelTests(unittest.TestCase):
    request = test_web.WebTests.request

    def setUp(self):
        WORKSPACE.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="gui-local-tests-", dir=WORKSPACE)
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

    def create(self, mode="local_ollama"):
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

    def test_local_generation_is_explicit_and_two_approvals_remain_separate(self):
        with patch("src.gui_workflow.create_local_draft", side_effect=fixture) as provider, \
                patch("src.gui_workflow.produce_mock_media", side_effect=AssertionError("unexpected render")) as render:
            state = self.create()
            provider.assert_called_once_with(BRIEF)
            self.assertEqual(state["status"], "draft")
            self.assertIsNone(state["draft"]["approval"])
            self.assertIsNone(state["draft"]["cost_estimate"])
            self.assertEqual(state["draft"]["brief"], BRIEF)
            self.assertEqual(state["draft"]["source"], f"ollama_local:{MODEL}@{MODEL_DIGEST}")
            creation = json.loads((self.base / state["id"] / "creation.json").read_text())
            self.assertEqual(creation["mode"], "local_ollama")
            self.assertIs(creation["real_execution_allowed"], False)
            self.action(state, "produce", expected=400)
            self.action(state, "prepare", expected=400)
            state = self.action(state, "approve_plan")
            self.assertEqual(state["status"], "plan_approved")
            state = self.action(state, "prepare")
            self.assertEqual(state["status"], "prepared")
            self.assertNotIn("produce", state["actions"])
            self.action(state, "produce", expected=400)
            state = self.action(state, "approve_production", {
                "approved_by": "synthetic GUI test", "reason": "explicit separate fixture approval"})
            self.assertEqual(state["status"], "production_approved")
            self.assertIs(state["real_execution_allowed"], False)
            self.assertEqual(Workflow(self.base).view(state["id"])["status"], "production_approved")
            self.assertEqual(self.request("GET", "/api/bootstrap")[0], 200)
            self.assertEqual(self.request("GET", f"/api/jobs/{state['id']}")[0], 200)
            provider.assert_called_once()
            render.assert_not_called()

    def test_revision_preserves_original_and_requires_reapproval_without_inference(self):
        with patch("src.gui_workflow.create_local_draft", side_effect=fixture) as provider:
            state = self.create()
            original = self.base / state["id"] / "r0001" / "draft.json"
            digest = sha256(original.read_bytes()).hexdigest()
            revised = self.action(state, "revise_draft", {"schema_version": 1,
                "feedback": "synthetic explicit edit", "changes": {"hook": "새로운 도입 문구"}})
            self.assertEqual((revised["revision"], revised["status"]), (2, "draft"))
            self.assertIsNone(revised["draft"]["approval"])
            self.assertEqual(sha256(original.read_bytes()).hexdigest(), digest)
            self.assertNotIn("prepare", revised["actions"])
            self.assertEqual(Workflow(self.base).view(state["id"])["revision"], 2)
            provider.assert_called_once()

    def test_provider_errors_are_korean_and_preserve_existing_jobs_then_recover(self):
        old = self.create("local_template")
        before = self.snapshot()
        errors = ["local server unavailable or timed out", "local runtime version does not match the approved version",
                  "approved local model is not installed with the expected digest", "invalid local response JSON",
                  "local generation is incomplete or uses an unexpected model", "local response exceeds byte limit"]
        for message in errors:
            with self.subTest(message=message), patch("src.gui_workflow.create_local_draft", side_effect=ValueError(message)) as provider:
                code, raw = self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": "local_ollama"})
                self.assertEqual(code, 400)
                text = json.loads(raw)["error"]
                self.assertIn("기존 작업", text)
                self.assertNotIn(message, text)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.workflow.view(old["id"])["status"], "draft")
                provider.assert_called_once()
        with patch("src.gui_workflow.create_local_draft", side_effect=fixture):
            new = self.create()
        self.assertNotEqual(old["id"], new["id"])
        for path, digest in before.items():
            self.assertEqual(sha256((self.base/path).read_bytes()).hexdigest(), digest)

    def test_provider_cannot_change_app_owned_fields_or_return_invalid_plan(self):
        cases = [None]
        for key, value in [("status", "approved"), ("approval", {"forged": True}),
                           ("cost_estimate", 1), ("source", "untrusted")]:
            value_plan = fixture(BRIEF)
            value_plan[key] = value
            cases.append(value_plan)
        changed = fixture(BRIEF)
        changed["brief"]["topic"] = "different user input"
        cases.append(changed)
        for value in cases:
            with self.subTest(value=value), patch("src.gui_workflow.create_local_draft", return_value=value):
                code, raw = self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": "local_ollama"})
                self.assertEqual(code, 400, raw)
                self.assertEqual(list(self.base.iterdir()), [])

    def test_modes_gets_injected_fields_and_restarts_never_trigger_real_inference(self):
        with patch("src.gui_workflow.create_local_draft", side_effect=AssertionError("unexpected inference")) as provider:
            self.create("local_template")
            state = self.create("local_model_mock")
            self.assertEqual(self.request("GET", "/api/bootstrap")[0], 200)
            self.assertEqual(self.request("GET", "/")[0], 200)
            self.assertEqual(self.request("GET", f"/api/jobs/{state['id']}")[0], 200)
            self.assertEqual(Workflow(self.base).view(state["id"])["status"], "draft")
            payloads = [{"mode": mode, "brief": BRIEF} for mode in ("live", "http://evil.invalid", [], None)]
            payloads += [{"mode": "local_ollama", "brief": BRIEF, "endpoint": "http://evil.invalid"},
                         {"mode": "local_ollama", "brief": dict(BRIEF, model="cloud")},
                         {"mode": "local_ollama", "brief": dict(BRIEF, approval=True)}]
            for payload in payloads:
                self.assertEqual(self.request("POST", "/api/jobs", payload)[0], 400)
            provider.assert_not_called()

    def test_slow_generation_keeps_bootstrap_readable_and_no_partial_job(self):
        started, release = Event(), Event()
        output = []
        def slow(brief):
            started.set()
            if not release.wait(5):
                raise ValueError("synthetic timeout")
            return fixture(brief)
        def call():
            output.append(self.request("POST", "/api/jobs", {"brief": BRIEF, "mode": "local_ollama"}))
        with patch("src.gui_workflow.create_local_draft", side_effect=slow) as provider:
            thread = Thread(target=call)
            thread.start()
            try:
                self.assertTrue(started.wait(3))
                code, raw = self.request("GET", "/api/bootstrap")
                self.assertEqual(code, 200)
                self.assertEqual(json.loads(raw)["jobs"], [])
                self.assertEqual(list(self.base.iterdir()), [])
            finally:
                release.set()
                thread.join(10)
            self.assertFalse(thread.is_alive())
            self.assertEqual(output[0][0], 200)
            provider.assert_called_once()


if __name__ == "__main__":
    unittest.main()
