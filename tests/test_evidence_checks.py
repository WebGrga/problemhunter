import pytest

from problem_hunter.evidence_checks import ground_payment


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
