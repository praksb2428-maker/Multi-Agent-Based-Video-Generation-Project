"""Provider-neutral local rule templates; no model, service, or media execution."""

from copy import deepcopy
from hashlib import sha256
import json

from src.shorts import REQUIRED_SCENE, is_approved


SOURCE = "local_rule_template"


def _canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("artifact must contain finite JSON values") from error


def _require_approved(plan):
    if not is_approved(plan):
        raise ValueError("a valid approved plan is required")


def _check_positive_text(text, forbidden):
    if any(term.casefold() in text.casefold() for term in forbidden):
        raise ValueError("positive direction or prompt contains a forbidden term")


def create_direction(plan):
    """Derive reproducible local directions only from an unchanged approved plan."""
    _require_approved(plan)
    scenes = []
    for original in plan["scenes"]:
        scene = {field: deepcopy(original[field]) for field in REQUIRED_SCENE}
        scene["lighting"] = {"value": "균일한 기본 조명", "origin": "local_default"}
        scene["audio"] = {"narration": original["script"], "background_music": None,
                          "origin": "local_default"}
        positive = " ".join([str(scene[field]) for field in
                              ("script", "background", "action", "camera")] +
                             [scene["lighting"]["value"]])
        _check_positive_text(positive, plan["brief"]["forbidden"])
        scenes.append(scene)
    return {"schema_version": 1, "kind": "direction", "source": SOURCE,
            "plan_source": plan["source"],
            "plan_sha256": plan["approval"]["content_sha256"],
            "conditions": deepcopy(plan["brief"]),
            "context": {"hook": plan["hook"], "story": plan["story"]}, "scenes": scenes}


def validate_direction(direction, plan):
    """Reject stale, modified, or unsupported local-template artifacts.

    These are fixed rule derivations, not manually editable direction proposals.
    Regenerate from the newly approved plan after a change.
    """
    expected = create_direction(plan)
    if (not isinstance(direction, dict) or type(direction.get("schema_version")) is not int or
            direction["schema_version"] != 1):
        raise ValueError("unsupported direction schema")
    # Canonical bytes distinguish booleans from integers and reject NaN/Infinity.
    if _canonical(direction) != _canonical(expected):
        raise ValueError("direction does not match the approved plan and local rules")
    return direction


def create_prompts(plan, direction):
    """Render generic scene instructions, never provider requests or approval."""
    validate_direction(direction, plan)
    brief = plan["brief"]
    scenes = []
    for scene in direction["scenes"]:
        prompt = "\n".join((
            f"주제: {brief['topic']}",
            f"대상 시청자: {brief['audience']}",
            f"스타일: {brief['style']}",
            f"전체 도입 훅: {plan['hook']}",
            f"전체 이야기 흐름: {plan['story']}",
            f"화면 비율: {brief['aspect_ratio']}",
            f"장면 번호: {scene['number']}",
            f"장면 길이(초): {scene['duration_seconds']}",
            f"배경: {scene['background']}",
            f"인물 행동: {scene['action']}",
            f"카메라: {scene['camera']}",
            f"조명(로컬 기본값): {scene['lighting']['value']}",
            f"대본: {scene['script']}",
            "오디오(로컬 기본값): 대본을 내레이션으로 사용; 배경음악 미정",
        ))
        _check_positive_text(prompt, brief["forbidden"])
        scenes.append({"number": scene["number"],
                       "duration_seconds": scene["duration_seconds"], "prompt": prompt})
    return {"schema_version": 1, "kind": "prompts", "source": SOURCE,
            "plan_source": plan["source"],
            "plan_sha256": plan["approval"]["content_sha256"],
            "direction_sha256": sha256(_canonical(direction)).hexdigest(),
            "status": "draft", "provider": None, "model": None,
            "cost_estimate": None, "production_approval": None,
            "context": deepcopy(direction["context"]),
            "must_avoid": deepcopy(brief["forbidden"]), "scenes": scenes}
