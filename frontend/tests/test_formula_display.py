from frontend.formula_display import assignment_to_text, clause_to_text, cnf_to_text, literal_to_text


VARIABLES = {"A": 1, "B": 2}


def test_literal_and_clause_display():
    assert literal_to_text(-1, VARIABLES) == "¬A"
    assert clause_to_text([1, -2], VARIABLES) == "(A ∨ ¬B)"


def test_true_and_false_cnf_states_are_distinct():
    assert cnf_to_text([], VARIABLES) == "⊤ (all clauses satisfied)"
    assert cnf_to_text([[]], VARIABLES) == "⊥  [CONFLICT]"


def test_partial_assignment_displays_unassigned_variables():
    assert assignment_to_text({"A": False}, VARIABLES) == "{A: False, B: —}"

