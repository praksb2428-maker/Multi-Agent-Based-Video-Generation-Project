"""Explicit local rework stages. Approval remains a separate caller action.

Source inputs are supplied again at every stage; bundles contain hashes, never
paths to follow or commands to execute. Fixed files live under workspace only.
"""

from copy import deepcopy
from datetime import datetime, timezone

from src.direction import _canonical, create_direction, create_prompts
from src.mock_media import (_result_dir, _file, _json_read, _json_write,
                            produce_mock_media, validate_mock_result)
from src.mock_production import _digest, create_mock_quote, validate_mock_approval
from src.quality_feedback import inspect_mock_result, validate_mock_review
from src.shorts import is_approved, revise_plan


COMMON = {"schema_version", "kind", "scope", "real_execution_allowed", "status",
          "created_at", "binding", "content_sha256"}


def _record(kind, status, binding):
    value = {"schema_version": 1, "kind": kind, "scope": "local_mock_rework",
             "real_execution_allowed": False, "status": status,
             "created_at": datetime.now(timezone.utc).isoformat(), "binding": binding}
    value["content_sha256"] = _digest(value)
    return value


def _read(folder, name):
    return _json_read(_file(folder, name))


def _check(record, kind, status, binding):
    # Full canonical binding comparison also rejects injected flags/unknown fields.
    if (not isinstance(record, dict) or set(record) != COMMON or
            type(record["schema_version"]) is not int or record["schema_version"] != 1 or
            record["kind"] != kind or record["scope"] != "local_mock_rework" or
            record["real_execution_allowed"] is not False or record["status"] != status):
        raise ValueError("unsupported rework handoff contract")
    from src.mock_production import _timestamp
    if _timestamp(record["created_at"]) > datetime.now(timezone.utc):
        raise ValueError("rework timestamp is in the future")
    if (record["content_sha256"] != _digest({k: v for k, v in record.items() if k != "content_sha256"}) or
            _canonical(record["binding"]) != _canonical(binding)):
        raise ValueError("rework handoff is stale or changed")


def _source(values, result, inspection, review, revision):
    validate_mock_review(review, *values, result, inspection)
    if review["status"] != "changes_requested":
        raise ValueError("rework requires an explicit changes_requested review")
    if inspection["status"] == "blocked" or any(
            route["target_stage"] in ("unknown", "input_approval", "result_validation", "local_environment") or
            route["next_action"] == "needs_manual_triage" for route in review["routes"]):
        raise ValueError("blocked or unknown source requires manual triage before rework")
    draft = revise_plan(values[0], revision)
    return draft, {"source_inputs": [_digest(v) for v in values],
                   "source_inspection": _digest(inspection), "source_review": _digest(review),
                   "source_result": deepcopy(inspection["result_snapshot"]),
                   "revision_request": _digest(revision), "draft": _digest(draft)}


def rework_plan_mock(values, result, inspection, review, revision, output):
    draft, binding = _source(values, result, inspection, review, revision)
    folder = _result_dir(output, new=True)
    handoff = _record("mock_rework_plan", "awaiting_plan_approval", binding)
    folder.mkdir(parents=True, exist_ok=False)
    _json_write(folder / "draft.json", draft)
    _json_write(folder / "revision.json", revision)
    _json_write(folder / "handoff.json", handoff)
    return handoff


def _plan(values, result, inspection, review, revision, rework, approved):
    draft, binding = _source(values, result, inspection, review, revision)
    folder = _result_dir(rework)
    handoff = _read(folder, "handoff.json")
    _check(handoff, "mock_rework_plan", "awaiting_plan_approval", binding)
    if (_canonical(_read(folder, "draft.json")) != _canonical(draft) or
            _canonical(_read(folder, "revision.json")) != _canonical(revision)):
        raise ValueError("saved rework draft or revision has changed")
    if not is_approved(approved):
        raise ValueError("revised plan requires separate plan approval")
    unapproved = deepcopy(approved)
    unapproved.update(status="draft", approval=None)
    if _canonical(unapproved) != _canonical(draft):
        raise ValueError("approved plan does not match this exact revised draft")
    return handoff


def _prepared(approved, pricing, handoff):
    direction = create_direction(approved)
    prompts = create_prompts(approved, direction)
    quote = create_mock_quote(approved, direction, prompts, pricing)
    artifacts = {"plan.json": approved, "direction.json": direction, "prompts.json": prompts,
                 "pricing.json": pricing, "quote.json": quote}
    binding = {"plan_handoff": _digest(handoff),
               "files": {name: _digest(value) for name, value in artifacts.items()}}
    return artifacts, binding


def prepare_rework_mock(values, result, inspection, review, revision, rework, approved, output):
    handoff = _plan(values, result, inspection, review, revision, rework, approved)
    artifacts, binding = _prepared(approved, values[3], handoff)
    folder = _result_dir(output, new=True)
    prepared = _record("mock_rework_prepared", "awaiting_mock_production_approval", binding)
    folder.mkdir(parents=True, exist_ok=False)
    for name, value in artifacts.items():
        _json_write(folder / name, value)
    _json_write(folder / "handoff.json", prepared)
    return prepared


def produce_rework_mock(values, result, inspection, review, revision, rework, approved,
                        prepared, approval, output):
    # Reject missing/old/expired permission before source media tools or output creation.
    artifacts, _ = _prepared(approved, values[3], {})
    new_values = tuple(artifacts[name] for name in
                       ("plan.json", "direction.json", "prompts.json", "pricing.json", "quote.json"))
    validate_mock_approval(approval, *new_values)
    handoff = _plan(values, result, inspection, review, revision, rework, approved)
    artifacts, binding = _prepared(approved, values[3], handoff)
    folder = _result_dir(prepared)
    ready = _read(folder, "handoff.json")
    _check(ready, "mock_rework_prepared", "awaiting_mock_production_approval", binding)
    for name, value in artifacts.items():
        if _canonical(_read(folder, name)) != _canonical(value):
            raise ValueError("prepared rework inputs have changed")
    destination = _result_dir(output, new=True)
    new_values = (*new_values, approval)
    produce_mock_media(*new_values, destination)
    quality = validate_mock_result(*new_values, destination)
    inspected = inspect_mock_result(*new_values, destination)
    if inspected["status"] != "technical_pass":
        raise ValueError("new rework result requires manual inspection; preserve the attempt")
    receipt = _record("mock_rework_receipt", "technical_complete_mock_human_review_pending",
                      {"prepared_handoff": _digest(ready), "source_review": _digest(review),
                       "new_approval": _digest(approval), "quality": _digest(quality),
                       "inspection": _digest(inspected), "result": inspected["result_snapshot"],
                       "issues_resolution": "not_inferred"})
    _json_write(destination / "inspection.json", inspected)
    _json_write(destination / "rework.json", receipt)
    return receipt
