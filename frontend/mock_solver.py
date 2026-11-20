"""Static educational traces. This module deliberately contains no solver."""

from __future__ import annotations

from copy import deepcopy
import re


BACKTRACK_EXPRESSION = "(¬A ∨ B) ∧ (¬A ∨ ¬B) ∧ (A ∨ C)"
UNSAT_EXPRESSION = "(A ∨ B) ∧ (A ∨ ¬B) ∧ (¬A ∨ B) ∧ (¬A ∨ ¬B)"
UNIT_CHAIN_EXPRESSION = "A ∧ (¬A ∨ B) ∧ (¬B ∨ C)"
EASY_SAT_EXPRESSION = "(A ∨ B) ∧ (¬A ∨ B)"

EXAMPLES = {
    "SAT + backtrack": BACKTRACK_EXPRESSION,
    "UNSAT": UNSAT_EXPRESSION,
    "Unit chain": UNIT_CHAIN_EXPRESSION,
    "Easy SAT": EASY_SAT_EXPRESSION,
}


def _event(seq, kind, node, assignment, cnf, *, parent=None, var=None,
           value=None, from_node=None, reason=None, message=""):
    return {
        "seq": seq, "type": kind, "node_id": node, "parent_id": parent,
        "variable": var, "value": value, "assignment": deepcopy(assignment),
        "remaining_cnf": deepcopy(cnf), "reason_clause": deepcopy(reason),
        "from_node": from_node, "message": message,
    }


def backtrack_fixture():
    initial = [[-1, 2], [-1, -2], [1, 3]]
    return {
        "status": "SAT", "input_expression": BACKTRACK_EXPRESSION,
        "variables": {"A": 1, "B": 2, "C": 3}, "initial_cnf": deepcopy(initial),
        "assignment": {"A": False, "C": True},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start with the input CNF."),
            _event(1, "decision", "n1", {"A": True}, [[2], [-2]], parent="n0", var="A", value=True, message="Try the decision A=True."),
            _event(2, "unit_propagation", "n1", {"A": True, "B": True}, [[]], var="B", value=True, reason=[-1, 2], message="The original clause ¬A ∨ B simplifies to unit B, forcing B=True."),
            _event(3, "conflict", "n1", {"A": True, "B": True}, [[]], reason=[-1, -2], message="The clause ¬A ∨ ¬B becomes empty: this branch conflicts."),
            _event(4, "backtrack", "n0", {}, initial, from_node="n1", message="Undo A=True and B=True, then return to the root."),
            _event(5, "decision", "n2", {"A": False}, [[3]], parent="n0", var="A", value=False, message="Try the alternative decision A=False."),
            _event(6, "unit_propagation", "n2", {"A": False, "C": True}, [], var="C", value=True, reason=[1, 3], message="The original clause A ∨ C simplifies to unit C, forcing C=True."),
            _event(7, "solution", "n2", {"A": False, "C": True}, [], message="All clauses are satisfied; a (possibly partial) model is found."),
        ],
    }


def unsat_fixture():
    initial = [[1, 2], [1, -2], [-1, 2], [-1, -2]]
    return {
        "status": "UNSAT", "input_expression": UNSAT_EXPRESSION,
        "variables": {"A": 1, "B": 2}, "initial_cnf": deepcopy(initial), "assignment": {},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start with the input CNF."),
            _event(1, "decision", "n1", {"A": True}, [[2], [-2]], parent="n0", var="A", value=True, message="Try the decision A=True."),
            _event(2, "unit_propagation", "n1", {"A": True, "B": True}, [[]], var="B", value=True, reason=[-1, 2], message="Unit B forces B=True; the opposite unit clause becomes empty."),
            _event(3, "conflict", "n1", {"A": True, "B": True}, [[]], reason=[-1, -2], message="An empty clause proves this branch impossible."),
            _event(4, "backtrack", "n0", {}, initial, from_node="n1", message="Undo the failed A=True branch."),
            _event(5, "decision", "n2", {"A": False}, [[2], [-2]], parent="n0", var="A", value=False, message="Try the alternative decision A=False."),
            _event(6, "unit_propagation", "n2", {"A": False, "B": True}, [[]], var="B", value=True, reason=[1, 2], message="Unit B forces B=True; the opposite unit clause becomes empty."),
            _event(7, "conflict", "n2", {"A": False, "B": True}, [[]], reason=[1, -2], message="An empty clause proves the second branch impossible."),
            _event(8, "backtrack", "n0", {}, initial, from_node="n2", message="Undo the failed A=False branch; both alternatives are exhausted."),
            _event(9, "unsat", "n0", {}, initial, message="Every decision branch failed, so the formula is UNSAT."),
        ],
    }


