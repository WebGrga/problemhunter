import httpx
import pytest

from problem_hunter.intelligence import Evaluator, SynthesisClient, FIELDS, explicit_evidence
from problem_hunter.models import Source


class HTTP:
    def __init__(self, payload):
        self.payload, self.requests = payload, []

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return httpx.Response(200, json=self.payload, request=httpx.Request(method, url))


def answers(count=1):
    result = {}
    for i in range(count):
        for name in FIELDS:
            result[f"{i}_{name}"] = {"type": "noul", "noul": 1}
        result[f"{i}_severity"] = {"type": "score", "score": 2.5, "confidence": .9}
        result[f"{i}_category"] = {"type": "choice", "choice": "services", "confidence": .9}
    return {"answers": result, "usage": {"input_tokens": 50, "output_tokens": 20}, "model": "jev-1.13.0"}


@pytest.mark.asyncio
async def test_jev_batches_and_parses_fractional_score():
    http = HTTP(answers(2))
    sources = [Source(f"https://example.com/{i}", "Appointment problem", "I waste hours manually managing appointments.", id=str(i)) for i in range(2)]
    result = await Evaluator(http, key="fixture", batch_size=2).evaluate(sources)
    assert len(http.requests) == 1
    payload = http.requests[0][2]["json"]
    assert len(payload["questions"]) == 14
    assert len(payload["state"]) == 2
    assert result[0].judgments["severity"] == .625
    assert result[0].evidence["loss"] in sources[0].content
    # Model confidence that payment exists never creates a payment quote.
    assert result[0].evidence["willingness_to_pay"] is None


@pytest.mark.asyncio
async def test_default_evaluation_isolates_documents_but_batches_questions():
    http = HTTP(answers())
    sources = [Source(f'https://example.com/{i}', 'p', 'I waste hours manually managing bookings.', id=str(i)) for i in range(2)]
    await Evaluator(http, key='fixture').evaluate(sources)
    assert len(http.requests) == 2
    for method, url, kwargs in http.requests:
        assert list(kwargs['json']['state']) == ['record_0']
        assert len(kwargs['json']['questions']) == 7
        assert all('record_0.content' in q['instructions'] for q in kwargs['json']['questions'].values())


@pytest.mark.asyncio
async def test_missing_key_fails_without_implicit_offline_fallback():
    with pytest.raises(ValueError, match="TYPESAFE_API_KEY"):
        await Evaluator(HTTP({})).evaluate([])


@pytest.mark.asyncio
async def test_invalid_jev_payload_is_not_silently_accepted():
    payload = answers()
    payload["answers"]["0_genuine"]["noul"] = 2
    with pytest.raises(ValueError, match="Invalid JEV"):
        await Evaluator(HTTP(payload), key="fixture").evaluate([Source("https://example.com", "p", "problem", id="1")])


@pytest.mark.asyncio
async def test_offline_is_labeled_and_uses_literal_evidence():
    source = Source("https://example.com", "Manual work", "We manually handle appointments. I would pay for automation.", id="a")
    result = await Evaluator(HTTP({}), offline=True).evaluate([source])
    assert result[0].evidence["mode"] == "offline_heuristic"
    assert result[0].evidence["willingness_to_pay"] == "I would pay for automation."


@pytest.mark.asyncio
async def test_synthesis_adapter_parses_explicit_endpoint():
    http = HTTP({"choices": [{"message": {"content": '{"groups": [["a"]]}'}}]})
    llm = SynthesisClient(http, "https://example.com/chat/completions", "key", "chosen-model")
    assert await llm.ask("Group", []) == {"groups": [["a"]]}
    assert http.requests[0][2]["provider"] == "llm"


@pytest.mark.asyncio
async def test_llm_invented_quote_is_rejected():
    class LLM:
        async def ask(self, *args):
            return {"statement": "Appointment workflow is slow", "evidence": {"willingness_to_pay": "I pay $50 monthly."}}
    source = Source("https://example.com", "Manual work", "We manually handle appointments.", id="a")
    result = await Evaluator(HTTP(answers()), key="fixture", llm=LLM()).evaluate([source])
    assert result[0].evidence["willingness_to_pay"] is None


def test_explicit_evidence_does_not_infer_payment_from_cost():
    assert explicit_evidence("This costs $500 and is frustrating.")["willingness_to_pay"] is None


def test_normal_working_hours_are_not_explicit_loss():
    assert explicit_evidence('I contract for up to 25 hours per week.')['loss'] is None
    assert explicit_evidence('We lose hours manually checking stock every day.')['loss'] is not None


@pytest.mark.asyncio
async def test_statement_prefers_real_complaint_over_ordinary_hours():
    source = Source('https://example.com', 'Invoices', 'I contract for up to 25 hours per week. The owner asked about missing invoices which I have inexplicably not sent.', id='a')
    problems = await Evaluator(HTTP(answers()), key='fixture').evaluate([source])
    assert problems[0].statement.startswith('The owner asked')


@pytest.mark.asyncio
async def test_non_object_answer_is_a_descriptive_error():
    payload = answers()
    payload['answers']['0_genuine'] = None
    with pytest.raises(ValueError, match='answer object'):
        await Evaluator(HTTP(payload), key='fixture').evaluate([Source('https://example.com', 'p', 'problem', id='1')])
    assert explicit_evidence("I pay nothing for this.")["willingness_to_pay"] is None
