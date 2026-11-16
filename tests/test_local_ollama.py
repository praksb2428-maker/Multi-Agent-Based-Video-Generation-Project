import copy
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import httpx

import shorts_cli
from src import local_ollama as local
from src.direction import create_direction
from src.shorts import create_draft, is_approved
from test_shorts import BRIEF


def answer():
    plan = create_draft(BRIEF)
    creative = {k: copy.deepcopy(plan[k]) for k in ('hook', 'story', 'scenes')}
    creative['hook'] = '분리배출 전, 내용물을 비웠나요?'
    return {'model': local.MODEL, 'done': True, 'done_reason': 'stop',
            'message': {'role': 'assistant', 'content': json.dumps(creative)},
            'created_at': '2026-11-16T00:00:00Z', 'total_duration': 123}


class LocalOllamaTests(unittest.TestCase):
    def transport(self, response=None, *, tags=None, version=None, handler=None):
        seen = []
        response = answer() if response is None else response
        def route(request):
            seen.append(request)
            self.assertEqual(request.url.host, '127.0.0.1')
            self.assertEqual(request.url.port, 11434)
            self.assertNotIn('authorization', request.headers)
            if handler:
                custom = handler(request)
                if custom is not None:
                    return custom
            if request.url.path == '/api/version':
                return httpx.Response(200, json=version if version is not None else {'version': local.VERSION})
            if request.url.path == '/api/tags':
                return httpx.Response(200, json=tags if tags is not None else {
                    'models': [{'name': local.MODEL, 'model': local.MODEL,
                                'digest': local.MODEL_DIGEST.removeprefix('sha256:')}]})
            self.assertEqual(request.url.path, '/api/chat')
            return httpx.Response(200, json=response)
        return httpx.MockTransport(route), seen

    def test_fixed_request_metadata_and_manual_approval_boundary(self):
        transport, seen = self.transport()
        original = copy.deepcopy(BRIEF)
        plan = local.create_local_draft(BRIEF, _transport=transport)
        self.assertEqual(BRIEF, original)
        self.assertEqual(plan['brief'], BRIEF)
        self.assertEqual(plan['status'], 'draft')
        self.assertIsNone(plan['approval'])
        self.assertIsNone(plan['cost_estimate'])
        self.assertIn(local.MODEL_DIGEST, plan['source'])
        self.assertFalse(is_approved(plan))
        with self.assertRaises(ValueError):
            create_direction(plan)
        self.assertEqual([r.url.path for r in seen], ['/api/version','/api/tags','/api/chat'])
        payload = json.loads(seen[-1].content)
        self.assertEqual(payload['model'], local.MODEL)
        self.assertIs(payload['stream'], False)
        self.assertIs(payload['think'], False)
        self.assertEqual(payload['keep_alive'], 0)
        self.assertEqual(payload['options']['num_ctx'], 4096)
        self.assertEqual(json.loads(payload['messages'][1]['content']), BRIEF)

    def test_no_network_dns_or_secret_proxy_environment_on_mock_path(self):
        transport, _ = self.transport()
        blocked = {'OPENAI_API_KEY','OPENAI_BASE_URL','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY'}
        class Guard(dict):
            def get(self,key,default=None):
                if key in blocked:
                    raise AssertionError('secret/proxy environment read')
                return super().get(key,default)
            def __getitem__(self,key):
                if key in blocked:
                    raise AssertionError('secret/proxy environment read')
                return super().__getitem__(key)
        with patch('os.environ', Guard()), \
             patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')) as connect, \
             patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')) as dns:
            for key in blocked:
                with self.assertRaises(AssertionError):
                    os.environ.get(key)
            local.create_local_draft(BRIEF, _transport=transport)
            self.assertEqual(connect.call_count, 0)
            self.assertEqual(dns.call_count, 0)

    def test_schema_uses_object_items_and_keeps_scene_constraints(self):
        # Ollama 0.40.16 rejects boolean items before generation. Exercise a
        # transport with that real boundary while retaining index/time pairs.
        def schema_boundary(request):
            if request.url.path != '/api/chat':
                return None
            payload=json.loads(request.content)
            scenes=payload['format']['properties']['scenes']
            if not isinstance(scenes.get('items'),dict):
                return httpx.Response(400,json={'error':'schema must be an object'})
            self.assertEqual((scenes['minItems'],scenes['maxItems']),(3,3))
            pairs=[(item['properties']['number']['const'],item['properties']['duration_seconds']['const'])
                   for item in scenes['items']['anyOf']]
            self.assertEqual(pairs,[(1,6),(2,15),(3,9)])
            for item in scenes['items']['anyOf']:
                self.assertEqual(set(item['required']),local.SCENE_FIELDS)
                self.assertIs(item['additionalProperties'],False)
            return None
        transport,_=self.transport(handler=schema_boundary)
        plan=local.create_local_draft(BRIEF,_transport=transport)
        self.assertIsNone(plan['approval'])

    def test_version_missing_model_and_digest_fail_before_chat(self):
        for kwargs in ({'version':{'version':'0.0.0'}},{'tags':{'models':[]}},
                       {'tags':{'models':[{'name':local.MODEL,'model':local.MODEL,'digest':'sha256:wrong'}]}},
                       {'tags':{'models':[{'name':'qwen3.5:cloud','model':'qwen3.5:cloud','digest':local.MODEL_DIGEST}]}},
                       {'tags':{'models':None}}):
            with self.subTest(kwargs=kwargs):
                transport, seen = self.transport(**kwargs)
                with self.assertRaises(ValueError):
                    local.create_local_draft(BRIEF, _transport=transport)
                self.assertNotIn('/api/chat', [r.url.path for r in seen])

    def test_rejects_redirect_http_errors_without_retry_or_fallback(self):
        for status in (301,401,404,429,500):
            transport, seen = self.transport(handler=lambda req: httpx.Response(
                status,headers={'Location':'https://example.invalid'}))
            with self.assertRaises(ValueError):
                local.create_local_draft(BRIEF, _transport=transport)
            self.assertEqual(len(seen),1)

    def test_timeout_and_unavailable_are_bounded_failures(self):
        for error in (httpx.ReadTimeout('slow'),httpx.ConnectError('unavailable')):
            def failed(request):
                raise error
            transport, seen = self.transport(handler=failed)
            with self.assertRaisesRegex(ValueError,'no retry or fallback'):
                local.create_local_draft(BRIEF, _transport=transport)
            self.assertEqual(len(seen),1)

    def test_incomplete_wrong_model_refusal_and_tools_are_rejected(self):
        good = answer()
        bad = [dict(good,done=False),dict(good,done_reason='length'),dict(good,model='qwen3.5:cloud'),
               dict(good,message={'role':'assistant','content':'{}','refusal':'refused'}),
               dict(good,message={'role':'assistant','content':'{}','tool_calls':[{}]}),
               dict(good,message={'role':'user','content':'{}'}),dict(good,message={'role':'assistant','content':None})]
        for response in bad:
            with self.subTest(response=response):
                transport, _ = self.transport(response)
                with self.assertRaises(ValueError):
                    local.create_local_draft(BRIEF, _transport=transport)

    def test_creative_fields_cannot_overwrite_application_approval_or_input(self):
        creative = json.loads(answer()['message']['content'])
        for field in ('approval','brief','status','cost_estimate','source'):
            response = answer()
            response['message']['content']=json.dumps(dict(creative,**{field:{}}))
            transport, _ = self.transport(response)
            with self.assertRaisesRegex(ValueError,'only hook'):
                local.create_local_draft(BRIEF, _transport=transport)

    def test_strict_json_rejects_duplicate_nonfinite_invalid_and_null(self):
        for content in ('null','NaN','{"hook":"a","hook":"b"}','{"hook":Infinity}', '```json\n{}\n```'):
            response = answer(); response['message']['content']=content
            transport, _ = self.transport(response)
            with self.assertRaises(ValueError):
                local.create_local_draft(BRIEF, _transport=transport)

    def test_scene_fields_forbidden_text_and_invalid_duration(self):
        for mutation in ('extra','duration','forbidden','number','count'):
            response=answer(); creative=json.loads(response['message']['content'])
            if mutation=='extra': creative['scenes'][0]['approval']=True
            elif mutation=='duration': creative['scenes'][0]['duration_seconds']=999
            elif mutation=='forbidden': creative['scenes'][0]['script']=BRIEF['forbidden'][0]
            elif mutation=='number': creative['scenes'][0]['number']=2
            else: creative['scenes']=creative['scenes'][:1]
            response['message']['content']=json.dumps(creative)
            transport, _=self.transport(response)
            with self.assertRaises(ValueError):
                local.create_local_draft(BRIEF,_transport=transport)

    def test_input_response_bytes_and_elapsed_limits(self):
        transport, seen=self.transport()
        with self.assertRaisesRegex(ValueError,'input limit'):
            local.create_local_draft(dict(BRIEF,style='a'*local.MAX_BRIEF_BYTES),_transport=transport)
        self.assertEqual(seen,[])
        transport, seen=self.transport(handler=lambda req:httpx.Response(200,content=b' '* (local.MAX_RESPONSE_BYTES+1)))
        with self.assertRaisesRegex(ValueError,'byte limit'):
            local.create_local_draft(BRIEF,_transport=transport)
        with patch('src.local_ollama.time.monotonic',side_effect=[0,local.MAX_SECONDS+1]):
            with self.assertRaisesRegex(ValueError,'time budget'):
                local.create_local_draft(BRIEF,_transport=self.transport()[0])

    def test_arbitrary_transport_is_not_a_real_endpoint_override(self):
        with self.assertRaises(ValueError):
            local.create_local_draft(BRIEF,_transport=object())

    def test_cli_saves_unapproved_draft_and_separate_test_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'brief.json'; output=root/'draft.json'; approved=root/'approved.json'
            source.write_text(json.dumps(BRIEF),encoding='utf-8')
            transport,_=self.transport()
            original_generate=local.create_local_draft
            def generate(brief): return original_generate(brief,_transport=transport)
            with patch('src.local_ollama.create_local_draft',side_effect=generate),patch('sys.stdout',new=io.StringIO()):
                self.assertEqual(shorts_cli.main(['draft-local',str(source),str(output)]),0)
                draft=json.loads(output.read_text(encoding='utf-8'))
                self.assertFalse(is_approved(draft))
                self.assertEqual(shorts_cli.main(['approve',str(output),str(approved)]),0)
            self.assertTrue(is_approved(json.loads(approved.read_text(encoding='utf-8'))))
            original=output.read_bytes()
            with patch('src.local_ollama.create_local_draft',side_effect=AssertionError('must not generate')), \
                 patch('sys.stderr',new=io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    shorts_cli.main(['draft-local',str(source),str(output)])
            self.assertEqual(error.exception.code,2)
            self.assertEqual(output.read_bytes(),original)

    def test_cli_generation_failure_never_creates_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'brief.json'; output=root/'missing-parent/draft.json'
            source.write_text(json.dumps(BRIEF),encoding='utf-8')
            with patch('src.local_ollama.create_local_draft',side_effect=ValueError('model failure')),patch('sys.stderr',new=io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    shorts_cli.main(['draft-local',str(source),str(output)])
            self.assertEqual(error.exception.code,2)
            self.assertFalse(output.parent.exists())


if __name__=='__main__':
    unittest.main()
