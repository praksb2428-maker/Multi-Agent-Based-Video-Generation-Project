import copy
from hashlib import sha256
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from shorts_web import LocalServer, MAX_BODY
from src.gui_workflow import Workflow, strict_json
from src.mock_media import WORKSPACE
from test_shorts import BRIEF


class WebTests(unittest.TestCase):
    def setUp(self):
        WORKSPACE.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="gui-tests-", dir=WORKSPACE)
        self.base = Path(self.temp.name)
        self.workflow = Workflow(self.base)
        self.server = LocalServer(0, self.workflow)
        self.thread = Thread(target=self.server.serve_forever)
        self.thread.start()
        self.port = self.server.server_port
        self.state = None

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive())
        self.temp.cleanup()

    def request(self, method, path, payload=None, **changes):
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", "X-CSRF-Token": self.server.csrf}
        headers.update(changes)
        connection = HTTPConnection("127.0.0.1", self.port, timeout=45)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def create(self, **brief):
        code, body = self.request("POST", "/api/jobs", {"brief": dict(BRIEF, target_seconds=5, **brief), "mode": "local_model_mock"})
        self.assertEqual(code, 200, body)
        self.state = json.loads(body)
        return self.state

    def action(self, name, payload=None):
        code, body = self.request("POST", f"/api/jobs/{self.state['id']}/action", {
            "action": name, "payload": {} if payload is None else payload, "sequence": self.state["sequence"]})
        self.assertEqual(code, 200, body)
        self.state = json.loads(body)
        return self.state

    def test_http_complete_manual_gates_reload_rework_and_preserved_originals(self):
        self.create()
        self.assertEqual(self.state["status"], "draft")
        with patch("src.gui_workflow.produce_mock_media", side_effect=AssertionError("render before approval")):
            self.action("approve_plan")
            self.assertEqual(self.state["status"], "plan_approved")
            self.action("prepare")
            self.assertEqual(self.state["status"], "prepared")
            self.assertIs(self.state["quote"]["real_execution_allowed"], False)
            self.action("approve_production", {"approved_by": "synthetic test", "reason": "separate explicit test action"})
        self.assertEqual(self.state["status"], "production_approved")
        self.action("produce")
        self.assertEqual(self.state["inspection"]["status"], "technical_pass")
        job = self.state["id"]
        old = self.base / job / "r0001"
        original = {p.relative_to(old).as_posix(): sha256(p.read_bytes()).hexdigest()
                    for p in old.rglob("*") if p.is_file()}
        self.assertEqual(Workflow(self.base).view(job)["status"], "result_pending")
        code, body = self.request("GET", f"/files/{job}/1/subtitles.srt")
        self.assertEqual(code, 200)
        self.assertIn(b"00:00:05,000", body)
        self.action("review", {"schema_version": 1, "reviewer": "synthetic tester", "decision": "request_changes",
                              "notes": "Change the opening explicitly", "issues": [{"category": "content", "scene_number": 1,
                              "note": "Change the opening explicitly"}]})
        # Review was added after original snapshot; earlier output bytes remain identical.
        revision = {"schema_version": 1, "feedback": "Explicit test patch", "changes": {"hook": "New explicit opening"}}
        self.action("revise_result", revision)
        self.assertEqual((self.state["revision"], self.state["status"]), (2, "draft"))
        self.assertIsNone(self.state["draft"]["approval"])
        self.action("approve_plan")
        self.action("prepare")
        self.action("approve_production", {"approved_by": "synthetic tester", "reason": "new quote confirmed separately"})
        self.action("produce")
        self.assertEqual(self.state["status"], "result_pending")
        receipt = json.loads((self.base / job / "r0002" / "result" / "rework.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "technical_complete_mock_human_review_pending")
        for name, digest in original.items():
            self.assertEqual(sha256((old / name).read_bytes()).hexdigest(), digest)

    def test_out_of_order_stale_duplicate_and_injected_actions_do_not_render(self):
        self.create()
        original = copy.deepcopy(self.state)
        with patch("src.gui_workflow.produce_mock_media", side_effect=AssertionError("gate bypass")) as render:
            for action, payload in (("produce", {}), ("approve_production", {}), ("shell", {}), ("approve_plan", {"real_execution_allowed": True})):
                code, _ = self.request("POST", f"/api/jobs/{self.state['id']}/action", {"action": action, "payload": payload, "sequence": self.state["sequence"]})
                self.assertEqual(code, 400)
            self.assertEqual(self.workflow.view(self.state["id"]), original)
            self.action("approve_plan")
            code, _ = self.request("POST", f"/api/jobs/{self.state['id']}/action", {"action": "prepare", "payload": {}, "sequence": original["sequence"]})
            self.assertEqual(code, 400)
            render.assert_not_called()

    def test_current_files_and_event_chain_tampering_are_rejected_after_restart(self):
        self.create()
        draft = self.base / self.state["id"] / "r0001" / "draft.json"
        draft.write_text(draft.read_text(encoding="utf-8") + " ", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "변경"):
            Workflow(self.base).view(self.state["id"])
        self.assertEqual(self.workflow.list_jobs()[0]["status"], "blocked")

    def test_corrupt_job_shapes_are_isolated_from_bootstrap_good_jobs_and_creation(self):
        good = self.create()["id"]
        changes = [("status", value) for value in ([], {}, None)] + [
            ("schema_version", []), ("sequence", {}), ("revision", None),
            ("source", []), ("error", {}), ("created_at", []), ("files", []),
            ("content_sha256", {}), ("previous_sha256", [])]
        for key, value in changes:
            with self.subTest(field=key, value=value):
                job = self.create()["id"]
                path = self.base / job / "events" / "000001.json"
                item = json.loads(path.read_text(encoding="utf-8"))
                item[key] = value
                # Keep the original seal: corruption must be rejected before
                # unsafe membership/indexing, not hidden by recomputing a hash.
                path.write_text(json.dumps(item), encoding="utf-8")
                with self.assertRaises(ValueError):
                    Workflow(self.base).view(job)
                code, body = self.request("GET", "/api/bootstrap")
                self.assertEqual(code, 200, body)
                rows = {row["id"]: row for row in json.loads(body)["jobs"]}
                self.assertEqual(rows[job]["status"], "blocked")
                self.assertEqual(rows[good]["status"], "draft")
                code, body = self.request("GET", f"/api/jobs/{job}")
                self.assertEqual(code, 400, body)
                self.assertIn("error", json.loads(body))
        for value in ([], {}, None, "not an event"):
            job = self.create()["id"]
            (self.base / job / "events" / "000001.json").write_text(json.dumps(value), encoding="utf-8")
            code, body = self.request("GET", "/api/bootstrap")
            self.assertEqual(code, 200, body)
            self.assertEqual(next(row for row in json.loads(body)["jobs"] if row["id"] == job)["status"], "blocked")
            self.assertEqual(self.request("GET", f"/api/jobs/{job}")[0], 400)
        for value in ([], None, {"topic": []}):
            job = self.create()["id"]
            (self.base / job / "brief.json").write_text(json.dumps(value), encoding="utf-8")
            code, body = self.request("GET", "/api/bootstrap")
            self.assertEqual(code, 200, body)
            self.assertEqual(next(row for row in json.loads(body)["jobs"] if row["id"] == job)["status"], "blocked")
        self.assertEqual(self.request("GET", f"/api/jobs/{good}")[0], 200)
        self.assertEqual(self.create()["status"], "draft")

    def test_http_origin_host_csrf_body_and_paths_are_rejected(self):
        for changed in ({"Origin": "https://example.invalid"}, {"Host": "evil.invalid"}, {"X-CSRF-Token": "wrong"},
                        {"Sec-Fetch-Site": "cross-site"}):
            code, _ = self.request("POST", "/api/jobs", {}, **changed)
            self.assertEqual(code, 403)
        code, _ = self.request("POST", "/api/jobs", {}, **{"Content-Length": str(MAX_BODY + 1)})
        self.assertEqual(code, 400)
        for path in ("/files/../../AGENTS.md", "/%2e%2e/AGENTS.md", "/api/bootstrap?target=anything"):
            code, _ = self.request("GET", path)
            self.assertIn(code, (400, 404))
        self.assertEqual(list(self.base.iterdir()), [])

    def test_json_unknown_fields_and_bad_brief_do_not_create_jobs(self):
        for text in ('{"a":1,"a":2}', 'NaN'):
            with self.assertRaises(ValueError):
                strict_json(text)
        for payload in (None, {}, {"brief": BRIEF, "mode": "live"},
                        {"brief": dict(BRIEF, api_key="not permitted"), "mode": "local_template"}):
            code, _ = self.request("POST", "/api/jobs", payload if payload is not None else [])
            self.assertEqual(code, 400)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_draft_revision_reapproval_and_failed_render_preserves_attempt(self):
        self.create()
        self.action("revise_draft", {"schema_version": 1, "feedback": "explicit edit", "changes": {"hook": "A clearer new hook"}})
        self.assertEqual(self.state["revision"], 2)
        self.action("approve_plan")
        self.action("prepare")
        self.action("approve_production", {"approved_by": "synthetic tester", "reason": "explicit approval"})
        def failed(*values):
            values[-1].mkdir()
            raise ValueError("synthetic controlled failure")
        with patch("src.gui_workflow.produce_mock_media", side_effect=failed):
            code, _ = self.request("POST", f"/api/jobs/{self.state['id']}/action", {"action": "produce", "payload": {}, "sequence": self.state["sequence"]})
            self.assertEqual(code, 400)
        state = Workflow(self.base).view(self.state["id"])
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["actions"], [])
        self.assertTrue((self.base / self.state["id"] / "r0002" / "result").is_dir())

    def test_static_page_is_local_only_and_import_does_not_start_runtime(self):
        code, body = self.request("GET", "/")
        self.assertEqual(code, 200)
        self.assertIn('기획 승인'.encode(), body)
        self.assertNotIn(b"https://", body)
        self.assertNotIn(b"api_key", body)
        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request("GET", "/architecture.svg")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "image/svg+xml; charset=utf-8")
            self.assertIn(b"<svg", response.read())
        finally:
            connection.close()
