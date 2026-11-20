import pytest

from frontend.mock_solver import EXAMPLES, solve_expression
from frontend.solver_adapter import solve_expression as adapter_solve
from frontend.trace_schema import validate_result


@pytest.mark.parametrize(
    ("name", "expected"),
    [("SAT + backtrack", "SAT"), ("UNSAT", "UNSAT"), ("Unit chain", "SAT"), ("Easy SAT", "SAT")],
)
def test_all_fixtures_are_valid_and_have_expected_status(name, expected):
    result = solve_expression(EXAMPLES[name])
    assert result["status"] == expected
    assert [event["seq"] for event in result["events"]] == list(range(len(result["events"])))
    validate_result(result)


def test_backtracking_fixture_has_exact_core_snapshots():
    events = solve_expression(EXAMPLES["SAT + backtrack"])["events"]
    assert events[1]["remaining_cnf"] == [[2], [-2]]
    assert events[2]["remaining_cnf"] == [[]]
    assert events[4]["assignment"] == {}
    assert events[6]["remaining_cnf"] == []


def test_fixture_return_is_a_deep_copy_and_ascii_aliases_match():
    first = solve_expression("(!A | B) & (!A | !B) & (A | C)")
    first["events"][0]["remaining_cnf"].clear()
    second = solve_expression(EXAMPLES["SAT + backtrack"])
    assert second["events"][0]["remaining_cnf"] != []


def test_unsupported_mock_input_never_gets_a_manufactured_answer():
    with pytest.raises(ValueError, match="four predefined"):
        adapter_solve("A ∨ C", mode="mock")


def test_real_alias_uses_integrated_backend_without_falling_back_to_mock():
    result = adapter_solve("A | !A", mode="real")
    assert result["status"] == "SAT"
    assert result["initial_cnf"] == []


def test_navigation_bounds_are_clamped():
    from frontend.app import clamp_step

    assert clamp_step(-1, 8) == 0
    assert clamp_step(99, 8) == 7
    assert clamp_step(3, 8) == 3
    assert clamp_step(2, 0) == 0


def test_pl_only_easy_sat_uses_pure_literal_without_decision():
    result = solve_expression(EXAMPLES["Easy SAT"], rule_mode="pl_only")
    assert [event["type"] for event in result["events"]] == [
        "start", "pure_literal", "solution"
    ]
    assert result["assignment"] == {"B": True}
    assert result["events"][1]["remaining_cnf"] == []
    validate_result(result)


def test_up_only_easy_sat_remains_distinct_from_pl_only():
    up_only = solve_expression(EXAMPLES["Easy SAT"], rule_mode="up_only")
    pl_only = solve_expression(EXAMPLES["Easy SAT"], rule_mode="pl_only")
    assert any(event["type"] == "decision" for event in up_only["events"])
    assert not any(event["type"] == "decision" for event in pl_only["events"])


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_all_pl_only_mock_fixtures_are_static_valid_and_contain_no_up(name):
    result = solve_expression(EXAMPLES[name], rule_mode="pl_only")
    validate_result(result)
    assert not any(event["type"] == "unit_propagation" for event in result["events"])


@pytest.mark.parametrize("name", list(EXAMPLES))
def test_all_up_only_mock_fixtures_contain_no_pure_literal(name):
    result = solve_expression(EXAMPLES[name], rule_mode="up_only")
    assert not any(event["type"] == "pure_literal" for event in result["events"])

