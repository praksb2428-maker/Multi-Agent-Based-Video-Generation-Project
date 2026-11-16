"""Optional research contracts, using only synthetic fixtures and transports."""

from contextlib import ExitStack
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

import httpx

from shorts_web import LocalServer
from src.gui_workflow import Workflow
from src.local_model_mock import draft_local_mock, local_request
from src import local_ollama
from src.mock_media import WORKSPACE
from src.openai_mock import create_mock_draft
from src.research_mock import EMPTY_QUERY, canonical, research_context, search_mock, validate_research
from src.shorts import _content_digest, approve_plan, create_draft, is_approved, revise_plan, validate_plan
from test_shorts import BRIEF
import test_local_ollama
import test_web


ROOT = Path(__file__).resolve().parents[1]


class ResearchContracts(unittest.TestCase):
    def test_off_keeps_exact_legacy_output_and_approval_hash(self):
        golden = json.loads((ROOT/'tests/fixtures/legacy_plan_without_research_v1.json').read_text(encoding='utf-8'))
        plan = create_draft(golden['plan']['brief'])
        self.assertEqual(plan, golden['plan'])
        self.assertEqual(_content_digest(plan), golden['content_sha256'])
        self.assertNotIn('research', create_mock_draft(BRIEF))
        self.assertEqual(json.loads(local_ollama._request(BRIEF)['messages'][1]['content']), BRIEF)

    def test_mock_sources_are_bounded_explicit_and_all_brief_fields_are_bound(self):
        packet = search_mock(BRIEF)
        self.assertEqual(packet['status'], 'results')
        self.assertTrue(packet['is_mock'])
        self.assertEqual(len(packet['sources']), 2)
        self.assertIn('실제 검색', packet['warning'])
        for source in packet['sources']:
            self.assertTrue(source['is_mock'])
            self.assertTrue(source['url'].startswith('https://research.example.invalid/'))
        changes = {'topic': '다른 주제', 'style': '다른 스타일', 'audience': '다른 대상',
                   'target_seconds': 40, 'aspect_ratio': '1:1', 'max_budget': 999,
                   'forbidden': ['다른 금지']}
        for name, value in changes.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_research(packet, dict(BRIEF, **{name:value}))

    def test_null_duplicate_corrupt_nonfinite_oversize_and_forged_url_rejected(self):
        original = search_mock(BRIEF)
        values = [None, [], dict(original, schema_version=True)]
        for edit in (lambda p:p['sources'].append(deepcopy(p['sources'][0])),
                     lambda p:p['sources'][0].update(url='https://example.com/'),
                     lambda p:p['sources'][0].update(summary='x'*20_000),
                     lambda p:p.update(content_sha256='0'*64),
                     lambda p:p.update(extra=True),lambda p:p.update(query=float('nan'))):
            item=deepcopy(original);edit(item);values.append(item)
        for value in values:
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ValueError):
                validate_research(value, BRIEF)

    def test_empty_results_are_visible_but_cannot_be_used_for_generation(self):
        brief=dict(BRIEF,topic=EMPTY_QUERY)
        packet=search_mock(brief)
        self.assertEqual(packet['sources'], [])
        validate_research(packet,brief,allow_empty=True)
        with self.assertRaisesRegex(ValueError, '검색 결과'):
            create_draft(brief,research=packet)

    def test_research_changes_template_and_is_bound_to_manual_approval(self):
        packet=search_mock(BRIEF)
        plan=create_draft(BRIEF,research=packet)
        self.assertIn(packet['sources'][0]['summary'],plan['scenes'][1]['script'])
        self.assertIn('mock-001',plan['story'])
        self.assertIsNone(plan['approval'])
        approved=approve_plan(plan)
        self.assertTrue(is_approved(approved))
        for mutation in ('remove','edit','hash'):
            altered=deepcopy(approved)
            if mutation=='remove':del altered['research']
            elif mutation=='edit':altered['research']['sources'][0]['summary']='changed'
            else:altered['research']['content_sha256']='0'*64
            self.assertFalse(is_approved(altered))
        revised=revise_plan(approved,{'schema_version':1,'feedback':'explicit synthetic edit',
                                    'changes':{'hook':'새 도입 문구'}})
        self.assertEqual(revised['research'],packet)
        self.assertIsNone(revised['approval'])
        self.assertTrue(is_approved(approve_plan(revised)))

    def test_sdk_and_mock_local_requests_receive_reference_data(self):
        packet=search_mock(BRIEF);seen=[]
        plan=create_mock_draft(BRIEF,research=packet,request_log=seen)
        body=json.loads(seen[0]['body']['input'])
        self.assertEqual(body['reference_data'],research_context(packet,BRIEF))
        self.assertEqual(body['brief'],BRIEF)
        self.assertEqual(plan['research'],packet)
        self.assertIn('mock-001',plan['story'])
        request=local_request(BRIEF,research=packet)
        self.assertEqual(json.loads(request['messages'][0]['content'])['reference_data'],body['reference_data'])
        local_plan=draft_local_mock(BRIEF,research=packet)
        self.assertEqual(local_plan['research'],packet)
        self.assertIn('mock-001',local_plan['story'])

    def test_ollama_context_is_only_exercised_with_mock_transport(self):
        packet=search_mock(BRIEF)
        helper=test_local_ollama.LocalOllamaTests()
        transport,seen=helper.transport()
        plan=local_ollama.create_local_draft(BRIEF,research=packet,_transport=transport)
        payload=json.loads(seen[-1].content)
        user=json.loads(payload['messages'][1]['content'])
        self.assertEqual(user['reference_data']['sources'],packet['sources'])
        self.assertEqual(plan['research'],packet)
        self.assertIsNone(plan['approval'])

    def test_network_dns_and_real_credentials_are_not_read(self):
        envtype=type(os.environ);original=envtype.__getitem__
        def guarded(environment,key):
            if key.startswith(('OPENAI_','TAVILY_')) or key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):
                raise AssertionError('secret/proxy environment read')
            return original(environment,key)
        with ExitStack() as guards:
            for target in ('socket.socket.connect','socket.socket.connect_ex','socket.create_connection','socket.getaddrinfo'):
                guards.enter_context(patch(target,side_effect=AssertionError('network forbidden')))
            guards.enter_context(patch.object(envtype,'__getitem__',guarded))
            packet=search_mock(BRIEF)
            plan=create_mock_draft(BRIEF,research=packet)
            self.assertEqual(plan['research'],packet)


