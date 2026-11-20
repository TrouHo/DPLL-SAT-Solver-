from frontend.mock_solver import EXAMPLES, solve_expression
from frontend.tree_visualizer import build_tree, get_backtrack_annotation, render_tree_svg


def source(step: int, example: str = "SAT + backtrack", rule_mode: str = "up_only") -> str:
    result = solve_expression(EXAMPLES[example], rule_mode=rule_mode)
    return build_tree(result, step).source


def test_events_appear_one_at_a_time_without_future_nodes():
    for step in range(8):
        dot = source(step)
        for future in range(step + 1, 8):
            assert f"evt_{future} [" not in dot
    assert "evt_0 [" in source(0)
    assert "evt_1 [" not in source(0)
    assert "evt_1 [" in source(1)
    assert "evt_2 [" not in source(1)


def test_decision_then_distinct_up_then_distinct_conflict():
    decision = source(1)
    assert 'evt_0 -> evt_1 [label="A = True"' in decision
    assert "<B>Decision</B>" in decision
    assert "Assume A = True" in decision
    assert "n1 (Decision)" not in decision
    assert "Initial formula" in decision
    assert "n0 (Root)" not in decision

    propagation = source(2)
    assert "evt_1 -> evt_2" in propagation
    assert "Unit propagation" in propagation
    assert "B = True" in propagation
    assert "Remain: ⊥" in propagation
    assert "n1.2" not in propagation

    conflict = source(3)
    assert "evt_2 -> evt_3" in conflict
    assert 'label="× Conflict"' in conflict
    assert "xlabel" not in conflict
    assert "fixedsize" not in conflict
    assert "#dc2626" in conflict


def test_backtrack_is_overlay_metadata_not_a_structural_edge():
    result = solve_expression(EXAMPLES["SAT + backtrack"])
    dot = source(4)
    assert "evt_3 -> evt_0" not in dot
    assert "Backtrack" not in dot
    assert "evt_5 [" not in dot
    assert get_backtrack_annotation(result, 4) == {
        "source_id": "evt_3",
        "target_id": "evt_0",
        "side": "left",
        "label": "Backtrack",
    }
    assert get_backtrack_annotation(result, 3) is None
    assert get_backtrack_annotation(result, 5) is None


def test_alternate_branch_and_success_appear_only_when_recorded():
    at_five = source(5)
    assert 'evt_0 -> evt_5 [label="A = False"' in at_five
    assert "evt_6 [" not in at_five
    at_six = source(6)
    assert "Pure literal" not in at_six
    assert "Unit propagation" in at_six
    final = source(7)
    assert "evt_6 -> evt_7" in final
    assert 'label="✓ SAT"' in final
    assert "#16845b" in final
    assert "evt_3 -> evt_0" not in final
    assert "Backtrack" not in final


def test_root_only_unit_chain_is_vertical_without_fake_decisions():
    dot = source(4, "Unit chain")
    assert "evt_0 -> evt_1" in dot
    assert "evt_1 -> evt_2" in dot
    assert "evt_2 -> evt_3" in dot
    assert "evt_3 -> evt_4" in dot
    assert dot.count("Unit propagation") == 3
    assert " = True\"" not in dot


def test_unsat_retains_both_failed_branches_and_final_terminal():
    dot = source(9, "UNSAT")
    assert 'label="A = True"' in dot
    assert 'label="A = False"' in dot
    assert dot.count('label="× Conflict"') == 2
    assert 'label="× UNSAT"' in dot
    assert "evt_3 -> evt_0" not in dot
    assert "evt_7 -> evt_0" not in dot

    result = solve_expression(EXAMPLES["UNSAT"])
    assert get_backtrack_annotation(result, 4)["side"] == "left"
    assert get_backtrack_annotation(result, 8)["side"] == "right"
    assert get_backtrack_annotation(result, 9) is None


def test_pure_literal_gets_its_own_teal_event_node():
    dot = source(2, "Easy SAT", "pl_only")
    assert "Pure literal" in dot
    assert "B = True" in dot
    assert "#0f766e" in dot
    assert "evt_0 -> evt_1" in dot
    assert "evt_1 -> evt_2" in dot
    assert 'label="✓ SAT"' in dot
    assert "(Decision)" not in dot
    assert "n0.1" not in dot


def test_readable_compact_graph_defaults():
    dot = source(7)
    assert "fontsize=12" in dot
    assert "nodesep=0.38" in dot
    assert "ranksep=0.48" in dot
    assert "splines=polyline" in dot
    assert 'margin="0.14,0.10"' in dot


def test_html_labels_escape_special_names_and_render_as_svg():
    result = solve_expression(EXAMPLES["SAT + backtrack"])
    result["variables"] = {"A&B": 1, "X<Y": 2, "C": 3}
    dot = build_tree(result, 0)
    assert "A&amp;B" in dot.source
    assert "X&lt;Y" in dot.source
    svg = dot.pipe(format="svg").decode("utf-8")
    assert "<svg" in svg
    assert "viewBox=" in svg


def test_renderer_returns_vector_svg_and_does_not_mutate_result():
    result = solve_expression(EXAMPLES["SAT + backtrack"])
    before = repr(result)
    svg, annotation = render_tree_svg(result, 4)
    assert "<svg" in svg
    assert "viewBox=" in svg
    assert "image/png" not in svg
    assert annotation["target_id"] == "evt_0"
    assert repr(result) == before

