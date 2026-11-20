"""Small, framework-independent helpers for displaying CNF states."""

from __future__ import annotations


def literal_to_text(lit: int, variables: dict[str, int]) -> str:
    """Convert a signed integer literal to its propositional notation."""
    names_by_id = {identifier: name for name, identifier in variables.items()}
    symbol = names_by_id[abs(lit)]
    return f"¬{symbol}" if lit < 0 else symbol


def clause_to_text(clause: list[int], variables: dict[str, int]) -> str:
    """Render one clause, using bottom for an empty clause."""
    if not clause:
        return "⊥"
    return "(" + " ∨ ".join(literal_to_text(lit, variables) for lit in clause) + ")"


def cnf_to_text(cnf: list[list[int]], variables: dict[str, int]) -> str:
    """Render a CNF while keeping true and contradiction states distinct."""
    if not cnf:
        return "⊤ (all clauses satisfied)"
    text = " ∧ ".join(clause_to_text(clause, variables) for clause in cnf)
    return f"{text}  [CONFLICT]" if any(not clause for clause in cnf) else text


def assignment_to_text(
    assignment: dict[str, bool], variables: dict[str, int], *, show_unassigned: bool = True
) -> str:
    """Render assignments in stable variable-ID order."""
    entries: list[str] = []
    for name in sorted(variables, key=variables.get):
        if name in assignment:
            value = "True" if assignment[name] else "False"
        elif show_unassigned:
            value = "—"
        else:
            continue
        entries.append(f"{name}: {value}")
    return "{" + ", ".join(entries) + "}"

