"""Local chat request adapter exercised only with an in-memory HTTP transport.

The target shape can later be adapted to a selected local server. This module
cannot open a real connection, install a runtime, or infer a supported model.
"""

from copy import deepcopy
import json

import httpx

from src.shorts import create_draft, validate_plan


LOCAL_URL = "http://127.0.0.1:11434/api/chat"
MODEL_PLACEHOLDER = "local-model-not-selected"


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate local response key")
        value[key] = item
    return value


def _constant(value):
    raise ValueError("non-finite local response value")


def local_request(brief, *, research=None):
    baseline = create_draft(brief, research=research)
    content = {"task": "Return only hook, story and scenes for this short-video brief.",
                 "brief": baseline["brief"], "required_scene_fields":
                 ["number", "duration_seconds", "script", "background", "action", "camera"]}
    if research is not None:
        from src.research_mock import research_context
        content["reference_data"] = research_context(research, brief)
    return {"model": MODEL_PLACEHOLDER, "stream": False, "format": "json",
            "messages": [{"role": "user", "content": json.dumps(content,
                ensure_ascii=False, allow_nan=False)}]}


def draft_local_mock(brief, *, transport=None, research=None):
    """Serialize a local-server-shaped request; accept only mock transport."""
    baseline = create_draft(brief, research=research)
    if transport is None:
        creative = {key: deepcopy(baseline[key]) for key in ("hook", "story", "scenes")}
        transport = httpx.MockTransport(lambda request: httpx.Response(
            200, json={"message": {"role": "assistant", "content": json.dumps(
                creative, ensure_ascii=False, allow_nan=False)}, "done": True}))
    if not isinstance(transport, httpx.MockTransport):
        raise ValueError("local model preparation accepts MockTransport only")
    with httpx.Client(transport=transport, trust_env=False, timeout=10,
                      follow_redirects=False) as client:
        response = client.post(LOCAL_URL, json=local_request(brief, research=research))
        if response.status_code != 200:
            raise ValueError("mock local server rejected the request; no retry or fallback")
        try:
            envelope = json.loads(response.content, object_pairs_hook=_object,
                                  parse_constant=_constant)
            if (not isinstance(envelope, dict) or set(envelope) != {"message", "done"} or
                    envelope["done"] is not True or not isinstance(envelope["message"], dict) or
                    set(envelope["message"]) != {"role", "content"} or
                    envelope["message"]["role"] != "assistant"):
                raise ValueError("invalid mock local completion envelope")
            content = envelope["message"]["content"]
            if not isinstance(content, str) or len(content) > 100_000:
                raise ValueError("invalid mock local completion content")
            creative = json.loads(content, object_pairs_hook=_object, parse_constant=_constant)
            if not isinstance(creative, dict) or set(creative) != {"hook", "story", "scenes"}:
                raise ValueError("local completion must contain creative fields only")
            if not isinstance(creative["scenes"], list) or any(
                    not isinstance(scene, dict) or set(scene) != {
                        "number", "duration_seconds", "script", "background", "action", "camera"}
                    for scene in creative["scenes"]):
                raise ValueError("invalid mock local scene contract")
            baseline.update(creative)
            baseline["source"] = "local_model_mock"
            validate_plan(baseline)
            return baseline
        except (TypeError, KeyError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid mock local response") from error
