"""Offline first milestone for a short-video content plan.

This module does not call a model or a paid production service. Its draft is
deliberately a template so that input, JSON handoff, and approval can be tested.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re


SCHEMA_VERSION = 1
REQUIRED_BRIEF = ("topic", "target_seconds", "aspect_ratio", "style", "audience",
                  "forbidden", "max_budget")
REQUIRED_SCENE = ("number", "duration_seconds", "script", "background", "action", "camera")
CREATIVE_FIELDS = frozenset(("hook", "story", "scenes"))


def _validate_revision(revision):
    fields = {"schema_version", "number", "parent_content_sha256", "feedback", "changed_fields"}
    if not isinstance(revision, dict) or set(revision) != fields:
        raise ValueError("invalid revision fields")
    if type(revision["schema_version"]) is not int or revision["schema_version"] != 1:
        raise ValueError("unsupported revision schema")
    if type(revision["number"]) is not int or revision["number"] < 1:
        raise ValueError("revision number must be a positive integer")
    digest = revision["parent_content_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid revision parent digest")
    _nonempty_string(revision["feedback"], "revision feedback")
    changed = revision["changed_fields"]
    if (not isinstance(changed, list) or not changed or
            any(not isinstance(field, str) or field not in CREATIVE_FIELDS for field in changed) or
            changed != sorted(set(changed))):
        raise ValueError("invalid revision changed_fields")


def _nonempty_string(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def validate_brief(brief):
    """Return a normalized project brief or raise ValueError."""
    if not isinstance(brief, dict):
        raise ValueError("brief must be an object")
    missing = set(REQUIRED_BRIEF) - set(brief)
    if missing:
        raise ValueError(f"missing brief fields: {', '.join(sorted(missing))}")
    normalized = {name: _nonempty_string(brief[name], name)
                  for name in ("topic", "aspect_ratio", "style", "audience")}
    seconds = brief["target_seconds"]
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or
            not math.isfinite(seconds) or not 5 <= seconds <= 180):
        raise ValueError("target_seconds must be a number from 5 to 180")
    normalized["target_seconds"] = seconds
    ratio = normalized["aspect_ratio"]
    if not re.fullmatch(r"[1-9]\d*:[1-9]\d*", ratio):
        raise ValueError("aspect_ratio must have a form such as 9:16")
    budget = brief["max_budget"]
    if (isinstance(budget, bool) or not isinstance(budget, (int, float)) or
            not math.isfinite(budget) or budget < 0):
        raise ValueError("max_budget must be a non-negative number")
    normalized["max_budget"] = budget
    forbidden = brief["forbidden"]
    if not isinstance(forbidden, list) or any(not isinstance(item, str) or not item.strip()
                                              for item in forbidden):
        raise ValueError("forbidden must be a list of non-empty strings")
    normalized["forbidden"] = [item.strip() for item in forbidden]
    if any(term.casefold() in normalized["topic"].casefold() for term in normalized["forbidden"]):
        raise ValueError("topic contains a forbidden term")
    return normalized


def create_draft(brief, *, research=None):
    """Create a transparent template draft for the first content-planning milestone."""
    brief = validate_brief(brief)
    topic = brief["topic"]
    duration = brief["target_seconds"]
    lengths = [round(duration * 0.2, 2), round(duration * 0.5, 2)]
    lengths.append(round(duration - sum(lengths), 2))
    scenes = [
        {"number": 1, "duration_seconds": lengths[0],
         "script": f"{topic}, 무엇부터 알아야 할까요?", "background": "주제 소개 화면",
         "action": "핵심 질문을 화면에 제시", "camera": "정면 고정 구도"},
        {"number": 2, "duration_seconds": lengths[1],
         "script": f"{topic}의 핵심 내용을 순서대로 살펴봅니다.", "background": "설명 화면",
         "action": "핵심 내용을 단계별로 표시", "camera": "중간 구도"},
        {"number": 3, "duration_seconds": lengths[2],
         "script": f"{topic}의 요점을 다시 확인해 보세요.", "background": "요약 화면",
         "action": "핵심 요점을 화면에 정리", "camera": "정면 고정 구도"},
    ]
    plan = {"schema_version": SCHEMA_VERSION, "status": "draft", "source": "local_template",
            "brief": brief, "hook": scenes[0]["script"],
            "story": "질문 → 핵심 설명 → 요약", "scenes": scenes,
            "cost_estimate": None, "approval": None}
    if research is not None:
        from src.research_mock import validate_research
        validate_research(research, brief)
        plan["research"] = deepcopy(research)
        reference = research["sources"][0]
        plan["story"] += f" · 모의 참고 [{reference['source_id']}]: {reference['summary']}"
        plan["scenes"][1]["script"] = f"[모의 참고 {reference['source_id']}] {reference['summary']}"
    validate_plan(plan)
    return plan


def validate_plan(plan):
    """Check the JSON handoff contract before approval or further production."""
    if (not isinstance(plan, dict) or type(plan.get("schema_version")) is not int or
            plan["schema_version"] != SCHEMA_VERSION):
        raise ValueError("unsupported plan schema")
    brief = validate_brief(plan.get("brief"))
    if plan.get("status") not in ("draft", "approved"):
        raise ValueError("invalid plan status")
    _nonempty_string(plan.get("source"), "source")
    if "revision" in plan:
        _validate_revision(plan["revision"])
    if "research" in plan:
        from src.research_mock import validate_research
        validate_research(plan["research"], brief)
    for name in ("hook", "story"):
        _nonempty_string(plan.get(name), name)
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list")
    total = 0
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or set(REQUIRED_SCENE) - set(scene):
            raise ValueError(f"scene {index} is missing required fields")
        if type(scene["number"]) is not int or scene["number"] != index:
            raise ValueError("scene numbers must be sequential")
        seconds = scene["duration_seconds"]
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or
                not math.isfinite(seconds) or seconds <= 0):
            raise ValueError(f"scene {index} duration must be positive")
        total += seconds
        for name in ("script", "background", "action", "camera"):
            _nonempty_string(scene[name], f"scene {index} {name}")
    if abs(total - brief["target_seconds"]) > brief["target_seconds"] * 0.1:
        raise ValueError("scene durations exceed the ±10% target tolerance")
    creative_text = " ".join([plan["hook"], plan["story"]] +
                             [str(scene[name]) for scene in scenes
                              for name in ("script", "background", "action", "camera")])
    if any(term.casefold() in creative_text.casefold() for term in brief["forbidden"]):
        raise ValueError("plan contains a forbidden term")
    return plan


def _content_digest(plan):
    content = {name: plan[name] for name in ("schema_version", "source", "brief", "hook", "story", "scenes")}
    # Optional metadata is bound only when present; legacy schema-1 hashes stay unchanged.
    if "revision" in plan:
        content["revision"] = plan["revision"]
    if "research" in plan:
        content["research"] = plan["research"]
    encoded = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def approve_plan(plan):
    """Mark the current validated content as approved; later edits invalidate it."""
    validate_plan(plan)
    if plan["status"] != "draft":
        raise ValueError("only draft plans can be approved")
    approved = dict(plan)
    approved["status"] = "approved"
    approved["approval"] = {"content_sha256": _content_digest(plan),
                            "approved_at": datetime.now(timezone.utc).isoformat()}
    return approved


def is_approved(plan):
    try:
        validate_plan(plan)
        approval = plan.get("approval")
        return (plan["status"] == "approved" and isinstance(approval, dict) and
                approval.get("content_sha256") == _content_digest(plan))
    except (KeyError, TypeError, ValueError):
        return False


def revise_plan(plan, request):
    """Apply explicit local creative replacements, never interpreting feedback with AI.

    Drafts and valid approved plans can be revised. The original is unchanged;
    every result is a fresh draft requiring an explicit new approval.
    """
    validate_plan(plan)
    if plan["status"] == "approved" and not is_approved(plan):
        raise ValueError("cannot revise an invalid approved plan")
    if plan["status"] == "draft" and plan.get("approval") is not None:
        raise ValueError("draft plan must not carry an approval")
    if not isinstance(request, dict) or set(request) != {"schema_version", "feedback", "changes"}:
        raise ValueError("revision request must contain schema_version, feedback, changes only")
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise ValueError("unsupported revision request schema")
    feedback = _nonempty_string(request["feedback"], "feedback")
    changes = request["changes"]
    if not isinstance(changes, dict) or not changes or not set(changes) <= CREATIVE_FIELDS:
        raise ValueError("changes must contain only hook, story, scenes")
    if "scenes" in changes:
        scenes = changes["scenes"]
        if (not isinstance(scenes, list) or any(not isinstance(scene, dict) or
                set(scene) != set(REQUIRED_SCENE) for scene in scenes)):
            raise ValueError("replacement scene fields do not match the contract")
    changed_fields = sorted(field for field, value in changes.items() if value != plan[field])
    if not changed_fields:
        raise ValueError("revision must change creative content")
    revised = deepcopy(plan)
    for field in changed_fields:
        revised[field] = deepcopy(changes[field])
    revised["status"], revised["approval"] = "draft", None
    revised["revision"] = {"schema_version": 1,
                           "number": plan.get("revision", {}).get("number", 0) + 1,
                           "parent_content_sha256": _content_digest(plan),
                           "feedback": feedback, "changed_fields": changed_fields}
    validate_plan(revised)
    return revised
