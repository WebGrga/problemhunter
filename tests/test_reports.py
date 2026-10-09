import json

import pytest

from problem_hunter.models import Opportunity, Problem, Source
from problem_hunter.reports import export_report


def example():
    sources = [Source("https://example.org/a", "Report A", "Complaint A", author="Alice", id="a"),
               Source("https://example.org/b", "Report B", "Complaint B", id="b")]
    opportunities = [Opportunity("o", "Appointments", "Manual entry loses hours", "restaurants",
        source_ids=["a", "b"], independent_sources=2, independent_complainants=2, score=60,
        evidence_strength="weak", score_breakdown={"pain": {"points": 20, "status": "observed"}},
        solutions=[{"name": "Calendar", "status": "observed", "weakness": "missing evidence"}],
        potential_fixes=["Automate entry"], unknowns=["Willingness to pay"],
        next_step="Interview users")]
    return opportunities, sources


def test_json_retains_all_sources_and_uncertainty(tmp_path):
    opportunities, sources = example()
    path = export_report(opportunities, sources, tmp_path / "report.json", "json")
    payload = json.loads(path.read_text())
    assert {source["id"] for source in payload["sources"]} == {"a", "b"}
    assert payload["opportunities"][0]["score"] == 60
    assert payload["opportunities"][0]["evidence_strength"] == "weak"
    assert payload["opportunities"][0]["unknowns"] == ["Willingness to pay"]
    assert payload["missing_source_ids"] == []


def test_markdown_traceability_and_labels(tmp_path):
    opportunities, sources = example()
    report = export_report(opportunities, sources, tmp_path / "report.md").read_text()
    assert "https://example.org/a" in report
    assert "https://example.org/b" in report
    assert "Evidence strength: weak" in report
    assert "hypotheses, requiring validation" in report
    assert "Willingness to pay" in report
    assert "Independent supporting sources: 2" in report
    assert "Interview users" in report


def test_missing_sources_explicit_and_invalid_format(tmp_path):
    opportunities, _ = example()
    path = export_report(opportunities, [], tmp_path / "report.json", "json")
    assert json.loads(path.read_text())["missing_source_ids"] == ["a", "b"]
    with pytest.raises(ValueError):
        export_report([], [], tmp_path / "invalid", "html")


def test_reports_include_judgments_verified_quotes_and_duplicate_links(tmp_path):
    opportunities, sources = example()
    sources[0].metadata = {"duplicate_urls": ["https://example.org/copy"],
                           "evaluation_mode": "offline_heuristic"}
    opportunities[0].problem_ids = ["problem-a"]
    problem = Problem("a", "Complaint A", "restaurants", id="problem-a",
        judgments={"evaluation_mode": "offline_heuristic", "severity": 3},
        evidence={"mode": "offline_heuristic", "loss": "Complaint A", "willingness_to_pay": "invented", "evaluation_model": "jev-1.13.0"})
    json_path = export_report(opportunities, sources, tmp_path / "report.json", "json", [problem])
    payload = json.loads(json_path.read_text())
    assert payload["problems"][0]["judgments"]["severity"] == 3
    assert payload["sources"][0]["metadata"]["duplicate_urls"] == ["https://example.org/copy"]
    report = export_report(opportunities, sources, tmp_path / "report.md", problems=[problem]).read_text()
    assert "https://example.org/copy" in report
    assert "not an independent report" in report
    assert "evaluation mode: offline_heuristic" in report
    assert 'Literal loss excerpt from `a`: "Complaint A"' in report
    assert "willingness_to_pay: excerpt could not be verified" in report
    assert "evaluation_model: excerpt could not be verified" not in report
    assert '"invented"' not in report


def test_actionable_summary_separates_priority_and_commercial_score(tmp_path):
    opportunities, sources = example()
    high_commercial = opportunities[0]
    high_commercial.score = 95
    high_commercial.investigation_priority = 30
    other = Opportunity("investigate", "Investigate recurring burden", "Complaint", "restaurants", score=10)
    other.investigation_priority = 80
    reviewed = Opportunity("review", "Review historical evidence", "Complaint", "restaurants", score=100)
    reviewed.investigation_priority = 99
    reviewed.review_required = True
    payload = json.loads(export_report([reviewed, high_commercial, other], sources,
        tmp_path / "report.json", "json").read_text())
    assert [item["id"] for item in payload["opportunities"]] == ["investigate", "o", "review"]
    summary = payload["opportunities"][0]["actionable_summary"]
    assert summary["investigation_priority"] == 80
    assert summary["commercial_opportunity_score"] == 10
    assert "Investigation priority 80.0/100" in summary["ranking_reason"]
    report = export_report([other], sources, tmp_path / "report.md").read_text()
    assert "investigation priority: 80.0/100; commercial opportunity score: 10.0/100" in report
    assert "not commercial viability" in report


