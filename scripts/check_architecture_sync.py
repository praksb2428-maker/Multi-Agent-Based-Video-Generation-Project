"""Require a design-document change alongside project implementation changes.

This checks whether a document changed in the same candidate. It cannot prove
the document accurately describes the code; the reviewer must check that.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DESIGN_DOCS = {"AGENTS.md", "docs/architecture.md"}
ROOT_CONFIG = {"pyproject.toml", "setup.cfg", "Pipfile", "Pipfile.lock", "uv.lock", "poetry.lock"}


def _git_paths(repo: Path, *args: str) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=True
    )
    return {
        path.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        for path in result.stdout.split(b"\0")
        if path
    }


def changed_paths(repo: Path, base: str) -> set[str]:
    """Include committed, staged, unstaged, and untracked non-ignored files."""
    return _git_paths(repo, "diff", "--name-only", "-z", base, "--") | _git_paths(
        repo, "ls-files", "--others", "--exclude-standard", "-z"
    )


def is_implementation(path: str) -> bool:
    if "/" not in path and (
        path.endswith(".py")
        or path.startswith("requirements") and path.endswith(".txt")
        or path in ROOT_CONFIG
    ):
        return True
    if path.startswith(("src/", "web/", "scripts/")):
        return True
    return path.startswith((".agents/skills/", "harness/skills/"))


def evaluate(repo: Path, base: str) -> tuple[list[str], list[str]]:
    changes = changed_paths(repo, base)
    implementation = sorted(path for path in changes if is_implementation(path))
    design = sorted(path for path in changes & DESIGN_DOCS if (repo / path).is_file())
    return implementation, design


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD", help="Git commit/ref to compare (default: HEAD)")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository root")
    args = parser.parse_args(argv)
    try:
        implementation, design = evaluate(args.repo.resolve(), args.base)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"architecture-sync: Git comparison failed: {error}", file=sys.stderr)
        return 2
    if not implementation:
        print("architecture-sync: no implementation changes")
        return 0
    if design:
        print(f"architecture-sync: {len(implementation)} implementation file(s); updated {', '.join(design)}")
        return 0
    print("architecture-sync: update AGENTS.md or docs/architecture.md for:", file=sys.stderr)
    for path in implementation:
        print(f"  {path}", file=sys.stderr)
    print("The reviewer must still verify that the design description is accurate.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
