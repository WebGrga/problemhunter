"""Opt-in experimental invoice evaluator; never silently replaces production."""
import hashlib
import re
from dataclasses import replace

from .benchmark import _evaluate_rubric
from .evidence_checks import complaint_excerpt, support_quotes, CHECK_VERSION
from .intelligence import explicit_evidence
from .models import Problem
from .rubric import load_rubric, snapshot, rubric_hash


def problem_family(content):
    """Invoice-specific grouping hypothesis, not learned semantic equivalence."""
    text = content.casefold()
    families = [
        ("installment_billing", r"installment|partial invoice|two payments|deposit.{0,80}remaining|50%.{0,80}50%"),
        ("invoice_document_collection", r"(?:gather|collect|grabb|sort|download|find|match|reconcil)\w*.{0,70}invoices?.{0,100}(?:accountant|expense|bank)|invoices?.{0,80}(?:accountant|expense|bank)"),
        ("invoice_integrity", r"duplicate invoice|lost.{0,25}invoice|missing.{0,25}invoice|cancel.{0,25}invoice|edit.{0,25}invoice|wrong.{0,25}invoice"),
        ("payment_collection", r"unpaid|overdue|late pay|not.{0,15}paid|chasing.{0,25}invoice|collect.{0,25}(?:payment|debt)|refus\w*.{0,20}pay"),
        ("invoice_generation", r"(?:creat|prepar|generat|issu|send|writ|bill)\w*.{0,35}invoices?|invoic\w*.{0,35}(?:excel|spreadsheet)|(?:excel|spreadsheet).{0,35}invoic"),
    ]
    return next((name for name, pattern in families if re.search(pattern, text)), None)


class ExperimentalEvaluator:
    offline = False

    def __init__(self, http, key, model="jev-latest", rubric="v3"):
        self.http, self.key, self.model = http, key, model
        self.rubric = snapshot(load_rubric(rubric) if isinstance(rubric, str) else rubric)
        if self.rubric.get("routing", {}).get("mode") != "grounded_v3":
            raise ValueError("Opt-in pipeline evaluation requires a grounded_v3 rubric")
        self.rubric_fingerprint = rubric_hash(self.rubric) + ":" + CHECK_VERSION
        self.evaluations = []

    async def evaluate(self, sources):
        if not self.key:
            raise ValueError("TYPESAFE_API_KEY is required for experimental evaluation")
        problems = []
        self.evaluations = []
        for source in sources:
            evaluated = replace(source, content=source.content[:16000])
            triage = await _evaluate_rubric(evaluated, self.http, self.key, self.model, self.rubric)
            self.evaluations.append({"source_id": source.id, **triage})
            source.metadata["triage"] = {k: v for k, v in triage.items() if k != "raw_response"}
            source.metadata["evaluation_content_truncated"] = len(source.content) > 16000
            if triage.get("error"):
                # Do not mark failed records as successfully evaluated/rejected.
                raise ValueError(f"JEV experimental evaluation failed for {source.id}: {triage['error']}")
            if not triage["accepted"]:
                continue
            statement = complaint_excerpt(evaluated.content)
            evidence = explicit_evidence(evaluated.content)
            evidence.update(mode="jev", content_kind=source.content_kind,
                            literal_loss=triage["literal_loss"], verified_payment=triage["verified_payment"],
                            evaluation_model=triage["raw_response"].get("model", self.model),
                            evaluation_rubric=self.rubric, evaluation_rubric_sha256=self.rubric_fingerprint,
                            evaluation_usage_batch=triage["raw_response"].get("usage", {}),
                            raw_judgments=triage["raw_response"]["answers"])
            evidence["loss"] = triage["literal_loss"]
            evidence["workaround"] = support_quotes(evaluated.content)["workaround_burden"]
            verified_payment = triage["verified_payment"]
            evidence["willingness_to_pay"] = verified_payment["quote"] if verified_payment and verified_payment["signal"] != "explicit_refusal" else None
            triage["problem_family"] = problem_family(evaluated.content)
            # Retain direct evidence independently of model numerical judgments.
            judgments = {"first_hand": triage["parsed"]["first_hand"], "loss": float(bool(evidence["loss"])),
                         "workaround": float(bool(evidence["workaround"])),
                         "willingness_to_pay": float(bool(evidence["willingness_to_pay"])),
                         "severity": triage["parsed"]["pain"] / (len(self.rubric["questions"]["pain"]["criteria"]) - 1),
                         "evaluation_mode": "jev_experimental", "triage": triage}
            problems.append(Problem(source_id=source.id, statement=statement, category="finance", judgments=judgments,
                                    evidence=evidence, id=hashlib.sha256((source.id + statement).encode()).hexdigest()[:24]))
        return problems
