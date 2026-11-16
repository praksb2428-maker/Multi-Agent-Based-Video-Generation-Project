"""Fictional quote and approval exercises, with no production executor."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from hashlib import sha256

from src.direction import _canonical, create_prompts


UNIT = "mock_credit"
POLICY_VERSION = "mock-production-v1"
MOCK_TTL = timedelta(hours=1)
PRICING_FIELDS = {"schema_version", "source", "unit", "video_per_second",
                  "narration_per_100_characters", "assembly_fixed"}
APPROVAL_FIELDS = {"schema_version", "kind", "scope", "status", "quote_sha256",
                   "policy_version", "approved_by", "reason", "approved_at",
                   "expires_at", "real_execution_allowed", "content_sha256"}


def _digest(value):
    return sha256(_canonical(value)).hexdigest()


def _label(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def validate_mock_pricing(pricing):
    if not isinstance(pricing, dict) or set(pricing) != PRICING_FIELDS:
        raise ValueError("invalid mock pricing fields")
    if type(pricing["schema_version"]) is not int or pricing["schema_version"] != 1:
        raise ValueError("unsupported mock pricing schema")
    if pricing["source"] != "fictional_test_only" or pricing["unit"] != UNIT:
        raise ValueError("only fictional mock_credit pricing is allowed")
    for name in ("video_per_second", "narration_per_100_characters", "assembly_fixed"):
        if type(pricing[name]) is not int or not 0 <= pricing[name] <= 1_000_000_000:
            raise ValueError(f"{name} must be an integer from 0 to 1000000000")
    return pricing


def create_mock_quote(plan, direction, prompts, pricing):
    """Recompute a fictional estimate; max_budget is only a mock numeric cap."""
    expected_prompts = create_prompts(plan, direction)
    if _canonical(prompts) != _canonical(expected_prompts):
        raise ValueError("prompts do not match the current approved plan and direction")
    validate_mock_pricing(pricing)
    lines = []
    for scene in direction["scenes"]:
        seconds = int(Decimal(str(scene["duration_seconds"])).to_integral_value(rounding=ROUND_CEILING))
        characters = len(scene["audio"]["narration"])
        narration_blocks = (characters + 99) // 100
        video = seconds * pricing["video_per_second"]
        narration = narration_blocks * pricing["narration_per_100_characters"]
        lines.append({"number": scene["number"], "billable_seconds": seconds,
                      "narration_characters": characters, "narration_blocks": narration_blocks,
                      "video_units": video, "narration_units": narration,
                      "subtotal_units": video + narration})
    total = sum(line["subtotal_units"] for line in lines) + pricing["assembly_fixed"]
    if total > 2**63 - 1:
        raise ValueError("mock total exceeds the supported integer range")
    budget = Decimal(str(plan["brief"]["max_budget"]))
    return {"schema_version": 1, "kind": "mock_quote", "source": "fictional_test_only",
            "unit": UNIT, "real_execution_allowed": False,
            "budget_interpretation": "max_budget numeric cap in mock_credit; not real currency",
            "plan_sha256": _digest(plan), "direction_sha256": _digest(direction),
            "prompts_sha256": _digest(prompts), "pricing_sha256": _digest(pricing),
            "lines": lines, "assembly_units": pricing["assembly_fixed"],
            "total_units": total, "budget_limit_units": str(budget),
            "within_budget": Decimal(total) <= budget}


def validate_mock_quote(quote, plan, direction, prompts, pricing):
    expected = create_mock_quote(plan, direction, prompts, pricing)
    if _canonical(quote) != _canonical(expected):
        raise ValueError("mock quote does not match current inputs and recalculated amounts")
    return quote


def _now(now):
    result = datetime.now(timezone.utc) if now is None else now
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("current time must be a timezone-aware UTC datetime")
    return result


def _timestamp(value):
    try:
        if not isinstance(value, str):
            raise ValueError("timestamp must be a string")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError("timestamp must use UTC")
        return parsed
    except (TypeError, ValueError) as error:
        raise ValueError("mock approval timestamps must be timezone-aware UTC") from error


def approve_mock_production(plan, direction, prompts, pricing, quote, *, approved_by, reason, now=None):
    """Record a mock-only confirmation; this is not identity or spending authority."""
    validate_mock_quote(quote, plan, direction, prompts, pricing)
    if not quote["within_budget"]:
        raise ValueError("mock quote exceeds the mock budget")
    approved_at = _now(now)
    approval = {"schema_version": 1, "kind": "mock_production_approval", "scope": "mock_only",
                "status": "mock_approved", "real_execution_allowed": False,
                "policy_version": POLICY_VERSION, "quote_sha256": _digest(quote),
                "approved_by": _label(approved_by, "approved_by"),
                "reason": _label(reason, "reason"), "approved_at": approved_at.isoformat(),
                "expires_at": (approved_at + MOCK_TTL).isoformat()}
    approval["content_sha256"] = _digest(approval)
    return approval


def validate_mock_approval(approval, plan, direction, prompts, pricing, quote, *, now=None):
    validate_mock_quote(quote, plan, direction, prompts, pricing)
    if not quote["within_budget"]:
        raise ValueError("mock quote exceeds the mock budget")
    if not isinstance(approval, dict) or set(approval) != APPROVAL_FIELDS:
        raise ValueError("invalid mock approval fields")
    if (type(approval["schema_version"]) is not int or approval["schema_version"] != 1 or
            approval["kind"] != "mock_production_approval" or approval["scope"] != "mock_only" or
            approval["status"] != "mock_approved" or approval["real_execution_allowed"] is not False or
            approval["policy_version"] != POLICY_VERSION):
        raise ValueError("unsupported mock approval contract")
    _label(approval["approved_by"], "approved_by")
    _label(approval["reason"], "reason")
    content = {key: value for key, value in approval.items() if key != "content_sha256"}
    if approval["content_sha256"] != _digest(content) or approval["quote_sha256"] != _digest(quote):
        raise ValueError("mock approval content or quote has changed")
    approved_at, expires_at = _timestamp(approval["approved_at"]), _timestamp(approval["expires_at"])
    current = _now(now)
    if expires_at - approved_at != MOCK_TTL or not approved_at <= current < expires_at:
        raise ValueError("mock approval is future-dated, expired, or has invalid expiry")
    return approval
