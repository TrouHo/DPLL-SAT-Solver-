from copy import deepcopy

import pytest

from frontend.mock_solver import EXAMPLES, solve_expression
from frontend.trace_schema import validate_result


def test_empty_clause_and_satisfied_cnf_are_not_interchangeable():
    result = solve_expression(EXAMPLES["Easy SAT"])
    broken = deepcopy(result)
    broken["events"][-1]["remaining_cnf"] = [[]]
    with pytest.raises(ValueError, match="solution event"):
        validate_result(broken)


def test_rejects_non_contiguous_sequence():
    result = solve_expression(EXAMPLES["Unit chain"])
    result["events"][2]["seq"] = 7
    with pytest.raises(ValueError, match="contiguous"):
        validate_result(result)


def test_rejects_unknown_literal_id():
    result = solve_expression(EXAMPLES["Easy SAT"])
    result["initial_cnf"][0].append(99)
    with pytest.raises(ValueError, match="unknown variable ID"):
        validate_result(result)


def test_partial_model_must_explicitly_satisfy_every_clause():
    result = solve_expression(EXAMPLES["SAT + backtrack"])
    result["assignment"] = {"A": False}
    result["events"][-1]["assignment"] = {"A": False}
    with pytest.raises(ValueError, match="does not satisfy"):
        validate_result(result)


def test_empty_variables_are_valid_only_for_empty_initial_cnf():
    valid = {
        "status": "SAT", "input_expression": "A | !A", "variables": {},
        "initial_cnf": [], "assignment": {},
        "events": [
            {"seq": 0, "type": "start", "node_id": "n0", "parent_id": None,
             "variable": None, "value": None, "assignment": {}, "remaining_cnf": [],
             "reason_clause": None, "from_node": None, "message": "Start."},
            {"seq": 1, "type": "solution", "node_id": "n0", "parent_id": None,
             "variable": None, "value": None, "assignment": {}, "remaining_cnf": [],
             "reason_clause": None, "from_node": None, "message": "Solved."},
        ],
    }
    validate_result(valid)
    invalid = deepcopy(valid)
    invalid["initial_cnf"] = [[]]
    with pytest.raises(ValueError, match="only when initial_cnf is empty"):
        validate_result(invalid)