def unit_chain_fixture():
    initial = [[1], [-1, 2], [-2, 3]]
    return {
        "status": "SAT", "input_expression": UNIT_CHAIN_EXPRESSION,
        "variables": {"A": 1, "B": 2, "C": 3}, "initial_cnf": deepcopy(initial),
        "assignment": {"A": True, "B": True, "C": True},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start with the input CNF."),
            _event(1, "unit_propagation", "n0", {"A": True}, [[2], [-2, 3]], var="A", value=True, reason=[1], message="Unit clause A forces A=True."),
            _event(2, "unit_propagation", "n0", {"A": True, "B": True}, [[3]], var="B", value=True, reason=[-1, 2], message="The clause ¬A ∨ B is now unit, forcing B=True."),
            _event(3, "unit_propagation", "n0", {"A": True, "B": True, "C": True}, [], var="C", value=True, reason=[-2, 3], message="The clause ¬B ∨ C is now unit, forcing C=True."),
            _event(4, "solution", "n0", {"A": True, "B": True, "C": True}, [], message="All clauses are satisfied without a decision."),
        ],
    }


def easy_sat_fixture():
    initial = [[1, 2], [-1, 2]]
    return {
        "status": "SAT", "input_expression": EASY_SAT_EXPRESSION,
        "variables": {"A": 1, "B": 2}, "initial_cnf": deepcopy(initial),
        "assignment": {"A": True, "B": True},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start with the input CNF."),
            _event(1, "decision", "n1", {"A": True}, [[2]], parent="n0", var="A", value=True, message="Try the decision A=True."),
            _event(2, "unit_propagation", "n1", {"A": True, "B": True}, [], var="B", value=True, reason=[-1, 2], message="The remaining unit clause forces B=True."),
            _event(3, "solution", "n1", {"A": True, "B": True}, [], message="All clauses are satisfied without backtracking."),
        ],
    }


def pure_literal_fixture():
    """PL-only trace for the easy SAT formula where B is pure positive."""
    initial = [[1, 2], [-1, 2]]
    return {
        "status": "SAT", "input_expression": EASY_SAT_EXPRESSION,
        "variables": {"A": 1, "B": 2}, "initial_cnf": deepcopy(initial),
        "assignment": {"B": True},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start with the input CNF."),
            _event(
                1, "pure_literal", "n0", {"B": True}, [], var="B", value=True,
                message="B occurs only positively, so pure-literal elimination sets B=True.",
            ),
            _event(
                2, "solution", "n0", {"B": True}, [],
                message="All clauses are satisfied after pure-literal elimination.",
            ),
        ],
    }


def pl_backtrack_fixture():
    """Recorded PL-only trace for the SAT + backtrack input."""
    initial = [[-1, 2], [-1, -2], [1, 3]]
    return {
        "status": "SAT", "input_expression": BACKTRACK_EXPRESSION,
        "variables": {"A": 1, "B": 2, "C": 3}, "initial_cnf": deepcopy(initial),
        "assignment": {"C": True, "A": False},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start the DPLL search."),
            _event(1, "pure_literal", "n0", {"C": True}, [[-1, 2], [-1, -2]],
                   var="C", value=True, message="C is pure positive, so set C=True."),
            _event(2, "pure_literal", "n0", {"C": True, "A": False}, [],
                   var="A", value=False, message="A is now pure negative, so set A=False."),
            _event(3, "solution", "n0", {"C": True, "A": False}, [],
                   message="All clauses are satisfied."),
        ],
    }


def pl_unit_chain_fixture():
    """Recorded PL-only trace for the unit-chain input; no UP is performed."""
    initial = [[1], [-1, 2], [-2, 3]]
    return {
        "status": "SAT", "input_expression": UNIT_CHAIN_EXPRESSION,
        "variables": {"A": 1, "B": 2, "C": 3}, "initial_cnf": deepcopy(initial),
        "assignment": {"C": True, "B": True, "A": True},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start the DPLL search."),
            _event(1, "pure_literal", "n0", {"C": True}, [[1], [-1, 2]],
                   var="C", value=True, message="C is pure positive, so set C=True."),
            _event(2, "pure_literal", "n0", {"C": True, "B": True}, [[1]],
                   var="B", value=True, message="B is now pure positive, so set B=True."),
            _event(3, "pure_literal", "n0", {"C": True, "B": True, "A": True}, [],
                   var="A", value=True, message="A is now pure positive, so set A=True."),
            _event(4, "solution", "n0", {"C": True, "B": True, "A": True}, [],
                   message="All clauses are satisfied."),
        ],
    }


