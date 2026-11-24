"""Exercise the Git-backed design-document freshness gate in a temporary repo."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_architecture_sync.py"


class ArchitectureSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Architecture Test")
        (self.repo / "src").mkdir()
        (self.repo / "docs").mkdir()
        (self.repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.repo / "docs" / "architecture.md").write_text("# Initial design\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-qm", "baseline")

    def _git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True, capture_output=True, text=True,
        )

    def _check(self):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo)],
            capture_output=True, text=True,
        )

    def test_implementation_requires_design_change(self):
        (self.repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        failure = self._check()
        self.assertEqual(failure.returncode, 1)
        self.assertIn("src/app.py", failure.stderr)

        (self.repo / "docs" / "architecture.md").write_text("# Revised design\n", encoding="utf-8")
        success = self._check()
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("docs/architecture.md", success.stdout)

    def test_untracked_skill_is_an_implementation_change(self):
        skill = self.repo / ".agents" / "skills" / "new-skill" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: new-skill\n---\n", encoding="utf-8")
        result = self._check()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".agents/skills/new-skill/SKILL.md", result.stderr)

    def test_deleted_design_document_does_not_satisfy_guard(self):
        (self.repo / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")
        (self.repo / "docs" / "architecture.md").unlink()
        result = self._check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("src/app.py", result.stderr)

    def test_new_implementation_shapes_require_design_change(self):
        for relative in ("new_feature.py", "web/new_asset.png", "src/new_config.json"):
            with self.subTest(relative=relative):
                path = self.repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic content\n", encoding="utf-8")
                result = self._check()
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn(relative, result.stderr)
                path.unlink()

    def test_test_or_document_only_change_needs_no_design_update(self):
        tests = self.repo / "tests"
        tests.mkdir()
        (tests / "test_app.py").write_text("# test only\n", encoding="utf-8")
        (self.repo / "docs" / "testing.md").write_text("# Tests\n", encoding="utf-8")
        result = self._check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no implementation changes", result.stdout)


if __name__ == "__main__":
    unittest.main()