def test_forged_quotes_and_payment_do_not_become_direct_evidence(tmp_path):
    opportunities, sources = example()
    opportunities[0].problem_ids = ["p"]
    problem = Problem("a", "Lost thousands", "restaurants", id="p",
        judgments={"triage": {"need_status": "unknown", "payment_signal": "paid_alternative"}},
        evidence={"literal_loss": "Lost thousands", "first_hand": "Complaint A",
                  "verified_payment": {"signal": "paid_alternative", "quote": "I pay $100"}})
    payload = json.loads(export_report(opportunities, sources, tmp_path / "report.json", "json", [problem]).read_text())
    summary = payload["opportunities"][0]["actionable_summary"]
    assert [entry["quote"] for entry in summary["strongest_problem_quotes"]] == ["Complaint A"]
    assert summary["payment_evidence"] == []
    assert any("Payment signal is unverified" in caution for caution in summary["cautions"])
    # Raw evidence remains available for audit, even when it cannot support the summary.
    assert payload["problems"][0]["evidence"]["verified_payment"]["quote"] == "I pay $100"
    report = export_report(opportunities, sources, tmp_path / "report.md", problems=[problem]).read_text()
    assert '"I pay $100"' not in report
    assert 'Literal literal_loss excerpt' not in report


def test_historical_need_verified_payment_and_limited_cards(tmp_path):
    opportunities, sources = example()
    sources[0].content = "Complaint A. I already pay $20 monthly for software."
    problems = [Problem("a", f"Complaint {index}", "restaurants", id=f"p{index}",
        judgments={"triage": {"need_status": "historical_resolved", "dimensions": {"pain": 0.8},
                              "supported_dimensions": ["pain"]}},
        evidence={"first_hand": "Complaint A", "verified_payment": {
            "signal": "paid_solution", "quote": "I already pay $20 monthly for software."}}) for index in range(4)]
    opportunities[0].problem_ids = [problem.id for problem in problems]
    opportunities[0].investigation_priority = 70
    report = export_report(opportunities, sources, tmp_path / "report.md", problems=problems).read_text()
    assert "historical_resolved" in report
    assert "Historical resolved complaints do not establish a current unmet need" in report
    assert "pain (0.80)" in report
    assert "Verified paid_solution excerpt" in report
    assert "Complaint summary (model inference): Complaint 3" not in report
    assert "1 additional judgments retained in JSON" in report
    assert "whether the complaint still occurs" in report


def test_legacy_order_still_uses_score_and_id(tmp_path):
    opportunities = [Opportunity("b", "B", "B", "x", score=50),
                     Opportunity("a", "A", "A", "x", score=50),
                     Opportunity("c", "C", "C", "x", score=60)]
    payload = json.loads(export_report(opportunities, [], tmp_path / "report.json", "json").read_text())
    assert [item["id"] for item in payload["opportunities"]] == ["c", "a", "b"]


@pytest.mark.parametrize("content,quote", [
    ("My customer paid me $20 for the software I sold.", "My customer paid me $20 for the software I sold."),
    ("I pay $20 for software. I pay $30 for an app.", "I pay $30 for an app."),
])
def test_payment_claim_requires_rule_selected_remedy_quote(tmp_path, content, quote):
    opportunities, sources = example()
    sources[0].content = content
    opportunities[0].problem_ids = ["p"]
    problem = Problem("a", "Complaint", "restaurants", id="p",
        judgments={"triage": {"payment_signal": "paid_solution", "need_status": "ongoing"}},
        evidence={"verified_payment": {"signal": "paid_solution", "quote": quote}})
    payload = json.loads(export_report(opportunities, sources, tmp_path / "report.json", "json", [problem]).read_text())
    summary = payload["opportunities"][0]["actionable_summary"]
    assert summary["payment_evidence"] == []
    assert any("Payment signal is unverified" in caution for caution in summary["cautions"])
    assert any("at publication" in caution for caution in summary["cautions"])


def test_explicit_refusal_is_not_a_spending_buyer_or_unknown_payment(tmp_path):
    opportunities, sources = example()
    quote = "I won't pay for software."
    sources[0].content = quote
    opportunities[0].problem_ids = ["p"]
    problem = Problem("a", "Complaint", "restaurants", id="p",
        judgments={"triage": {"payment_signal": "explicit_refusal", "need_status": "ongoing"}},
        evidence={"willingness_to_pay": quote,
                  "verified_payment": {"signal": "explicit_refusal", "quote": quote}})
    payload = json.loads(export_report(opportunities, sources, tmp_path / "report.json", "json", [problem]).read_text())
    summary = payload["opportunities"][0]["actionable_summary"]
    assert summary["payment_evidence"][0]["signal"] == "explicit_refusal"
    assert not any("willingness to pay is unknown" in caution for caution in summary["cautions"])
    assert "why they would not pay" in summary["next_step"]
    assert "what they currently spend" not in summary["next_step"]
    report = export_report(opportunities, sources, tmp_path / "report.md", problems=[problem]).read_text()
    assert "Verified explicit_refusal excerpt" in report
    assert "Literal payment-related excerpt" in report
    assert "ongoing does not establish" in report

