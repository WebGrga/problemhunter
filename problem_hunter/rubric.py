"""Readable, validated JEV question definitions; snapshots are loaded once per run."""
import copy
import hashlib
import json
import math
from pathlib import Path

RUBRIC_DIR = Path(__file__).with_name("rubrics")


def load_rubric(name="general-v5"):
    path = RUBRIC_DIR / f"{name}.json" if name in {"general-v4", "general-v5", "production"} else Path(name)
    try:
        rubric = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot load rubric {path}: {exc}") from exc
    validate_rubric(rubric)
    return rubric


def validate_rubric(rubric):
    if not isinstance(rubric, dict) or rubric.get("schema_version") != 1 or not isinstance(rubric.get("version"), str) or not rubric["version"]:
        raise ValueError("Rubric requires schema_version=1 and a version")
    questions = rubric.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("Rubric requires named questions")
    for name, question in questions.items():
        if not isinstance(name, str) or not name or not isinstance(question, dict):
            raise ValueError("Invalid question definition")
        if question.get("type") not in {"noul", "choice", "score"} or not isinstance(question.get("instructions"), str) or not question["instructions"].strip():
            raise ValueError(f"Invalid type/instructions for {name}")
        criteria = question.get("criteria")
        if question["type"] == "score" and (not isinstance(criteria, list) or not 2 <= len(criteria) <= 10 or not all(isinstance(v, str) and v.strip() for v in criteria)):
            raise ValueError(f"Score {name} requires 2–10 ordered descriptions")
        if question["type"] == "choice" and (not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255 or not all(isinstance(k, str) and k and isinstance(v, str) and v.strip() for k, v in criteria.items())):
            raise ValueError(f"Choice {name} requires described options")
    if "routing" not in rubric:
        required = {"genuine", "first_hand", "workaround", "loss", "willingness_to_pay", "severity", "category"}
        if set(questions) != required:
            raise ValueError("Production rubric requires the seven supported questions")
        if any(questions[n]["type"] != "noul" for n in required - {"severity", "category"}) or questions["severity"]["type"] != "score" or questions["category"]["type"] != "choice":
            raise ValueError("Production question types cannot be changed")
        if len(questions["severity"]["criteria"]) != 5:
            raise ValueError("Production severity requires five levels")
        return
    routing, weights = rubric["routing"], rubric.get("weights")
    if not isinstance(routing, dict) or routing.get("mode") != "universal_v4":
        raise ValueError("Unsupported routing mode")
    if not isinstance(weights, dict) or set(weights) != {"pain", "workaround_burden", "replacement_motivation"} or not all(type(v) in {int, float} and math.isfinite(v) and v > 0 for v in weights.values()):
        raise ValueError("Priority weights must be positive finite numbers for the three dimensions")
    if not math.isclose(sum(weights.values()), 100):
        raise ValueError("Priority weights must total 100 so coverage is a percentage")
    if routing.get("minimum_supported_dimensions_for_primary_rank") != 1:
        raise ValueError("Universal routing requires one supported dimension")
    threshold = routing.get("first_hand_review_threshold")
    if type(threshold) not in {int, float} or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Routing threshold must be between zero and one")
    expected = set(weights) | {"first_hand", "relevance", "payment_signal", "evidence_kind", "need_status",
                               "category", "problem_excerpt", "workaround_excerpt", "payment_excerpt"}
    if set(questions) != expected:
        raise ValueError("Question IDs must match the selected routing mode")
    for name in expected:
        kind = "score" if name in weights else "noul" if name == "first_hand" else "choice"
        if questions[name]["type"] != kind:
            raise ValueError(f"Unexpected type for {name}")
    options = {"relevance": {"yes", "adjacent", "no"},
               "payment_signal": {"unknown", "explicit_refusal", "spending_workaround", "explicit_intent", "paid_solution"},
               "evidence_kind": {"experienced_burden", "experienced_workaround", "satisfied_low_burden", "promotion_or_general", "unclear"},
               "need_status": {"ongoing", "historical_resolved", "mixed", "unknown"}}
    for name, values in options.items():
        if set(questions[name]["criteria"]) != values:
            raise ValueError(f"Unsupported options for {name}; edit descriptions, not option IDs")
    for name in ('problem_excerpt', 'workaround_excerpt', 'payment_excerpt'):
        if set(questions[name]['criteria']) != {'none', 'passage'}:
            raise ValueError(f'{name} requires none/passage template options; actual IDs are supplied at runtime')


def snapshot(rubric):
    validate_rubric(rubric)
    return copy.deepcopy(rubric)


def rubric_hash(rubric):
    return hashlib.sha256(json.dumps(rubric, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
