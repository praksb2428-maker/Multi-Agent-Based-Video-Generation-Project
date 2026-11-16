import copy
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx

from src.local_model_mock import LOCAL_URL, MODEL_PLACEHOLDER, draft_local_mock
from src.shorts import create_draft
from test_shorts import BRIEF


class LocalModelMockTests(unittest.TestCase):
    def test_adapter_serializes_local_shape_and_never_uses_network(self):
        requests = []
        creative = {k: v for k, v in create_draft(BRIEF).items() if k in ("hook", "story", "scenes")}
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"done": True, "message": {
                "role": "assistant", "content": json.dumps(creative)}})
        blocked = {"OPENAI_API_KEY", "OPENAI_BASE_URL", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"}
        safe = {key: os.environ.get(key, "") for key in ("PATH", "PATHEXT", "SystemRoot", "WINDIR")}
        reads = []
        class Guard(dict):
            def __getitem__(self, key):
                if key in blocked:
                    reads.append(key)
                    raise AssertionError("secret/proxy environment read")
                return super().__getitem__(key)
            def get(self, key, default=None):
                if key in blocked:
                    reads.append(key)
                    raise AssertionError("secret/proxy environment read")
                return super().get(key, default)
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")) as connect, \
             patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")) as dns, \
             patch("os.environ", Guard(safe)):
            for key in blocked:
                with self.assertRaises(AssertionError):
                    os.environ.get(key)
            reads.clear()
            result = draft_local_mock(BRIEF, transport=httpx.MockTransport(handler))
            # Assert the sentinels are effective, then distinguish intentional probes.
            with self.assertRaises(AssertionError):
                socket.getaddrinfo("example.invalid", 443)
            probe = socket.socket()
            try:
                with self.assertRaises(AssertionError):
                    probe.connect(("127.0.0.1", 11434))
            finally:
                probe.close()
            self.assertEqual((connect.call_count, dns.call_count), (1, 1))
            self.assertEqual(reads, [])
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), LOCAL_URL)
        body = json.loads(requests[0].content)
        self.assertEqual(body["model"], MODEL_PLACEHOLDER)
        self.assertIs(body["stream"], False)
        self.assertEqual(result["source"], "local_model_mock")
        self.assertIsNone(result["approval"])
        self.assertEqual(result["brief"], BRIEF)

    def test_null_injected_approval_bad_scenes_and_invalid_envelopes_are_rejected(self):
        baseline = create_draft(BRIEF)
        creative = {k: copy.deepcopy(baseline[k]) for k in ("hook", "story", "scenes")}
        bad = [None, dict(creative, approval={}), dict(creative, scenes=None), dict(creative, hook="")]
        for value in bad:
            with self.subTest(value=value):
                transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
                    "message": {"role": "assistant", "content": json.dumps(value)}, "done": True}))
                with self.assertRaises(ValueError):
                    draft_local_mock(BRIEF, transport=transport)
        for value in [None, {"done": False}, {"message": {"content": "{}"}, "done": True}]:
            with self.assertRaises(ValueError):
                draft_local_mock(BRIEF, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=value)))

    def test_no_real_transport_redirect_retry_or_fallback(self):
        with self.assertRaises(ValueError):
            draft_local_mock(BRIEF, transport=object())
        for code in (301, 401, 429, 500):
            seen = []
            def handler(request):
                seen.append(request)
                return httpx.Response(code, headers={"Location": "https://example.invalid"})
            with self.assertRaises(ValueError):
                draft_local_mock(BRIEF, transport=httpx.MockTransport(handler))
            self.assertEqual(len(seen), 1)

    def test_duplicate_nonfinite_and_null_content_are_not_silently_replaced(self):
        for content in ('{"hook":"a","hook":"b","story":"s","scenes":[]}', 'NaN', 'null'):
            with self.assertRaises(ValueError):
                draft_local_mock(BRIEF, transport=httpx.MockTransport(lambda request: httpx.Response(
                    200, json={"done": True, "message": {"role": "assistant", "content": content}})))
