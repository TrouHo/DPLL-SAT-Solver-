"""Types and runtime validation for the frozen frontend/backend trace contract."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


EventType = Literal[
    "start", "decision", "unit_propagation", "pure_literal",
    "conflict", "backtrack", "solution", "unsat",
]


class Event(TypedDict, total=False):
    seq: int
    type: EventType
    node_id: str
    parent_id: str | None
    variable: str | None
    value: bool | None
    assignment: dict[str, bool]
    remaining_cnf: list[list[int]]
    reason_clause: list[int] | None
    from_node: str | None
    message: str


class SolveResult(TypedDict):
    status: Literal["SAT", "UNSAT"]
    input_expression: str
    variables: dict[str, int]
    initial_cnf: list[list[int]]
    assignment: dict[str, bool]
    events: list[Event]


ALLOWED_EVENT_TYPES = {
    "start", "decision", "unit_propagation", "pure_literal",
    "conflict", "backtrack", "solution", "unsat",
}


def _validate_cnf(cnf: Any, variables: dict[str, int], location: str) -> None:
    if not isinstance(cnf, list) or any(not isinstance(clause, list) for clause in cnf):
        raise ValueError(f"{location} must be a list of clause lists")
    known_ids = set(variables.values())
    for clause_index, clause in enumerate(cnf):
        for lit in clause:
            if isinstance(lit, bool) or not isinstance(lit, int) or lit == 0:
                raise ValueError(f"{location}[{clause_index}] contains an invalid literal")
            if abs(lit) not in known_ids:
                raise ValueError(f"{location}[{clause_index}] contains unknown variable ID {abs(lit)}")


def _validate_assignment(value: Any, variables: dict[str, int], location: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be a dictionary")
    for name, assigned in value.items():
        if name not in variables:
            raise ValueError(f"{location} contains unknown variable {name!r}")
        if not isinstance(assigned, bool):
            raise ValueError(f"{location}[{name!r}] must be bool")


def _model_satisfies(cnf: list[list[int]], variables: dict[str, int], model: dict[str, bool]) -> bool:
    names_by_id = {identifier: name for name, identifier in variables.items()}
    for clause in cnf:
        if not any(
            names_by_id[abs(lit)] in model
            and model[names_by_id[abs(lit)]] == (lit > 0)
            for lit in clause
        ):
            return False
    return True


def validate_result(result: Any) -> None:
    """Raise ``ValueError`` when a solver response violates the trace contract."""
    if not isinstance(result, dict):
        raise ValueError("Solver result must be a dictionary")
    required = {"status", "input_expression", "variables", "initial_cnf", "assignment", "events"}
    missing = required - result.keys()
    if missing:
        raise ValueError(f"Solver result is missing: {', '.join(sorted(missing))}")
    if result["status"] not in {"SAT", "UNSAT"}:
        raise ValueError("status must be SAT or UNSAT")
    if not isinstance(result["input_expression"], str):
        raise ValueError("input_expression must be a string")
    variables = result["variables"]
    if not isinstance(variables, dict):
        raise ValueError("variables must be a dictionary")
    if not variables and result["initial_cnf"] != []:
        raise ValueError("variables may be empty only when initial_cnf is empty")
    if any(not isinstance(name, str) or not name for name in variables):
        raise ValueError("variable names must be non-empty strings")
    identifiers = list(variables.values())
    if any(isinstance(x, bool) or not isinstance(x, int) or x <= 0 for x in identifiers):
        raise ValueError("variable IDs must be positive integers")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("variable IDs must be unique")

    _validate_cnf(result["initial_cnf"], variables, "initial_cnf")
    _validate_assignment(result["assignment"], variables, "assignment")
    events = result["events"]
    if not isinstance(events, list) or not events:
        raise ValueError("events must be a non-empty list")
    if [event.get("seq") if isinstance(event, dict) else None for event in events] != list(range(len(events))):
        raise ValueError("event seq values must be contiguous from zero")
    if not isinstance(events[0], dict) or events[0].get("type") != "start":
        raise ValueError("the first event must be start")

    known_nodes: set[str] = set()
    for index, event in enumerate(events):
        location = f"events[{index}]"
        event_required = {
            "seq", "type", "node_id", "parent_id", "variable", "value",
            "assignment", "remaining_cnf", "reason_clause", "from_node", "message",
        }
        missing_event = event_required - event.keys()
        if missing_event:
            raise ValueError(f"{location} is missing: {', '.join(sorted(missing_event))}")
        kind = event["type"]
        if kind not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"{location}.type is invalid")
        node_id = event["node_id"]
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"{location}.node_id must be a non-empty string")
        if kind == "start":
            if known_nodes:
                raise ValueError("start may appear only once")
            known_nodes.add(node_id)
        elif kind == "decision":
            if node_id in known_nodes:
                raise ValueError(f"{location} reuses decision node {node_id}")
            if event["parent_id"] not in known_nodes:
                raise ValueError(f"{location} has an unknown parent")
            known_nodes.add(node_id)
        elif node_id not in known_nodes:
            raise ValueError(f"{location} references unknown node {node_id}")
        if kind == "backtrack":
            if event["from_node"] not in known_nodes:
                raise ValueError(f"{location}.from_node references an unknown node")
            if event["from_node"] == node_id:
                raise ValueError(f"{location} must resume a different node")
        if kind in {"decision", "unit_propagation", "pure_literal"}:
            if event["variable"] not in variables or not isinstance(event["value"], bool):
                raise ValueError(f"{location} needs a known variable and boolean value")
        _validate_assignment(event["assignment"], variables, f"{location}.assignment")
        _validate_cnf(event["remaining_cnf"], variables, f"{location}.remaining_cnf")
        reason = event["reason_clause"]
        if reason is not None:
            _validate_cnf([reason], variables, f"{location}.reason_clause")
        if not isinstance(event["message"], str):
            raise ValueError(f"{location}.message must be a string")
        if kind == "conflict" and not any(not clause for clause in event["remaining_cnf"]):
            raise ValueError("a conflict event must contain an empty clause")
        if kind == "solution" and event["remaining_cnf"] != []:
            raise ValueError("a solution event must have no remaining clauses")

    last = events[-1]
    if result["status"] == "SAT":
        if last["type"] != "solution" or last["remaining_cnf"] != []:
            raise ValueError("SAT traces must end with a solution and no remaining clauses")
        if result["assignment"] != last["assignment"]:
            raise ValueError("final SAT assignment must equal the solution snapshot")
        if not _model_satisfies(result["initial_cnf"], variables, result["assignment"]):
            raise ValueError("final assignment does not satisfy every original clause")
    else:
        if last["type"] != "unsat":
            raise ValueError("UNSAT traces must end with an unsat event")
        if result["assignment"] != {}:
            raise ValueError("UNSAT results must not contain a model")

