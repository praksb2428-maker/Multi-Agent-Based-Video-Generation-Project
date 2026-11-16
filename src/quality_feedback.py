"""Local inspection and self-reported review records; never execute rework."""

from copy import deepcopy
from datetime import datetime, timezone

from src.direction import _canonical
from src.mock_media import (INPUT_NAMES, PAYLOADS, WORKSPACE, MockResultValidationError,
                            _file, _file_record, _input_digests, _result_dir,
                            validate_mock_result)
from src.mock_production import _digest, _timestamp


SOURCE = "local_mock_review"
SCOPE = "synthetic_review_only"
ROUTES = {
    "content": ("planning", "revise_then_reapprove"),
    "visual": ("direction_prompt", "regenerate_after_reapproval"),
    "timing": ("production_editing", "rebuild_after_approval"),
    "subtitle": ("production_editing", "rebuild_after_approval"),
}
REQUEST_FIELDS = {"schema_version", "reviewer", "decision", "notes", "issues"}
INSPECTION_FIELDS = {"schema_version", "kind", "source", "scope", "real_execution_allowed",
                     "checked_at", "inputs", "result_snapshot", "status", "technical_result",
                     "failure", "routes", "human_review", "content_sha256"}
REVIEW_FIELDS = {"schema_version", "kind", "source", "scope", "real_execution_allowed",
                 "reviewed_at", "inspection_sha256", "binding", "status", "request",
                 "routes", "content_sha256"}


def _route(stage, action, *, scene_number=None, note=""):
    return {"target_stage": stage, "next_action": action, "scene_number": scene_number,
            "note": note, "auto_execute": False, "requires_revalidation": True}


def _snapshot(result):
    # Do not follow unsafe paths or manifest-supplied filenames to collect evidence.
    snapshot = {"requested_location_sha256": _digest(str(result)), "location": None,
                "state": "unavailable", "files": {}}
    try:
        folder = _result_dir(result)
    except (OSError, ValueError):
        return snapshot
    snapshot.update(location=folder.relative_to(WORKSPACE.absolute()).as_posix(), state="present")
    for name in ("manifest.json", *PAYLOADS, "failure.json"):
        try:
            snapshot["files"][name] = {"state": "present", **_file_record(_file(folder, name))}
        except (OSError, ValueError):
            snapshot["files"][name] = {"state": "missing_or_unsafe"}
    return snapshot


def _inspection_core(values, result):
    inputs = _input_digests(values)
    snapshot = _snapshot(result)
    failure, technical, routes = None, None, []
    try:
        technical = validate_mock_result(*values, result)
        status = "technical_pass"
    except MockResultValidationError as error:
        status = "blocked" if error.target_stage in (
            "input_approval", "result_validation", "local_environment") else "rework_required"
        failure = {"check_id": error.check_id, "message": str(error)}
        routes = [_route(error.target_stage, error.next_action)]
    except Exception as error:
        # Unknown failures never become an invented diagnosis or a successful check.
        status = "blocked"
        failure = {"check_id": "unknown_validation_failure", "message": type(error).__name__}
        routes = [_route("unknown", "needs_manual_triage")]
    after = _snapshot(result)
    if _canonical(snapshot) != _canonical(after):
        status, technical = "blocked", None
        failure = {"check_id": "snapshot_changed_during_validation",
                   "message": "result changed during inspection; preserve it and inspect again"}
        routes = [_route("unknown", "needs_manual_triage")]
        snapshot = after
    return {"inputs": inputs, "result_snapshot": snapshot, "status": status,
            "technical_result": technical, "failure": failure, "routes": routes,
            "human_review": "not_recorded"}


def _seal(value):
    value["content_sha256"] = _digest(value)
    return value


def _check_record(value, fields, kind, time_field):
    if (not isinstance(value, dict) or set(value) != fields or
            type(value["schema_version"]) is not int or value["schema_version"] != 1 or
            value["kind"] != kind or value["source"] != SOURCE or value["scope"] != SCOPE or
            value["real_execution_allowed"] is not False):
        raise ValueError(f"unsupported {kind} contract")
    content = {key: item for key, item in value.items() if key != "content_sha256"}
    if value["content_sha256"] != _digest(content):
        raise ValueError(f"{kind} content has changed")
    when = _timestamp(value[time_field])
    if when > datetime.now(timezone.utc):
        raise ValueError(f"{kind} timestamp is in the future")
    return when