def pl_unsat_fixture():
    """Recorded complete PL-only DFS trace when no literal is pure."""
    initial = [[1, 2], [1, -2], [-1, 2], [-1, -2]]
    return {
        "status": "UNSAT", "input_expression": UNSAT_EXPRESSION,
        "variables": {"A": 1, "B": 2}, "initial_cnf": deepcopy(initial), "assignment": {},
        "events": [
            _event(0, "start", "n0", {}, initial, message="Start the DPLL search."),
            _event(1, "decision", "n1", {"A": True}, [[2], [-2]], parent="n0", var="A", value=True, message="Decide A=True."),
            _event(2, "decision", "n2", {"A": True, "B": True}, [[]], parent="n1", var="B", value=True, message="Decide B=True."),
            _event(3, "conflict", "n2", {"A": True, "B": True}, [[]], reason=[-1, -2], message="An empty clause creates a conflict."),
            _event(4, "backtrack", "n1", {"A": True}, [[2], [-2]], from_node="n2", message="Backtrack to A=True."),
            _event(5, "decision", "n3", {"A": True, "B": False}, [[]], parent="n1", var="B", value=False, message="Decide B=False."),
            _event(6, "conflict", "n3", {"A": True, "B": False}, [[]], reason=[-1, 2], message="An empty clause creates a conflict."),
            _event(7, "backtrack", "n1", {"A": True}, [[2], [-2]], from_node="n3", message="Backtrack to A=True."),
            _event(8, "backtrack", "n0", {}, initial, from_node="n1", message="Backtrack to the root."),
            _event(9, "decision", "n4", {"A": False}, [[2], [-2]], parent="n0", var="A", value=False, message="Decide A=False."),
            _event(10, "decision", "n5", {"A": False, "B": True}, [[]], parent="n4", var="B", value=True, message="Decide B=True."),
            _event(11, "conflict", "n5", {"A": False, "B": True}, [[]], reason=[1, -2], message="An empty clause creates a conflict."),
            _event(12, "backtrack", "n4", {"A": False}, [[2], [-2]], from_node="n5", message="Backtrack to A=False."),
            _event(13, "decision", "n6", {"A": False, "B": False}, [[]], parent="n4", var="B", value=False, message="Decide B=False."),
            _event(14, "conflict", "n6", {"A": False, "B": False}, [[]], reason=[1, 2], message="An empty clause creates a conflict."),
            _event(15, "backtrack", "n4", {"A": False}, [[2], [-2]], from_node="n6", message="Backtrack to A=False."),
            _event(16, "backtrack", "n0", {}, initial, from_node="n4", message="Backtrack to the root."),
            _event(17, "unsat", "n0", {}, initial, message="Every branch conflicts, so the formula is UNSAT."),
        ],
    }


def _normalize(text: str) -> str:
    normalized = text.strip().replace("<->", "↔").replace("->", "→")
    normalized = normalized.replace("!", "¬").replace("&", "∧").replace("|", "∨")
    return re.sub(r"\s+", "", normalized)


_FIXTURES = {
    _normalize(BACKTRACK_EXPRESSION): backtrack_fixture,
    _normalize(UNSAT_EXPRESSION): unsat_fixture,
    _normalize(UNIT_CHAIN_EXPRESSION): unit_chain_fixture,
    _normalize(EASY_SAT_EXPRESSION): easy_sat_fixture,
}

_PL_FIXTURES = {
    _normalize(BACKTRACK_EXPRESSION): pl_backtrack_fixture,
    _normalize(UNSAT_EXPRESSION): pl_unsat_fixture,
    _normalize(UNIT_CHAIN_EXPRESSION): pl_unit_chain_fixture,
    _normalize(EASY_SAT_EXPRESSION): pure_literal_fixture,
}


def solve_expression(text: str, rule_mode: str = "up_only") -> dict:
    """Return a matching recorded trace for the requested educational mode."""
    if rule_mode not in {"up_only", "pl_only"}:
        raise ValueError(f"Unknown rule mode: {rule_mode}")
    normalized = _normalize(text)
    factory = _FIXTURES.get(normalized)
    if factory is None:
        raise ValueError("Mock mode supports only the four predefined examples")
    result = _PL_FIXTURES[normalized]() if rule_mode == "pl_only" else factory()
    result["input_expression"] = text
    return deepcopy(result)

