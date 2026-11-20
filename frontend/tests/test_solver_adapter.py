import sys
from types import ModuleType

import pytest

from frontend.solver_adapter import (
    normalize_backend_result,
    normalize_expression_for_backend,
    simplify_cnf,
    solve_expression,
)


def test_unicode_expression_is_normalized_for_backend_only():
    visible = "(¬A ∨ B) ∧ (A → B) ∧ (A ↔ B)"
    assert normalize_expression_for_backend(visible) == "(!A | B) & (A -> B) & (A <-> B)"
    assert "¬" in visible


def test_simplify_cnf_keeps_true_and_conflict_distinct():
    assert simplify_cnf([[1, -2], [2]], {"A": True}, {"A": 1, "B": 2}) == [[2]]
    assert simplify_cnf([[1], [-1]], {"A": True}, {"A": 1}) == [[]]
    assert simplify_cnf([[1]], {"A": True}, {"A": 1}) == []


def test_backend_schema_normalization_resolves_clauses_and_snapshots():
    raw = {
        "status": "SAT",
        "assignment": {"A": True, "B": True},
        "clauses": [
            {"id": "c1", "literals": ["A", "!B"]},
            {"id": "c2", "literals": ["B"]},
        ],
        "events": [
            {"type": "root", "node_id": "n0", "assignment": {}},
            {"type": "unit_propagation", "node_id": "n0", "variable": "B", "value": True, "assignment": {"B": True}, "reason_clause": "c2"},
            {"type": "unit_propagation", "node_id": "n0", "variable": "A", "value": True, "assignment": {"A": True, "B": True}, "reason_clause": "c1"},
            {"type": "sat", "node_id": "n0", "assignment": {"A": True, "B": True}},
        ],
    }
    result = normalize_backend_result(raw, "visible formula")
    assert result["input_expression"] == "visible formula"
    assert result["variables"] == {"A": 1, "B": 2}
    assert result["initial_cnf"] == [[1, -2], [2]]
    assert result["events"][0]["type"] == "start"
    assert result["events"][1]["reason_clause"] == [2]
    assert result["events"][1]["remaining_cnf"] == [[1]]
    assert result["events"][-1]["type"] == "solution"


def test_backend_error_is_human_readable():
    with pytest.raises(RuntimeError, match="bad formula"):
        normalize_backend_result({"status": "ERROR", "message": "bad formula"}, "x")


def test_nested_backend_error_includes_code_message_and_parser_position():
    raw = {"status": "ERROR", "error": {
        "code": "SYNTAX_ERROR", "message": "Unexpected token.", "position": 3,
    }}
    with pytest.raises(RuntimeError, match=r"SYNTAX_ERROR: Unexpected token.*parser position 3"):
        normalize_backend_result(raw, "A →")


def test_backend_pl_mode_is_forwarded_to_the_in_process_service(monkeypatch):
    backend = ModuleType("backend")
    dpllsat = ModuleType("backend.dpllsat")
    service = ModuleType("backend.dpllsat.service")
    captured = {}
    def fake_solve(request):
        captured.update(request)
        return {
            "status": "SAT", "assignment": {}, "clauses": [],
            "events": [
                {"type": "root", "node_id": "n0", "assignment": {}},
                {"type": "solution", "node_id": "n0", "assignment": {}},
            ],
        }
    service.solve_request = fake_solve
    monkeypatch.setitem(sys.modules, "backend", backend)
    monkeypatch.setitem(sys.modules, "backend.dpllsat", dpllsat)
    monkeypatch.setitem(sys.modules, "backend.dpllsat.service", service)
    result = solve_expression("A ∨ ¬A", source="backend", rule_mode="pl_only")
    assert result["initial_cnf"] == []
    assert captured == {"expression": "A | !A", "trace": True, "rule_mode": "pl_only"}


def test_tautology_with_no_clauses_or_variables_is_valid():
    raw = {
        "status": "SAT", "assignment": {}, "clauses": [],
        "events": [
            {"type": "root", "node_id": "n0", "assignment": {}},
            {"type": "solution", "node_id": "n0", "assignment": {}},
        ],
    }
    result = normalize_backend_result(raw, "A ∨ ¬A")
    assert result["variables"] == {}
    assert result["initial_cnf"] == []
    assert all(event["remaining_cnf"] == [] for event in result["events"])


def test_pure_literal_backend_event_is_normalized_with_residual_cnf():
    raw = {
        "status": "SAT", "assignment": {"B": True},
        "clauses": [
            {"id": "c1", "literals": ["A", "B"]},
            {"id": "c2", "literals": ["!A", "B"]},
        ],
        "events": [
            {"type": "root", "node_id": "n0", "assignment": {}},
            {"type": "pure_literal", "node_id": "n0", "variable": "B", "value": True, "assignment": {"B": True}},
            {"type": "solution", "node_id": "n0", "assignment": {"B": True}},
        ],
    }
    result = normalize_backend_result(raw, "(A | B) & (!A | B)")
    assert result["events"][1]["type"] == "pure_literal"
    assert result["events"][1]["remaining_cnf"] == []


def test_real_backend_handles_lowercase_as_the_same_variable():
    result = solve_expression("a & !A", source="backend", rule_mode="pl_only")
    assert result["status"] == "UNSAT"
    assert result["variables"] == {"A": 1}


def test_unknown_source_and_rule_mode_are_rejected():
    with pytest.raises(ValueError, match="source"):
        solve_expression("A", source="mystery")
    with pytest.raises(ValueError, match="rule mode"):
        solve_expression("A", rule_mode="mystery")

