from frontend import app
from frontend.mock_solver import EXAMPLES, solve_expression


def test_solver_and_rule_labels_are_plain_text():
    assert app.SOURCE_LABELS == {"mock": "Mock", "backend": "Backend"}
    assert app.RULE_LABELS == {"up_only": "Unit propagation", "pl_only": "Pure literal"}


def test_tree_viewer_keeps_svg_vector_and_routes_backtrack_as_overlay():
    javascript = app._TREE_VIEWER_JS
    css = app._TREE_VIEWER_CSS
    assert 'viewport.innerHTML = String(data?.svg ?? "")' in javascript
    assert "backtrack-overlay" in javascript
    assert "stroke-dasharray" in javascript
    assert "marker-end" in javascript
    assert 'annotation.side !== "right"' in javascript
    assert "width: max-content" in css
    assert "max-width: none" in css


def test_page_source_has_no_decorative_icon_labels_or_png_tree_path():
    source = open(app.__file__, encoding="utf-8").read()
    decorative = [
        "🧩", "🧪", "🗄️", "⚡", "✨", "📄", "🎬", "🧱", "🎯", "🏷️",
        "ⓘ", "⏮", "⏸", "⏭", "🔴", "🟢", "🟠", "🟣", "🟦", "🔵",
    ]
    assert not any(icon in source for icon in decorative)
    assert 'format="png"' not in source
    assert "st.image(" not in source


def test_active_branch_is_semantic_for_root_nested_decisions_and_backtrack():
    result = solve_expression(EXAMPLES["UNSAT"], rule_mode="pl_only")
    events = result["events"]

    assert app._active_branch_label(events[0], events) == "Root"
    assert app._active_branch_label(events[1], events) == "A = True"
    assert app._active_branch_label(events[2], events) == "A = True → B = True"
    assert app._active_branch_label(events[4], events) == "A = True"
    assert app._active_branch_label(events[8], events) == "Root"


def test_page_source_uses_neutral_stale_caption_instead_of_warning():
    source = open(app.__file__, encoding="utf-8").read()
    assert 'caption("Previous result · Edit made after last Solve")' in source
    assert "Results correspond to the last Solve input" not in source
