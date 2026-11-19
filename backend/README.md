# Backend: DPLL SAT solver

Python 3, no external packages.

## Use

```python
from dpllsat import solve_request

response = solve_request({"expression": "(!A | B) & (!A | !B) & (A | C)", "trace": True})
```

From the `backend` folder:

```bash
python -m dpllsat.service "(A -> B) & !B"
```

```bash
python -m unittest
```

```bash
python make_examples.py
```

`examples/` holds sample request/response pairs for the frontend to use as mock data.

## Input syntax

Case-insensitive, spaces ignored. Any propositional formula is accepted and
converted to CNF before solving.

| Meaning | Symbol |
|---|---|
| not | `!` |
| and | `&` |
| or | `\|` |
| implies | `->` |
| if and only if | `<->` |

Precedence, strongest first: `!`, `&`, `|`, `->`, `<->`.

## Response

- `status`: `"SAT"`, `"UNSAT"` or `"ERROR"`
- `assignment`: variable name to boolean, or `null`. It may be partial.
- `cnf`: the formula after conversion to CNF, as text
- `clauses`: `[{id, literals}]`; `reason_clause` in events points to these ids
- `events`: the ordered search trace (empty when `"trace": false`)
- `error`: `{code, message, position?}`, only when `status` is `"ERROR"`

Error codes: `EMPTY_INPUT`, `SYNTAX_ERROR`, `TOO_LARGE`, `INVALID_REQUEST`, `INTERNAL_ERROR`.

Limits: 1000 characters, 20 variables, 50 clauses, 2000 events.

## Files

| File | Role |
|---|---|
| `dpllsat/parser.py` | text to syntax tree, syntax errors |
| `dpllsat/cnf.py` | syntax tree to CNF, variable numbering |
| `dpllsat/dpll.py` | the DPLL algorithm |
| `dpllsat/trace.py` | records the events |
| `dpllsat/service.py` | `solve_request`, the single entry point |
| `dpllsat/errors.py` | error codes and limits |
