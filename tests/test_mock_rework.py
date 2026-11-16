import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.mock_media import WORKSPACE, _json_write, produce_mock_media
from src.mock_production import approve_mock_production, _digest
from src.mock_rework import rework_plan_mock, prepare_rework_mock, produce_rework_mock
from src.quality_feedback import inspect_mock_result, review_mock_result
from src.shorts import approve_plan
from test_mock_media import values
from test_quality_feedback import CHANGES, ACCEPT

ROOT = Path(__file__).resolve().parents[1]


class MockReworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="rework-tests-", dir=WORKSPACE)
        cls.base = Path(cls.temp.name)
        cls.values = values()
        cls.result = cls.base / "old"
        produce_mock_media(*cls.values, cls.result)
        cls.inspection = inspect_mock_result(*cls.values, cls.result)
        cls.review = review_mock_result(*cls.values, cls.result, cls.inspection, CHANGES)
        scenes = copy.deepcopy(cls.values[0]["scenes"])
        scenes[0]["script"] = "Explicit synthetic revised opening"
        cls.revision = {"schema_version": 1, "feedback": "Explicit test candidate, not inferred resolution",
                        "changes": {"hook": "A changed test opening", "scenes": scenes}}
        cls.common = (cls.values, cls.result, cls.inspection, cls.review, cls.revision)
        cls.rework = cls.base / "draft"
        rework_plan_mock(*cls.common, cls.rework)
        cls.draft = json.loads((cls.rework / "draft.json").read_text(encoding="utf-8"))
        cls.approved = approve_plan(cls.draft)
        cls.prepared = cls.base / "prepared"
        prepare_rework_mock(*cls.common, cls.rework, cls.approved, cls.prepared)
        cls.new_values = tuple(json.loads((cls.prepared / name).read_text(encoding="utf-8")) for name in
                               ("plan.json", "direction.json", "prompts.json", "pricing.json", "quote.json"))
        cls.approval = approve_mock_production(*cls.new_values, approved_by="synthetic tester", reason="explicit new approval")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_F1_waiting_states_separate_approvals_and_original_preservation(self):
        self.assertEqual(self.draft["status"], "draft")
        self.assertIsNone(self.draft["approval"])
        handoff = json.loads((self.rework / "handoff.json").read_text())
        ready = json.loads((self.prepared / "handoff.json").read_text())
        self.assertEqual(handoff["status"], "awaiting_plan_approval")
        self.assertEqual(ready["status"], "awaiting_mock_production_approval")
        self.assertFalse((self.prepared / "approval.json").exists())
        before = {p.name: p.read_bytes() for p in self.result.iterdir() if p.is_file()}
        with patch("src.mock_rework.produce_mock_media", side_effect=AssertionError("no rendering")):
            with self.assertRaises(ValueError):
                prepare_rework_mock(*self.common, self.rework, self.draft, self.base / "unapproved")
        self.assertFalse((self.base / "unapproved").exists())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.result.iterdir() if p.is_file()})

    def test_F2_wrong_missing_old_expired_or_real_approval_stops_before_tools(self):
        expired = approve_mock_production(*self.new_values, approved_by="test", reason="expired",
                                          now=datetime.now(timezone.utc) - timedelta(hours=2))
        real = {**self.approval, "real_execution_allowed": True}
        for index, approval in enumerate((None, self.values[-1], expired, real)):
            out = self.base / f"denied-{index}"
            with patch("src.mock_media._tools", side_effect=AssertionError("no tools")), \
                    patch("src.mock_rework.produce_mock_media", side_effect=AssertionError("no rendering")):
                with self.subTest(index=index), self.assertRaises(ValueError):
                    produce_rework_mock(*self.common, self.rework, self.approved, self.prepared, approval, out)
            self.assertFalse(out.exists())

    def test_F3_current_source_review_patch_and_exact_new_plan_required(self):
        for index, field in enumerate(("review", "inspection", "revision", "inputs", "approved")):
            current = list(copy.deepcopy(self.common))
            approved = copy.deepcopy(self.approved)
            if field == "review": current[3]["request"]["notes"] += "changed"
            elif field == "inspection": current[2]["status"] = "blocked"
            elif field == "revision": current[4]["changes"]["hook"] += "changed"
            elif field == "inputs": current[0][3]["assembly_fixed"] += 1
            else:
                alternate = copy.deepcopy(self.draft)
                alternate["hook"] += "different"
                approved = approve_plan(alternate)
            out = self.base / f"stale-{index}"
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare_rework_mock(*current, self.rework, approved, out)
            self.assertFalse(out.exists())

    def test_F4_accept_and_unknown_manual_triage_cannot_start_rework(self):
        accepted = review_mock_result(*self.values, self.result, self.inspection, ACCEPT)
        with self.assertRaises(ValueError):
            rework_plan_mock(self.values, self.result, self.inspection, accepted, self.revision, self.base / "accepted")
        with patch("src.quality_feedback.validate_mock_result", side_effect=RuntimeError("unknown")):
            unknown = inspect_mock_result(*self.values, self.result)
            review = review_mock_result(*self.values, self.result, unknown, CHANGES)
            with self.assertRaisesRegex(ValueError, "manual triage"):
                rework_plan_mock(self.values, self.result, unknown, review, self.revision, self.base / "unknown")

    def test_F5_handoff_tamper_versions_fixed_files_and_overwrites(self):
        import shutil
        for index, (file, edit) in enumerate((("handoff.json", "version"), ("handoff.json", "flag"),
                ("handoff.json", "binding"), ("draft.json", "draft"), ("revision.json", "revision"))):
            folder = self.base / f"tamper-{index}"
            shutil.copytree(self.rework, folder)
            path = folder / file
            obj = json.loads(path.read_text(encoding="utf-8"))
            if edit == "version": obj["schema_version"] = 2
            elif edit == "flag": obj["real_execution_allowed"] = True
            elif edit == "binding": obj["binding"]["draft"] = "different"
            elif edit == "draft": obj["hook"] += "changed"
            else: obj["feedback"] += "changed"
            if file == "handoff.json":
                obj["content_sha256"] = _digest({k: v for k, v in obj.items() if k != "content_sha256"})
            path.write_text(json.dumps(obj), encoding="utf-8")
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                prepare_rework_mock(*self.common, folder, self.approved, self.base / f"tampered-{index}")
        with self.assertRaisesRegex(ValueError, "already exists"):
            rework_plan_mock(*self.common, self.rework)
        for out in (ROOT / "outside-workspace", WORKSPACE / "x" / ".." / "escape"):
            with self.assertRaises(ValueError):
                rework_plan_mock(*self.common, out)

    def test_F6_prepared_changes_cannot_render(self):
        import shutil
        for index, name in enumerate(("prompts.json", "quote.json", "pricing.json", "handoff.json")):
            folder = self.base / f"prepared-tamper-{index}"
            shutil.copytree(self.prepared, folder)
            path = folder / name
            data = json.loads(path.read_text(encoding="utf-8"))
            data["injected"] = True
            path.write_text(json.dumps(data), encoding="utf-8")
            out = self.base / f"not-produced-{index}"
            with patch("src.mock_rework.produce_mock_media", side_effect=AssertionError("no rendering")):
                with self.assertRaises(ValueError):
                    produce_rework_mock(*self.common, self.rework, self.approved, folder, self.approval, out)
            self.assertFalse(out.exists())

    def test_F7_real_local_roundtrip_under_effective_network_and_environment_guards(self):
        safe = {k: os.environ.get(k, "") for k in ("PATH", "PATHEXT", "SystemRoot", "WINDIR")}
        class Guard(dict):
            def get(self, key, default=None):
                if key.startswith("OPENAI_") or "PROXY" in key.upper():
                    raise AssertionError("credential access")
                return super().get(key, default)
            def __getitem__(self, key):
                if key.startswith("OPENAI_") or "PROXY" in key.upper():
                    raise AssertionError("credential access")
                return super().__getitem__(key)
        original = {p.name: p.read_bytes() for p in self.result.iterdir() if p.is_file()}
        output = self.base / "new-render"
        with patch("socket.socket.connect", side_effect=AssertionError("network")), \
                patch("socket.getaddrinfo", side_effect=AssertionError("DNS")), patch("os.environ", Guard(safe)):
            for key in ("OPENAI_API_KEY", "HTTPS_PROXY"):
                with self.assertRaises(AssertionError): os.environ.get(key)
            with self.assertRaises(AssertionError): socket.getaddrinfo("sentinel.invalid", 443)
            with self.assertRaises(AssertionError): socket.socket.connect(None, ("127.0.0.1", 1))
            # Fresh bundles demonstrate all local stages under the guards too.
            draftdir, prepdir = self.base / "guard-draft", self.base / "guard-prep"
            rework_plan_mock(*self.common, draftdir)
            prepare_rework_mock(*self.common, draftdir, self.approved, prepdir)
            receipt = produce_rework_mock(*self.common, draftdir, self.approved, prepdir, self.approval, output)
        self.assertEqual(receipt["status"], "technical_complete_mock_human_review_pending")
        self.assertEqual(receipt["binding"]["issues_resolution"], "not_inferred")
        self.assertIn("Explicit synthetic revised opening", (output / "subtitles.srt").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((output / "quality.json").read_text())["observed"]["frames"], 120)
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.result.iterdir() if p.is_file()})
        with self.assertRaises(ValueError):
            produce_rework_mock(*self.common, draftdir, self.approved, prepdir, self.approval, output)

    def test_F8_cli_strict_json_and_disk_resume_approval_boundaries(self):
        folder = self.base / "cli"
        folder.mkdir()
        inputs = []
        for index, value in enumerate(self.values):
            file = folder / f"input-{index}.json"
            _json_write(file, value)
            inputs.append(str(file))
        inspection, review, revision = (folder / name for name in ("inspection.json", "review.json", "revision.json"))
        for file, value in zip((inspection, review, revision), (self.inspection, self.review, self.revision)):
            _json_write(file, value)
        args = [*inputs, str(self.result), str(inspection), str(review), str(revision)]
        def run(command, *more):
            return subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", command, *args, *map(str, more)],
                                  cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
        draftdir, approved, prepdir = folder / "draft", folder / "approved.json", folder / "prep"
        self.assertEqual(run("rework-plan-mock", draftdir).returncode, 0)
        denied = run("prepare-rework-mock", draftdir, draftdir / "draft.json", prepdir)
        self.assertEqual(denied.returncode, 2, denied.stderr)
        separate = subprocess.run([sys.executable, "-X", "utf8", "shorts_cli.py", "approve",
                                   str(draftdir / "draft.json"), str(approved)], cwd=ROOT,
                                  capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(separate.returncode, 0, separate.stderr)
        ready = run("prepare-rework-mock", draftdir, approved, prepdir)
        self.assertEqual(ready.returncode, 0, ready.stderr)
        for index, text in enumerate(("null", '{"schema_version":NaN}', '{"schema_version":1,"schema_version":1}',
                                      '{"schema_version":9}', '{"schema_version":1,"real_execution_allowed":true}')):
            revision.write_text(text, encoding="utf-8")
            out = folder / f"invalid-{index}"
            self.assertEqual(run("rework-plan-mock", out).returncode, 2)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