class ResearchGuiTests(unittest.TestCase):
    request=test_web.WebTests.request

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='research-tests-',dir=WORKSPACE)
        self.base=Path(self.temp.name);self.workflow=Workflow(self.base)
        self.server=LocalServer(0,self.workflow);self.port=self.server.server_port
        self.thread=Thread(target=self.server.serve_forever);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.thread.join(5);self.server.server_close();self.temp.cleanup()
        self.assertFalse(self.thread.is_alive())

    def search(self,brief=BRIEF):
        code,raw=self.request('POST','/api/research-mock',{'brief':brief})
        self.assertEqual(code,200,raw);return json.loads(raw)

    def create(self,identity=None,brief=BRIEF):
        payload={'brief':brief,'mode':'openai_mock'}
        if identity is not None:payload['research_id']=identity
        code,raw=self.request('POST','/api/jobs',payload)
        self.assertEqual(code,200,raw);return json.loads(raw)

    def action(self,state,action,payload=None,expected=200):
        code,raw=self.request('POST',f"/api/jobs/{state['id']}/action",{
            'sequence':state['sequence'],'action':action,'payload':{} if payload is None else payload})
        self.assertEqual(code,expected,raw);return json.loads(raw)

    def test_explicit_search_then_context_two_approvals_and_revision_without_researching(self):
        with patch('src.gui_workflow.search_mock',wraps=search_mock) as searching, \
                patch('src.gui_workflow.produce_mock_media',side_effect=AssertionError('implicit render')) as render:
            result=self.search();state=self.create(result['id'])
            self.assertEqual(state['draft']['research'],result['packet'])
            self.assertEqual(state['status'],'draft')
            original=(self.base/state['id']/'r0001/draft.json').read_bytes()
            self.action(state,'prepare',expected=400)
            state=self.action(state,'approve_plan');state=self.action(state,'prepare')
            self.action(state,'produce',expected=400)
            state=self.action(state,'approve_production',{'approved_by':'synthetic research tester','reason':'separate approval'})
            self.assertEqual(state['status'],'production_approved')
            self.assertFalse(state['real_execution_allowed'])
            reopened=Workflow(self.base).view(state['id'])
            self.assertEqual(reopened['draft']['research'],result['packet'])
            self.assertEqual(self.request('GET','/api/bootstrap')[0],200)
            draft=self.create(result['id'])
            draft=self.action(draft,'revise_draft',{'schema_version':1,'feedback':'explicit edit','changes':{'hook':'새 훅'}})
            self.assertEqual(draft['status'],'draft')
            self.assertEqual(draft['draft']['research'],result['packet'])
            self.assertIsNone(draft['draft']['approval'])
            self.assertEqual(searching.call_count,1)
            self.assertEqual((self.base/state['id']/'r0001/draft.json').read_bytes(),original)
            render.assert_not_called()

    def test_default_off_old_api_and_saved_jobs_still_work(self):
        state=self.create()
        self.assertNotIn('research',state['draft'])
        self.assertEqual(Workflow(self.base).view(state['id'])['draft'],state['draft'])
        self.assertNotIn('research',(self.base/state['id']/'creation.json').read_text(encoding='utf-8'))

    def test_stale_missing_empty_tampered_packets_fail_before_provider_and_job_save(self):
        result=self.search();empty=self.search(dict(BRIEF,topic=EMPTY_QUERY))
        saved=self.base/'research'/f"{result['id']}.json"
        with patch('src.gui_workflow.create_mock_draft',side_effect=AssertionError('should not generate')):
            for identity,brief in [('0'*32,BRIEF),(result['id'],dict(BRIEF,style='new style')),(empty['id'],dict(BRIEF,topic=EMPTY_QUERY))]:
                code,_=self.request('POST','/api/jobs',{'brief':brief,'mode':'openai_mock','research_id':identity})
                self.assertEqual(code,400)
            corrupted=json.loads(saved.read_text(encoding='utf-8'));corrupted['sources'][0]['summary']='changed'
            saved.write_text(json.dumps(corrupted),encoding='utf-8')
            self.assertEqual(self.request('POST','/api/jobs',{'brief':BRIEF,'mode':'openai_mock','research_id':result['id']})[0],400)
        self.assertEqual([p for p in self.base.iterdir() if p.name!='research'],[])

    def test_caller_cannot_inject_packet_url_key_live_or_invalid_id(self):
        for extra in ({'packet':{}},{'url':'https://example.com'},{'api_key':'not-a-key'},{'live':True}):
            self.assertEqual(self.request('POST','/api/research-mock',dict(brief=BRIEF,**extra))[0],400)
        for identity in (None,True,[],{},'../research','https://example.com'):
            self.assertEqual(self.request('POST','/api/jobs',{'brief':BRIEF,'mode':'openai_mock','research_id':identity})[0],400)
        self.assertEqual(self.request('POST','/api/jobs',{'brief':BRIEF,'mode':'openai_mock','research':search_mock(BRIEF)})[0],400)


if __name__=='__main__':unittest.main()
