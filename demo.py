"""Show the local content-planning handoff without writing files."""

import json
from pathlib import Path

from src.shorts import approve_plan, create_draft, is_approved


brief = json.loads(Path("examples/shorts_brief.json").read_text(encoding="utf-8"))
draft = create_draft(brief)
approved = approve_plan(draft)
print("초안 훅:", draft["hook"])
print("장면 수:", len(draft["scenes"]))
print("기획 승인 유효:", is_approved(approved))
