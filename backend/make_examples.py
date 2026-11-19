"""Write sample responses to examples/ for the frontend to use as mock data.

Run from the backend folder:  python make_examples.py
"""

import json
from pathlib import Path

from dpllsat import solve_request

EXAMPLES = {
    "sat_with_backtrack": "(!A | B) & (!A | !B) & (A | C)",   # the contract example
    "sat_unit_only": "A & (!A | B)",
    "unsat_direct": "A & !A",
    "unsat_both_branches": "(A | B) & (A | !B) & (!A | B) & (!A | !B)",
    "sat_deeper_tree": "(A | B) & (!A | C) & (!B | !C) & (!A | !C | D) & (B | D)",
    "sat_from_non_cnf": "(A -> B) & (B -> C) & !(A <-> C)",
    "sat_always_true": "A | !A",
    "error_syntax": "(A | B",
    "error_empty": "",
}


def main():
    folder = Path(__file__).parent / "examples"
    folder.mkdir(exist_ok=True)
    for name, expression in EXAMPLES.items():
        request = {"expression": expression, "trace": True}
        content = {"request": request, "response": solve_request(request)}
        (folder / f"{name}.json").write_text(json.dumps(content, indent=2), encoding="utf-8")
        print(f"{name}: {content['response']['status']}, {len(content['response']['events'])} events")


if __name__ == "__main__":
    main()
