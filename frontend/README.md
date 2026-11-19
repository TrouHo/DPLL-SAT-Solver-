# DPLL SAT Solver frontend

This folder contains a Streamlit interface for replaying educational DPLL traces. Application and solver integration code remain Python-only; the caret-aware editor uses a small inline Streamlit Components v2 JavaScript handler embedded in `formula_editor.py` and requires no Node/React build. The frontend does **not** implement a general parser, CNF converter, or DPLL solver. Mock source recognizes the approved deterministic formula/rule combinations and refuses unsupported combinations explicitly.

## Run locally

From the repository root:

```powershell
python -m pip install -r frontend/requirements.txt
python -m pytest frontend/tests -q
python -m streamlit run frontend/app.py
```

The Python `graphviz` package and the Graphviz `dot` executable produce a fresh SVG for each replay step. A small inline Streamlit Components v2 viewer keeps that SVG as vector DOM, so labels and edges remain sharp while zooming. If local SVG generation fails, the app reports the error and uses Streamlit's browser-side Graphviz renderer as a vector fallback.

## Input and controls

The predefined mock formulas are propositional CNF. Unicode `¬`, `∧`, and `∨` are shown in the examples; ASCII aliases `!`, `&`, and `|` also match them. The editor also provides `→` and `↔` for a backend parser. Quantifiers are not supported.

The integrated editor accepts up to 1000 characters and supports typing, paste, selections, parentheses, and logical characters. Its keypad inserts at the current caret or replaces the selected text, then returns focus to the editor so typing can continue immediately. Loading an example, Clear, and Reset synchronize through an editor revision without overwriting ordinary typing or moving the caret. **Solve** is the sole action that invokes the adapter. Navigation, seeking, and playback reuse the stored response and never invoke the solver again.

Mock cases:

- SAT with a failed branch and backtracking
- UNSAT after two failed decision branches
- SAT through a root-level unit-propagation chain
- SAT via one decision and unit propagation, without backtracking

The web interface always runs the real in-process Python Backend; there is no solver-source selector. Mock remains available through the adapter and automated tests as an optional deterministic testing source. The **Rule mode** selector chooses between **Unit propagation** (`up_only`), which never applies pure-literal elimination, and **Pure literal** (`pl_only`), which never applies unit propagation but still uses decisions and backtracking when PL cannot finish the search. All four predefined formulas retain separate static mock traces for both modes. Changing the rule invalidates the previous result.

The graph is an expanded event tree: start, decision, unit-propagation, pure-literal, conflict, and terminal events each have their own visual node. Terminal states use auto-sized `× Conflict`, `× UNSAT`, and `✓ SAT` pills, avoiding external-label collisions. Backtracking is not part of structural DOT: only on the current backtrack step, the SVG viewer draws a dashed orange reverse route in the outside gutter from the failed terminal to the recorded ancestor. It disappears on the next step. Decision values appear on branch edges. Red marks failed branches, green marks SAT, blue marks the active node, purple marks unit propagation, and teal marks pure-literal elimination. The viewer preserves a natural SVG size and scrolls when a future diagram exceeds its viewport; **Expand** provides additional room.

An empty remaining CNF (`[]`) is rendered as `⊤`; a CNF containing an empty clause (`[[]]`) is rendered as `⊥`. These states are never treated as interchangeable.

## Backend integration contract

Backend source imports this function without falling back to mock data:

```python
# backend/dpllsat/service.py (owned by the backend developer)
def solve_request(request: dict) -> dict:
    ...
```

The adapter converts visible Unicode operators to backend ASCII without changing editor text, then calls `solve_request({"expression": ..., "trace": True, "rule_mode": ...})` in process. It derives remaining CNF from assignment snapshots, normalizes event names, resolves reason-clause IDs, and validates the result against `frontend.trace_schema.SolveResult`. Structured backend errors are shown with their code, message and parser position when supplied. Valid tautologies with `clauses=[]`, `variables={}` and an empty model are accepted.

## Accessibility and verification

The formula field, symbol toolbar, vector tree, toggles, and controls expose labels for keyboard and assistive-technology use. Keypad actions preserve focus, insert at the caret, and replace selections. The page uses plain text labels rather than decorative emoji; logical keypad symbols, graph arrows, and terminal `×`/`✓` marks remain because they carry meaning. Run `python -m pytest frontend/tests -q` for the schema, fixture, adapter, editor, and graph tests. Visual checks should include 1600×900, 1440×900, browser zoom, and a narrow viewport, plus every mock replay through its final step.

