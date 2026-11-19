import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest

from frontend.solver_adapter import solve_expression
from frontend.trace_schema import validate_result
from frontend.tree_visualizer import build_tree, render_tree_svg


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def test_streamlit_has_no_source_selector_and_always_uses_backend():
    app = AppTest.from_file(APP_PATH, default_timeout=15).run()

    assert not app.exception
    assert len(app.segmented_control) == 1
    assert app.segmented_control[0].label == "Rule mode"
    assert app.session_state["selected_source"] == "backend"


def test_existing_mock_session_is_forced_back_to_backend():
    app = AppTest.from_file(APP_PATH, default_timeout=15)
    app.session_state["selected_source"] = "mock"
    app.run()

    assert not app.exception
    assert app.session_state["selected_source"] == "backend"


def test_mock_remains_available_only_as_an_explicit_adapter_testing_mode():
    result = solve_expression(
        "(A | B) & (!A | B)", source="mock", rule_mode="pl_only"
    )
    assert result["status"] == "SAT"
    assert [event["type"] for event in result["events"]] == [
        "start", "pure_literal", "solution",
    ]


def test_stale_result_uses_a_neutral_summary_caption_and_disappears_when_equal():
    result = solve_expression("A | B", source="backend", rule_mode="up_only")
    app = AppTest.from_file(APP_PATH, default_timeout=15)
    app.session_state["expression"] = "A | C"
    app.session_state["result"] = result
    app.session_state["solved_expression"] = "A | B"
    app.session_state["solved_source"] = "backend"
    app.session_state["solved_rule"] = "up_only"
    app.run()

    assert not app.exception
    assert not app.warning
    assert "Previous result · Edit made after last Solve" in [item.value for item in app.caption]

    app.session_state["expression"] = "A | B"
    app.session_state["editor_revision"] += 1
    app.run()
    assert not app.exception
    assert "Previous result · Edit made after last Solve" not in [item.value for item in app.caption]


def test_backend_selection_executes_each_real_inference_algorithm():
    expression = "A & (!A | B)"
    up = solve_expression(expression, source="backend", rule_mode="up_only")
    pl = solve_expression(expression, source="backend", rule_mode="pl_only")

    assert up["status"] == pl["status"] == "SAT"
    assert any(event["type"] == "unit_propagation" for event in up["events"])
    assert not any(event["type"] == "pure_literal" for event in up["events"])
    assert any(event["type"] == "pure_literal" for event in pl["events"])
    assert not any(event["type"] == "unit_propagation" for event in pl["events"])


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("(X | Y) & (!X | Z)", "SAT"),
        ("P & !P", "UNSAT"),
        ("(A → B) ∧ A ∧ ¬B", "UNSAT"),
        ("(LEFT ↔ RIGHT) ∨ EXTRA", "SAT"),
    ],
)
@pytest.mark.parametrize("rule_mode", ["up_only", "pl_only"])
def test_backend_solves_arbitrary_valid_formulas(expression, expected, rule_mode):
    result = solve_expression(expression, source="backend", rule_mode=rule_mode)

    assert result["status"] == expected
    validate_result(result)


@pytest.mark.parametrize("expression", ["", "A |", "(A | B", "A & & B", "A $ B"])
def test_backend_syntax_errors_remain_readable(expression):
    with pytest.raises(RuntimeError, match=r"EMPTY_INPUT|SYNTAX_ERROR"):
        solve_expression(expression, source="backend", rule_mode="up_only")


@pytest.mark.parametrize("rule_mode", ["up_only", "pl_only"])
def test_backend_trace_replays_every_step_as_the_existing_vector_tree(rule_mode):
    result = solve_expression(
        "(A | B) & (A | !B) & (!A | B) & (!A | !B)",
        source="backend",
        rule_mode=rule_mode,
    )

    for step in range(len(result["events"])):
        diagram = build_tree(result, step)
        assert diagram.source
        svg, annotation = render_tree_svg(result, step)
        assert "<svg" in svg
        assert annotation is None or annotation["label"] == "Backtrack"
