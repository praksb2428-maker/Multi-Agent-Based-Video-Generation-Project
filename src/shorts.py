"""Offline first milestone for a short-video content plan.

This module does not call a model or a paid production service. Its draft is
deliberately a template so that input, JSON handoff, and approval can be tested.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re


SCHEMA_VERSION = 1
REQUIRED_BRIEF = ("topic", "target_seconds", "aspect_ratio", "style", "audience",
                  "forbidden", "max_budget")
REQUIRED_SCENE = ("number", "duration_seconds", "script", "background", "action", "camera")


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


def create_draft(brief):
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
