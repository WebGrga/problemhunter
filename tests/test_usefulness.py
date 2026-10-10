import json

import httpx
import pytest

from problem_hunter.discovery import Discovery
from problem_hunter.extraction import Extractor
from problem_hunter.http import HTTP
from problem_hunter.landscape import subject_questions, parse_subject, consolidate
from problem_hunter.models import Source
from problem_hunter.models import Opportunity
from problem_hunter.research import Researcher, validate_brief
from problem_hunter.pipeline import Pipeline
from problem_hunter.storage import Store
from problem_hunter.universal import UniversalEvaluator
from test_universal import response


def choices(questions, selected):
    return {'model': 'fixture', 'usage': {'input_tokens': 100, 'output_tokens': 10},
        'answers': {name: {'type': 'choice', 'choice': selected[name], 'confidence': 1,
            'probabilities': {k: float(k == selected[name]) for k in q['criteria']}}
            for name,q in questions.items()}}


@pytest.mark.asyncio
async def test_short_card_does_not_replace_snippet_or_override_original_date(monkeypatch):
    monkeypatch.setattr('problem_hunter.extraction.socket.getaddrinfo', lambda *a,**k: [(2,1,6,'',('8.8.8.8',443))])
    class Client:
        async def request(self,method,url,**kwargs):
            body = '<meta property="article:published_time" content="2019-09-01"><meta property="article:modified_time" content="2026-01-01"><article>Unrelated course card.</article>'
            return httpx.Response(404 if url.endswith('robots.txt') else 200,text=body,
                headers={'content-type':'text/html'},request=httpx.Request(method,url))
    source = await Extractor(Client()).enrich(Source('https://example.org/article','Article','Original search lead',published_at='2026-01-01',content_kind='snippet'))
    assert source.content_kind == 'snippet' and source.content == 'Original search lead'
    assert source.published_at == '2019-09-01'
    assert source.metadata['search_reported_at'] == '2026-01-01'
    assert source.metadata['modified_at'] == '2026-01-01'
    assert source.metadata['date_conflict']


@pytest.mark.asyncio
async def test_main_body_not_recommendation_article_and_jsonld_publication(monkeypatch):
    monkeypatch.setattr('problem_hunter.extraction.socket.getaddrinfo', lambda *a,**k: [(2,1,6,'',('8.8.8.8',443))])
    text = 'I cannot access the supplied lesson materials and lose classroom time. ' * 8
    class Client:
        async def request(self,method,url,**kwargs):
            body = '<script type="application/ld+json">{"@type":"Article","datePublished":"2025-06-01","dateModified":"2026-01-01"}</script><main>'+text+'</main><article>Related post</article>'
            return httpx.Response(404 if url.endswith('robots.txt') else 200,text=body,
                headers={'content-type':'text/html'},request=httpx.Request(method,url))
    source = await Extractor(Client()).fetch('https://example.org/article')
    assert source.content == text.strip() and source.content_kind == 'full_text'
    assert source.published_at == '2025-06-01'


@pytest.mark.asyncio
async def test_date_filters_and_invalid_window_before_requests():
    calls=[]
    class Client:
        async def request(self,method,url,**kwargs):
            calls.append(kwargs['params'])
            return httpx.Response(200,json={},request=httpx.Request(method,url))
    discovery=Discovery(Client(),'fixture')
    await discovery.search('feedback',since='2025-01-01',until='2026-10-10')
    await discovery.search('feedback','hn',since='2025-01-01',until='2026-10-10')
    assert calls[0]['freshness']=='2025-01-01to2026-10-10'
    assert 'created_at_i>=' in calls[1]['numericFilters']
    with pytest.raises(ValueError):
        await discovery.hunt('feedback',since='2026-01-01',until='2025-01-01')
    assert len(calls)==2


@pytest.mark.asyncio
@pytest.mark.parametrize('fit,failure,accepted',[('adjacent','yes',False),('yes','no',False),('yes','yes',True)])
async def test_v5_actor_task_and_positive_outcome_gates(tmp_path,fit,failure,accepted):
    def handler(request):
        payload=json.loads(request.content);q=payload['questions']
        if 'actor_task_fit' not in q:
            return httpx.Response(200,json=response(q,workaround='p1'))
        selected={'actor_task_fit':fit,'experienced_failure':failure,'experience_status':'resolved',
            'workaround_same_speaker':'no',**{f:'none' for f in ('actor','task','consequence','unmet_constraint','existing_remedy')}}
        return httpx.Response(200,json=choices(q,selected))
    with Store(tmp_path/'store.db') as store:
        async with HTTP(store,rate=0,transport=httpx.MockTransport(handler)) as http:
            groups=await Pipeline(store,UniversalEvaluator(http,'fixture',rubric='general-v5')).process([
                Source('https://example.org/post','Feedback','I receive vague client feedback. Another commenter recommends a tool.',author='alice')])
        assert bool(groups)==accepted
        if accepted:
            p=store.load_problems()[0]
            assert p.evidence['workaround'] is None
            assert p.evidence['problem_representation']['selections']['experience_status']=='resolved'
            assert p.judgments['triage']['need_status']=='historical_resolved'
            assert groups[0].review_required


