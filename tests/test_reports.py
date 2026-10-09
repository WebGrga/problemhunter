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