def inspect_mock_result(plan, direction, prompts, pricing, quote, approval, result):
    """Preserve a new report even for technical failures; no repair is executed."""
    core = _inspection_core((plan, direction, prompts, pricing, quote, approval), result)
    return _seal({"schema_version": 1, "kind": "mock_inspection", "source": SOURCE,
                  "scope": SCOPE, "real_execution_allowed": False,
                  "checked_at": datetime.now(timezone.utc).isoformat(), **core})


def validate_mock_inspection(inspection, plan, direction, prompts, pricing, quote, approval, result):
    _check_record(inspection, INSPECTION_FIELDS, "mock_inspection", "checked_at")
    current = _inspection_core((plan, direction, prompts, pricing, quote, approval), result)
    saved = {key: inspection[key] for key in current}
    if _canonical(_stable_core(saved)) != _canonical(_stable_core(current)):
        raise ValueError("inspection is stale or does not match current inputs and result")
    return inspection


def _stable_core(core):
    failure = core["failure"]
    if failure is not None:
        if (not isinstance(failure, dict) or set(failure) != {"check_id", "message"} or
                not isinstance(failure["check_id"], str) or not failure["check_id"] or
                not isinstance(failure["message"], str)):
            raise ValueError("unsupported inspection failure contract")
        # Native diagnostics can contain per-process addresses. Preserve the raw
        # message in the sealed report, but compare currentness using stable facts.
        failure = {"check_id": failure["check_id"]}
    return {**core, "failure": failure}


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _request(request, plan):
    if (not isinstance(request, dict) or set(request) != REQUEST_FIELDS or
            type(request["schema_version"]) is not int or request["schema_version"] != 1):
        raise ValueError("unsupported review request contract")
    reviewer, notes = _text(request["reviewer"], "reviewer"), _text(request["notes"], "notes")
    decision, issues = request["decision"], request["issues"]
    if decision not in ("accept", "request_changes") or not isinstance(issues, list):
        raise ValueError("invalid review decision or issues")
    if (decision == "accept" and issues) or (decision == "request_changes" and not issues):
        raise ValueError("accept requires no issues; request_changes requires issues")
    scenes = plan.get("scenes", []) if isinstance(plan, dict) else []
    numbers = {scene["number"] for scene in scenes if isinstance(scene, dict) and
               type(scene.get("number")) is int}
    normalized, routes = [], []
    for issue in issues:
        if (not isinstance(issue, dict) or set(issue) != {"category", "scene_number", "note"} or
                not isinstance(issue["category"], str) or issue["category"] not in ROUTES):
            raise ValueError("unsupported review issue")
        number = issue["scene_number"]
        if number is not None and (type(number) is not int or number not in numbers):
            raise ValueError("review issue scene_number does not exist")
        note = _text(issue["note"], "issue note")
        normalized.append({"category": issue["category"], "scene_number": number, "note": note})
        stage, action = ROUTES[issue["category"]]
        routes.append(_route(stage, action, scene_number=number, note=note))
    return {"schema_version": 1, "reviewer": reviewer, "decision": decision,
            "notes": notes, "issues": normalized}, routes


def _review_body(request, inspection, plan):
    request, routes = _request(request, plan)
    if request["decision"] == "accept" and inspection["status"] != "technical_pass":
        raise ValueError("technical failure or blocked inspection cannot be accepted")
    return {"inspection_sha256": _digest(inspection),
            "binding": {"inputs": deepcopy(inspection["inputs"]),
                        "result_snapshot": deepcopy(inspection["result_snapshot"])},
            "status": "accepted_mock_result" if request["decision"] == "accept" else "changes_requested",
            "request": request, "routes": deepcopy(inspection["routes"]) + routes}


def review_mock_result(plan, direction, prompts, pricing, quote, approval, result, inspection, request):
    """Record the caller's explicit self-report, not proof they watched the video."""
    validate_mock_inspection(inspection, plan, direction, prompts, pricing, quote, approval, result)
    body = _review_body(request, inspection, plan)
    return _seal({"schema_version": 1, "kind": "mock_result_review", "source": SOURCE,
                  "scope": SCOPE, "real_execution_allowed": False,
                  "reviewed_at": datetime.now(timezone.utc).isoformat(), **body})


def validate_mock_review(review, plan, direction, prompts, pricing, quote, approval, result, inspection):
    reviewed_at = _check_record(review, REVIEW_FIELDS, "mock_result_review", "reviewed_at")
    validate_mock_inspection(inspection, plan, direction, prompts, pricing, quote, approval, result)
    if reviewed_at < _timestamp(inspection["checked_at"]):
        raise ValueError("review cannot precede its inspection")
    body = _review_body(review["request"], inspection, plan)
    if _canonical({key: review[key] for key in body}) != _canonical(body):
        raise ValueError("review does not match the explicit request and inspection")
    return review