def test_fixed_subject_quotes_include_late_price_and_do_not_borrow_competitor():
    content='ClipNote collects contextual client feedback. '+ 'Ordinary introduction. '*65 + 'ClipNote costs $12 per month. OtherTool costs $50 per month.'
    q,excerpts=subject_questions(content,{'task':'collect feedback'},'ClipNote')
    assert 'ClipNote costs $12 per month.' in q['pricing']['criteria'].values()
    picked={name:next(iter(question['criteria'])) for name,question in q.items()}
    picked.update(kind='software',role='independent',fit='yes',constraint_status='unknown',adoption_type='unknown',single_subject='no')
    picked['function']=next(k for k,v in excerpts.items() if v=='ClipNote collects contextual client feedback.')
    picked['pricing']=next(k for k,v in excerpts.items() if v=='OtherTool costs $50 per month.')
    picked['subject_anchor']=picked['function']
    e=parse_subject(picked,excerpts,{'content':content},'ClipNote')
    assert e['fit']=='yes' and 'pricing' not in e['claims']


@pytest.mark.asyncio
async def test_v2_multiple_identities_condition_claims_on_fixed_subject(tmp_path):
    body='ClipNote captures client website screenshots. ClipNote costs $12 monthly. PinBoard collects contextual website annotations. PinBoard costs $20 monthly.'
    source=Source('https://review.example/tools','Feedback comparison',body)
    class Search:
        async def search(self,query,provider):
            return [source]
    class Extract:
        async def enrich(self,source):
            return source
    calls=[]
    def handler(request):
        p=json.loads(request.content);q=p['questions'];calls.append(p['state'].get('fixed_remedy'))
        if 'remedy_0' in q:
            picked={f'remedy_{i}':next((k for k,v in q[f'remedy_{i}']['criteria'].items() if v==name),'none')
                for i,name in enumerate(['ClipNote','PinBoard','none'])}
        elif 'function_quote' in p['state']:
            assert p['state']['function_quote']
            picked={'fit':'yes','constraint_status':'unknown',**{k:'yes' for k in q if k.startswith('subject_')}}
        else:
            name=p['state']['fixed_remedy']
            picked={k: ('none' if 'none' in v['criteria'] else 'unknown' if 'unknown' in v['criteria'] else 'no') for k,v in q.items()}
            picked.update(kind='software',role='independent',fit='yes',constraint_status='unknown',adoption_type='unknown',single_subject='no')
            picked['function']=next(k for k,v in q['function']['criteria'].items() if v.startswith(name+' ') and v.endswith('screenshots.' if name=='ClipNote' else 'annotations.'))
            picked['pricing']=next(k for k,v in q['pricing']['criteria'].items() if v==f'{name} costs ${12 if name=="ClipNote" else 20} monthly.')
            picked['subject_anchor']=picked['function']
        return httpx.Response(200,json=choices(q,picked))
    item=Opportunity('a','Vague feedback','I lose time reproducing vague client reports','technology',research_brief=validate_brief({
        'affected_person':'Web developer','task':'Collect client website feedback','desired_outcome':'Contextual bug reports',
        'unmet_constraint':'Agent-ready context','remedy_types':['software']}))
    with Store(tmp_path/'store.db') as store:
        async with HTTP(store,rate=0,transport=httpx.MockTransport(handler)) as http:
            await Researcher(Search(),Extract(),http=http,jev_key='fixture').research([item])
        store.save_opportunities([item])
        assert len(store.load_opportunities()[0].solution_landscape['offerings'])==2
    assert calls==[None,'ClipNote','ClipNote','PinBoard','PinBoard']
    offerings=item.solution_landscape['offerings']
    assert {o['name'] for o in offerings}=={'ClipNote','PinBoard'}
    assert all(o['name'] in o['claims']['pricing'][0]['quote'] for o in offerings)


def test_partial_task_fit_cannot_establish_well_served_even_with_satisfied_claim():
    source={'url':'https://clip.example/features','name':'ClipNote','content_kind':'full_text',
        'offering_evidences':[{'name':'ClipNote','kind':'software','role':'provider','fit':'partial',
            'constraint_status':'satisfied','adoption_type':'unknown',
            'claims':{'function':'ClipNote collects feedback.','constraint':'ClipNote is open source.'}}]}
    result=consolidate([source],{'unmet_constraint':'Open source with client access and agent integration'})
    assert result['offerings'][0]['task_fit']=='partially_supported'
    assert result['offerings'][0]['constraint_status']=='unknown'
    assert result['disposition']['status']=='insufficient_information'
    assert result['disposition']['closest_remedy_id']==result['offerings'][0]['id']

