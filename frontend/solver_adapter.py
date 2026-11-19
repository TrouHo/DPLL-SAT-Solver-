"""Single in-process boundary for recorded mocks and the optional Python backend."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from .trace_schema import ALLOWED_EVENT_TYPES, validate_result
except ImportError:  # Streamlit executes frontend/app.py as a script.
    from trace_schema import ALLOWED_EVENT_TYPES, validate_result


def normalize_expression_for_backend(expression: str) -> str:
    """Translate visible Unicode operators without changing the editor text."""
    return (
        expression.replace("↔", "<->").replace("→", "->")
        .replace("¬", "!").replace("∧", "&").replace("∨", "|")
    )


def simplify_cnf(
    initial_cnf: list[list[int]], assignment: dict[str, bool], variables: dict[str, int]
) -> list[list[int]]:
    """Return a new residual CNF; ``[]`` is true and an empty clause is false."""
    names_by_id = {identifier: name for name, identifier in variables.items()}
    residual: list[list[int]] = []
    for clause in initial_cnf:
        remaining: list[int] = []
        satisfied = False
        for literal in clause:
            name = names_by_id[abs(literal)]
            value = assignment.get(name)
            if value is None:
                remaining.append(literal)
            elif value == (literal > 0):
                satisfied = True
                break
        if not satisfied:
            residual.append(remaining)
    return residual


def _literal_name(literal: Any) -> tuple[str, bool]:
    if not isinstance(literal, str):
        raise ValueError(f"Unsupported backend literal: {literal!r}")
    token = literal.strip()
    negative = token.startswith(("!", "¬", "~", "-"))
    name = token[1:] if negative else token
    if not name:
        raise ValueError(f"Unsupported backend literal: {literal!r}")
    return name, negative


def _normalize_clauses(raw: dict) -> tuple[dict[str, int], list[list[int]], dict[str, list[int]]]:
    clauses = raw.get("clauses")
    if not isinstance(clauses, list):
        raise ValueError("Backend clauses must be a list")

    names: set[str] = set()
    for clause in clauses:
        if not isinstance(clause, dict) or not isinstance(clause.get("literals"), list):
            raise ValueError("Each backend clause must contain a literals list")
        for literal in clause["literals"]:
            if isinstance(literal, str):
                names.add(_literal_name(literal)[0])
    for assignment in [raw.get("assignment"), *(e.get("assignment") for e in raw.get("events", []))]:
        if isinstance(assignment, dict):
            names.update(assignment)

    raw_variables = raw.get("variables")
    if isinstance(raw_variables, dict) and raw_variables:
        variables = {str(name): int(identifier) for name, identifier in raw_variables.items()}
    else:
        variables = {name: index + 1 for index, name in enumerate(sorted(names))}
    if not variables and clauses:
        raise ValueError("Backend response does not identify variables for its clauses")

    clause_lookup: dict[str, list[int]] = {}
    initial: list[list[int]] = []
    for index, clause in enumerate(clauses):
        converted: list[int] = []
        for literal in clause.get("literals", []):
            if isinstance(literal, int) and not isinstance(literal, bool):
                converted.append(literal)
            elif isinstance(literal, str):
                name, negative = _literal_name(literal)
                converted.append(-variables[name] if negative else variables[name])
            else:
                raise ValueError(f"Unsupported backend literal: {literal!r}")
        clause_id = str(clause.get("id", f"c{index + 1}"))
        clause_lookup[clause_id] = converted
        initial.append(converted)
    return variables, initial, clause_lookup


def _generated_message(kind: str, variable: str | None, value: bool | None) -> str:
    messages = {
        "start": "Start the DPLL search.",
        "conflict": "An empty clause creates a conflict.",
        "backtrack": "Backtrack to the recorded ancestor.",
        "solution": "All clauses are satisfied.",
        "unsat": "All branches are exhausted; the formula is UNSAT.",
    }
    if kind in messages:
        return messages[kind]
    rule = {"decision": "Decide", "unit_propagation": "Unit propagation forces", "pure_literal": "Pure-literal elimination sets"}[kind]
    return f"{rule} {variable}={value}."


def normalize_backend_result(raw: dict, input_expression: str) -> dict:
    """Convert the backend service response into the shared replay schema."""
    if not isinstance(raw, dict):
        raise ValueError("Backend response must be a dictionary")
    status = raw.get("status")
    if status == "ERROR":
        error = raw.get("error")
        if isinstance(error, dict):
            code = error.get("code")
            message = error.get("message") or "Backend rejected the formula"
            position = error.get("position")
            prefix = f"{code}: " if code else ""
            suffix = f" (parser position {position})" if position is not None else ""
            raise RuntimeError(f"{prefix}{message}{suffix}")
        raise RuntimeError(str(raw.get("message") or error or "Backend rejected the formula"))
    if status not in {"SAT", "UNSAT"}:
        raise ValueError("Backend response status must be SAT, UNSAT, or ERROR")

    variables, initial_cnf, clause_lookup = _normalize_clauses(raw)
    normalized_events: list[dict] = []
    type_aliases = {"root": "start", "sat": "solution"}
    for seq, source_event in enumerate(raw.get("events", [])):
        kind = type_aliases.get(source_event.get("type"), source_event.get("type"))
        if kind not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"Unsupported backend event type: {kind!r}")
        assignment = {str(name): bool(value) for name, value in (source_event.get("assignment") or {}).items()}
        reason = source_event.get("reason_clause")
        if isinstance(reason, str):
            reason = deepcopy(clause_lookup.get(reason))
        elif isinstance(reason, list):
            reason = deepcopy(reason)
        else:
            reason = None
        variable = source_event.get("variable")
        value = source_event.get("value")
        normalized_events.append({
            "seq": seq,
            "type": kind,
            "node_id": str(source_event.get("node_id", "n0")),
            "parent_id": source_event.get("parent_id") if kind == "decision" else None,
            "variable": variable,
            "value": value,
            "assignment": assignment,
            "remaining_cnf": simplify_cnf(initial_cnf, assignment, variables),
            "reason_clause": reason,
            "from_node": source_event.get("from_node") if kind == "backtrack" else None,
            "message": str(source_event.get("message") or _generated_message(kind, variable, value)),
        })
    if not normalized_events:
        raise ValueError("Backend response contains no trace events")

    final_assignment = raw.get("assignment") or {}
    result = {
        "status": status,
        "input_expression": input_expression,
        "variables": variables,
        "initial_cnf": initial_cnf,
        "assignment": {} if status == "UNSAT" else {str(k): bool(v) for k, v in final_assignment.items()},
        "events": normalized_events,
    }
    validate_result(result)
    return result


def solve_expression(
    expression: str,
    mode: str | None = None,
    *,
    source: str | None = None,
    rule_mode: str = "up_only",
) -> dict:
    """Solve through the selected source without ever falling back silently."""
    selected_source = source or mode or "mock"
    if selected_source == "real":
        selected_source = "backend"
    if selected_source not in {"mock", "backend"}:
        raise ValueError(f"Unknown solver source: {selected_source}")
    if rule_mode not in {"up_only", "pl_only"}:
        raise ValueError(f"Unknown rule mode: {rule_mode}")

    if selected_source == "mock":
        try:
            from .mock_solver import solve_expression as mock_solve
        except ImportError:
            from mock_solver import solve_expression as mock_solve
        result = mock_solve(expression, rule_mode=rule_mode)
        validate_result(result)
        return result

    try:
        from backend.dpllsat.service import solve_request
    except (ImportError, ModuleNotFoundError) as exc:
        raise RuntimeError(
            "Backend is not integrated. Expected backend.dpllsat.service.solve_request."
        ) from exc
    raw = solve_request({
        "expression": normalize_expression_for_backend(expression),
        "trace": True,
        "rule_mode": rule_mode,
    })
    return normalize_backend_result(raw, expression)

