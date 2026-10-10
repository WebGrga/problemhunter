"""Opt-in universal triage using exact JEV-selected source passages.

No invoice family rules, free-form model quotes, or confidence-as-demand logic.
Selections establish literal presence, not semantic truth or willingness forecasts.
"""
import hashlib
import math

from .benchmark import _answer
from .evidence_checks import passages
from .models import Problem
from .rubric import load_rubric, rubric_hash, snapshot

SELECTION_VERSION = 'passage-v1'
EXCERPT_FIELDS = {'problem_excerpt', 'workaround_excerpt', 'payment_excerpt'}


def parse_choice(answer, criteria):
    value = _answer({'value': answer}, 'value', 'choice', criteria)
    probabilities = answer.get('probabilities')
    confidence = answer.get('confidence')
    def valid(number):
        return type(number) in (int, float) and math.isfinite(number) and 0 <= number <= 1
    if (not valid(confidence) or not isinstance(probabilities, dict) or set(probabilities) != set(criteria)
            or not all(valid(p) for p in probabilities.values()) or not math.isclose(sum(probabilities.values()), 1, abs_tol=.02)):
        raise ValueError('Incomplete universal Choice distribution')
    gap = max(probabilities.values()) - probabilities[value]
    # Live API returned p0=.34 as choice while p1=.35. Preserve its choice and
    # flag the discrepancy rather than inventing an answer or rejecting the post.
    if gap > .0200001:
        raise ValueError('Universal Choice disagrees materially with its distribution')
    return value, gap > .000001


def build_request(source, scope, rubric):
    selected = {}
    parts = passages(source.content[:16000])
    for part in parts:
        for start in range(0, len(part), 1600):
            selected[f'p{len(selected)}'] = part[start:start + 1600].strip()
    truncated = len(source.content) > 16000 or len(selected) > 48
    selected = dict(list(selected.items())[:48])
    questions = snapshot(rubric)['questions']
    for field in EXCERPT_FIELDS:
        questions[field]['criteria'] = {'none': questions[field]['criteria']['none'],
            **{name: f'The source passage {name} in passages.' for name in selected}}
    return {'research_scope': scope, 'title': source.title, 'passages': selected}, questions, truncated


