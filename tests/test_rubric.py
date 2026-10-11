import pytest

from problem_hunter.rubric import load_rubric, rubric_hash, snapshot, validate_rubric


def test_immutable_snapshot():
    rubric = load_rubric("general-v5")
    frozen = snapshot(rubric)
    before = rubric_hash(frozen)
    rubric["questions"]["pain"]["instructions"] = "Changed question"
    assert rubric_hash(rubric) != before
    assert rubric_hash(frozen) == before
    assert frozen["routing"]["mode"] == "universal_v4"


@pytest.mark.parametrize("mutate", [
    lambda r: r["questions"]["pain"].update(type="magic"),
    lambda r: r["questions"]["pain"].update(criteria=["one"]),
    lambda r: r["weights"].update(pain=float("nan")),
    lambda r: r["weights"].update(pain=99),
    lambda r: r["routing"].update(first_hand_review_threshold=2),
    lambda r: r["questions"]["evidence_kind"]["criteria"].update(new_option="unsupported"),
])
def test_invalid_definition_rejected_before_calls(mutate):
    rubric = load_rubric("general-v5")
    mutate(rubric)
    with pytest.raises(ValueError):
        validate_rubric(rubric)
