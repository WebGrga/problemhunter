import pytest

from problem_hunter.evidence_checks import ground_payment, loss_quote
from problem_hunter.benchmark import revised_priority
from problem_hunter.rubric import load_rubric


def response(kind="experienced_burden", payment="unknown", relevance="yes", pain=2):
    r = load_rubric("v3")
    choices = {"first_hand": .95, "evidence_kind": kind, "payment_signal": payment, "relevance": relevance, "need_status": "ongoing"}
    return {"answers": {name: {"type": q["type"], q["type"]: choices.get(name, pain if name == "pain" else 2)} for name, q in r["questions"].items()}}


def test_short_underpayment_is_literal_and_not_availability_vetoed():
    text = "I invoice $380 and they send me $365."
    assert loss_quote(text) == text
    result = revised_priority(response(), load_rubric("v3"), text)
    assert result["accepted"]
    assert result["supported_dimensions"] == ["pain"]
    assert result["score"] == 50


def test_loss_conflicts_are_reviewed_not_silently_discarded():
    text = "I waste hours preparing invoices manually."
    result = revised_priority(response(kind="satisfied_low_burden", pain=.5), load_rubric("v3"), text)
    assert result["accepted"] and result["route"] == "review"
    assert len(result["review_reasons"]) == 2


@pytest.mark.parametrize("text", ["I hand invoices to my accountant.", "My customer paid me $500 for my work.", "I paid all my employees while invoices stayed unpaid.", "I use a free software tool."])
def test_payment_requires_explicit_remedy_spending(text):
    assert ground_payment(text, "spending_workaround") is None
    assert ground_payment(text, "paid_solution") is None


@pytest.mark.parametrize("text,signal", [
    ("I hired an office manager to chase invoices.", "spending_workaround"),
    ("I paid $50 for invoice automation software.", "paid_solution"),
    ("I would pay for an invoice automation tool.", "explicit_intent"),
    ("I won't pay for another invoice software tool.", "explicit_refusal"),
])
def test_literal_payment_categories_are_traceable(text, signal):
    result = ground_payment(text, signal)
    assert result["quote"] == text
    assert result["verification"] == "literal_rule_check"


def test_model_payment_without_quote_becomes_unknown_and_review():
    text = "I waste hours gathering invoices for my accountant."
    result = revised_priority(response(payment="spending_workaround"), load_rubric("v3"), text)
    assert result["payment_signal"] == "unknown"
    assert result["payment_signal_model"] == "spending_workaround"
    assert result["verified_payment"] is None
    assert result["route"] == "review"


def test_irrelevance_not_overridden_by_real_loss():
    result = revised_priority(response(relevance="no"), load_rubric("v3"), "I waste hours in unpaid lunch meetings.")
    assert not result["accepted"]