class UniversalEvaluator:
    offline = False

    def __init__(self, http, key, model='jev-latest', scope='Any real-world experienced problem; no topic restriction', rubric='general-v4'):
        self.http, self.key, self.model, self.scope = http, key, model, scope
        self.rubric = snapshot(load_rubric(rubric) if isinstance(rubric, str) else rubric)
        if self.rubric['routing']['mode'] != 'universal_v4':
            raise ValueError('UniversalEvaluator requires a universal_v4 rubric')
        self.rubric_fingerprint = rubric_hash(self.rubric) + ':' + SELECTION_VERSION + ':' + hashlib.sha256(scope.encode()).hexdigest()

    async def evaluate(self, sources):
        if not self.key:
            raise ValueError('TYPESAFE_API_KEY is required for universal evaluation')
        problems = []
        for source in sources:
            state, questions, truncated = build_request(source, self.scope, self.rubric)
            if not state['passages']:
                source.metadata['triage'] = {'accepted': False, 'route': 'excluded', 'rejection_reasons': ['empty source']}
                continue
            response = await self.http.request('POST', 'https://api.typesafe.ai/v1/systemone', provider='jev',
                headers={'Authorization': f'Bearer {self.key}'}, json={'model': self.model, 'state': state, 'questions': questions})
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get('answers'), dict) or not isinstance(payload.get('model'), str):
                raise ValueError('Incomplete universal JEV response')
            usage = payload.get('usage')
            if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('input_tokens', 'output_tokens')):
                raise ValueError('Missing universal JEV token usage')
            parsed, answer_flags = {}, []
            for name, q in questions.items():
                if q['type'] == 'choice':
                    parsed[name], inconsistent = parse_choice(payload['answers'].get(name), q['criteria'])
                    if inconsistent:
                        answer_flags.append(f'{name}: reported choice differs slightly from highest returned probability; inspect raw answer')
                else:
                    parsed[name] = _answer(payload['answers'], name, q['type'], q.get('criteria'))
            impact = state['passages'].get(parsed['problem_excerpt'])
            workaround = state['passages'].get(parsed['workaround_excerpt'])
            payment = state['passages'].get(parsed['payment_excerpt'])
            reasons, review, payment_review = [], answer_flags, []
            if not impact:
                reasons.append('No selected experienced problem passage')
            if parsed['relevance'] == 'no':
                reasons.append('Experienced problem is outside scope')
            if parsed['evidence_kind'] in {'promotion_or_general', 'satisfied_low_burden'}:
                reasons.append('No concrete experienced burden')
            if parsed['relevance'] == 'adjacent':
                review.append('Related but different topic')
            if parsed['first_hand'] < self.rubric['routing']['first_hand_review_threshold'] or parsed['evidence_kind'] == 'unclear':
                review.append('Experienced attribution needs review')
            if source.content_kind == 'snippet':
                review.append('Snippet may mix speakers; original attribution unverified')
            if truncated:
                review.append('Only a bounded part of the source was evaluated')
            if impact and parsed['pain'] <= 1:
                review.append('Selected impact and low severity need review')
            signal = parsed['payment_signal']
            if signal != 'unknown' and not payment:
                payment_review.append('Payment classification has no selected remedy-payment passage')
                signal = 'unknown'
            if signal == 'unknown' and payment:
                payment_review.append('Payment passage conflicts with unknown classification')
            supported = {'pain': parsed['pain'] / (len(questions['pain']['criteria']) - 1)} if impact else {}
            if workaround:
                for field in ('workaround_burden', 'replacement_motivation'):
                    supported[field] = parsed[field] / (len(questions[field]['criteria']) - 1)
            weights = self.rubric['weights']
            coverage = sum(weights[k] for k in supported)
            score = round(sum(weights[k] * v for k, v in supported.items()) / coverage * 100, 2) if coverage else None
            triage = {'accepted': not reasons, 'route': 'excluded' if reasons else 'review' if review else 'primary',
                'rejection_reasons': reasons, 'review_reasons': review + payment_review,
                'payment_review_reasons': payment_review, 'score': score,
                'rubric_version': self.rubric['version'], 'ranking_policy': 'priority_before_review_flag',
                'dimensions': supported, 'supported_dimensions': list(supported), 'coverage_weight': coverage,
                'need_status': parsed['need_status'], 'payment_signal': signal, 'payment_signal_model': parsed['payment_signal'],
                'problem_family': None, 'parsed': parsed, 'research_scope': self.scope}
            source.metadata.update(triage=triage, evaluation_content_truncated=truncated)
            if reasons:
                continue
            # A snippet's pronouns cannot establish the original thread author's experience.
            firsthand = impact if source.content_kind != 'snippet' and parsed['first_hand'] >= .6 else None
            evidence = {'mode': 'jev', 'content_kind': source.content_kind, 'first_hand': firsthand,
                'impact': impact, 'workaround': workaround, 'loss': None, 'willingness_to_pay': None,
                'verified_payment': None, 'payment_candidate': {'signal': signal, 'quote': payment,
                    'status': 'model_selected_literal_excerpt; meaning requires review'} if payment and signal != 'unknown' else None,
                'evaluation_model': payload['model'], 'evaluation_rubric': self.rubric,
                'evaluation_rubric_sha256': self.rubric_fingerprint, 'evaluation_usage_batch': usage,
                'raw_judgments': payload['answers'], 'rendered_questions': questions,
                'selected_passages': state['passages'], 'selection_version': SELECTION_VERSION}
            statement = f'{source.title}: {impact}' if source.title else impact
            judgments = {'first_hand': parsed['first_hand'] if firsthand else 0, 'experienced_impact': 1,
                'loss': 0, 'workaround': float(bool(workaround)), 'willingness_to_pay': 0,
                'severity': supported['pain'], 'evaluation_mode': 'jev_universal_experimental', 'triage': triage}
            problems.append(Problem(source.id, statement[:2000], parsed['category'], judgments, evidence,
                hashlib.sha256((source.id + statement).encode()).hexdigest()[:24]))
        return problems
