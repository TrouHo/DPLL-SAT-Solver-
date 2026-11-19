"""The single function the frontend (or a future web API) calls.

    solve_request({"expression": "(!A | B) & (A | C)", "trace": True})

It never raises: every problem is returned as status "ERROR".
It does not depend on any web framework.

Command line:  python -m dpllsat.service "(!A | B) & (A | C)"
"""

import json
import sys

from . import cnf, dpll, parser
from .errors import (INTERNAL_ERROR, INVALID_REQUEST, MAX_CLAUSES, MAX_VARIABLES,
                     TOO_LARGE, SolverError)
from .trace import Tracer


def _error(code, message, position=None):
    error = {"code": code, "message": message}
    if position is not None:
        error["position"] = position
    return {"status": "ERROR", "assignment": None, "cnf": None,
            "clauses": [], "events": [], "error": error}


def _solve(payload):
    if not isinstance(payload, dict):
        raise SolverError(INVALID_REQUEST, "The request must be a JSON object.")
    expression = payload.get("expression")
    if not isinstance(expression, str):
        raise SolverError(INVALID_REQUEST, "The field 'expression' must be a string.")
    with_trace = payload.get("trace", True)
    if not isinstance(with_trace, bool):
        raise SolverError(INVALID_REQUEST, "The field 'trace' must be true or false.")

    tree = parser.parse(expression)
    if len(parser.variables(tree)) > MAX_VARIABLES:
        raise SolverError(TOO_LARGE, f"The expression uses more than {MAX_VARIABLES} variables.")

    clauses = cnf.to_cnf(tree)
    if len(clauses) > MAX_CLAUSES:
        raise SolverError(TOO_LARGE, f"The CNF form has more than {MAX_CLAUSES} clauses.")

    encoded, names = cnf.encode(clauses)
    tracer = Tracer(names, enabled=with_trace)
    result = dpll.solve(encoded, tracer)

    return {
        "status": "SAT" if result is not None else "UNSAT",
        "assignment": None if result is None
        else {names[variable]: value for variable, value in result.items()},
        "cnf": cnf.cnf_text(clauses),
        "clauses": [{"id": f"c{index}", "literals": [cnf.literal_text(lit) for lit in clause]}
                    for index, clause in enumerate(clauses, 1)],
        "events": tracer.events,
    }


def solve_request(payload):
    """Solve one request and return a JSON-ready dict."""
    try:
        return _solve(payload)
    except SolverError as error:
        return _error(error.code, error.message, error.position)
    except RecursionError:
        return _error(TOO_LARGE, "The expression is nested too deeply.")
    except Exception as error:  # never crash the caller
        return _error(INTERNAL_ERROR, f"Unexpected error: {error}")


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "(!A | B) & (!A | !B) & (A | C)"
    print(json.dumps(solve_request({"expression": text, "trace": True}), indent=2))
