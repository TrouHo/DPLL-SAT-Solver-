"""Streamlit user interface and trace replay for the DPLL assignment."""

from __future__ import annotations

import streamlit as st

try:
    from .formula_editor import formula_editor
    from .formula_display import assignment_to_text, clause_to_text, cnf_to_text
    from .mock_solver import EXAMPLES
    from .solver_adapter import solve_expression
    from .tree_visualizer import build_tree, render_tree_svg
except ImportError:  # Supports: python -m streamlit run frontend/app.py
    from formula_editor import formula_editor
    from formula_display import assignment_to_text, clause_to_text, cnf_to_text
    from mock_solver import EXAMPLES
    from solver_adapter import solve_expression
    from tree_visualizer import build_tree, render_tree_svg


SOURCE_LABELS = {"mock": "Mock", "backend": "Backend"}
RULE_LABELS = {"up_only": "Unit propagation", "pl_only": "Pure literal"}


_TREE_VIEWER_HTML = """
<div class="tree-viewport" role="img" aria-label="DPLL event tree"></div>
"""


_TREE_VIEWER_CSS = """
:host { color: var(--st-text-color); font-family: var(--st-font); }
.tree-viewport {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 0.35rem;
}
.tree-viewport svg {
  display: block;
  width: max-content;
  max-width: none;
  height: auto;
  margin: 0 auto;
}
"""


_TREE_VIEWER_JS = """
export default function(component) {
  const { data, parentElement } = component;
  const viewport = parentElement.querySelector(".tree-viewport");
  if (!viewport) return;

  viewport.innerHTML = String(data?.svg ?? "");
  const svg = viewport.querySelector("svg");
  if (!svg) return;
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "DPLL event tree through the current replay step");
  svg.style.display = "block";
  svg.style.width = "max-content";
  svg.style.maxWidth = "none";
  svg.style.height = "auto";
  const initialViewBox = svg.viewBox.baseVal;
  svg.setAttribute("width", `${initialViewBox.width}px`);

  const annotation = data?.annotation;
  if (!annotation) return;

  const nodes = [...svg.querySelectorAll("g.node")];
  const findNode = (id) => nodes.find(
    (node) => node.querySelector(":scope > title")?.textContent === id
  );
  const source = findNode(annotation.source_id);
  const target = findNode(annotation.target_id);
  if (!source || !target) return;

  const bounds = (node) => {
    const box = node.getBBox();
    return {
      left: box.x, right: box.x + box.width,
      top: box.y, bottom: box.y + box.height,
    };
  };

  const allBounds = nodes.map(bounds);
  const sourceBox = bounds(source);
  const targetBox = bounds(target);
  const leftSide = annotation.side !== "right";
  const gutter = leftSide
    ? Math.min(...allBounds.map((box) => box.left)) - 52
    : Math.max(...allBounds.map((box) => box.right)) + 52;
  const startX = leftSide ? sourceBox.left : sourceBox.right;
  const endX = leftSide ? targetBox.left : targetBox.right;
  const startY = (sourceBox.top + sourceBox.bottom) / 2;
  const endY = (targetBox.top + targetBox.bottom) / 2;

  const namespace = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(namespace, "defs");
  const marker = document.createElementNS(namespace, "marker");
  marker.setAttribute("id", "dpll-backtrack-arrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "9");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "7");
  marker.setAttribute("markerHeight", "7");
  marker.setAttribute("orient", "auto-start-reverse");
  const arrow = document.createElementNS(namespace, "path");
  arrow.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  arrow.setAttribute("fill", "#e87918");
  marker.appendChild(arrow);
  defs.appendChild(marker);
  svg.appendChild(defs);

  const path = document.createElementNS(namespace, "path");
  path.setAttribute(
    "d",
    `M ${startX} ${startY} L ${gutter} ${startY} L ${gutter} ${endY} L ${endX} ${endY}`
  );
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "#e87918");
  path.setAttribute("stroke-width", "2.25");
  path.setAttribute("stroke-dasharray", "7 5");
  path.setAttribute("stroke-linejoin", "round");
  path.setAttribute("marker-end", "url(#dpll-backtrack-arrow)");
  path.setAttribute("class", "backtrack-overlay");
  const graphGroup = source.parentElement;
  graphGroup.appendChild(path);

  const label = document.createElementNS(namespace, "text");
  const labelY = (startY + endY) / 2;
  label.textContent = annotation.label ?? "Backtrack";
  label.setAttribute("x", String(gutter));
  label.setAttribute("y", String(labelY));
  label.setAttribute("fill", "#c65f0a");
  label.setAttribute("font-size", "12");
  label.setAttribute("font-weight", "600");
  label.setAttribute("text-anchor", "middle");
  label.setAttribute("transform", `rotate(${leftSide ? -90 : 90} ${gutter} ${labelY})`);
  label.setAttribute("class", "backtrack-label");
  graphGroup.appendChild(label);

  const viewBox = svg.viewBox.baseVal;
  const padding = 20;
  const graphMatrix = graphGroup.transform.baseVal.consolidate()?.matrix;
  const gutterInViewBox = graphMatrix
    ? new DOMPoint(gutter, 0).matrixTransform(graphMatrix).x
    : gutter;
  const nextLeft = Math.min(viewBox.x, gutterInViewBox - padding);
  const nextRight = Math.max(viewBox.x + viewBox.width, gutterInViewBox + padding);
  svg.setAttribute("viewBox", `${nextLeft} ${viewBox.y} ${nextRight - nextLeft} ${viewBox.height}`);
  svg.setAttribute("width", `${nextRight - nextLeft}px`);
}
"""


_TREE_VIEWER = st.components.v2.component(
    "dpll_tree_viewer",
    html=_TREE_VIEWER_HTML,
    css=_TREE_VIEWER_CSS,
    js=_TREE_VIEWER_JS,
)


def clamp_step(step: int, event_count: int) -> int:
    """Clamp navigation to the available event range."""
    return max(0, min(step, max(0, event_count - 1)))


def _set_step(step: int) -> None:
    count = len(st.session_state.result["events"]) if st.session_state.result else 0
    value = clamp_step(step, count)
    st.session_state.step_idx = value
    st.session_state.timeline_slider = value


def _first() -> None:
    st.session_state.playing = False
    _set_step(0)


def _previous() -> None:
    st.session_state.playing = False
    _set_step(st.session_state.step_idx - 1)


def _next() -> None:
    st.session_state.playing = False
    _set_step(st.session_state.step_idx + 1)


def _last() -> None:
    st.session_state.playing = False
    _set_step(len(st.session_state.result["events"]) - 1)


def _toggle_play() -> None:
    if st.session_state.result:
        at_end = st.session_state.step_idx >= len(st.session_state.result["events"]) - 1
        st.session_state.playing = False if at_end else not st.session_state.playing


def _seek() -> None:
    st.session_state.step_idx = st.session_state.timeline_slider
    st.session_state.playing = False


def _clear_result() -> None:
    st.session_state.result = None
    st.session_state.solved_expression = None
    st.session_state.solved_source = None
    st.session_state.solved_rule = None
    st.session_state.step_idx = 0
    st.session_state.timeline_slider = 0
    st.session_state.playing = False


def _invalidate_solver_context() -> None:
    """Rule changes invalidate traces produced under another context."""
    st.session_state.selected_source = "backend"
    if st.session_state.get("rule_mode") not in RULE_LABELS:
        st.session_state.rule_mode = "up_only"
    _clear_result()


def _load_example(expression: str) -> None:
    st.session_state.expression = expression
    st.session_state.editor_revision += 1
    _clear_result()


def _reset() -> None:
    st.session_state.expression = ""
    st.session_state.editor_revision += 1
    _clear_result()


def _initialize_state() -> None:
    defaults = {
        "expression": EXAMPLES["SAT + backtrack"],
        "editor_revision": 0,
        "result": None,
        "solved_expression": None,
        "solved_source": None,
        "solved_rule": None,
        "step_idx": 0,
        "timeline_slider": 0,
        "playing": False,
        "selected_source": "backend",
        "rule_mode": "up_only",
        "speed": 1.0,
        "expand_tree": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    # Backend is the only interactive source; Mock remains available to tests.
    st.session_state.selected_source = "backend"
    if st.session_state.rule_mode not in RULE_LABELS:
        st.session_state.rule_mode = "up_only"


def _event_label(event: dict) -> str:
    return event["type"].replace("_", " ").title()


def _active_branch_label(current: dict, events: list[dict]) -> str:
    """Return the semantic decision ancestry for the current logical node."""
    decisions = {
        event["node_id"]: event
        for event in events
        if event["type"] == "decision"
    }
    path: list[str] = []
    node_id = current["node_id"]
    visited: set[str] = set()
    while node_id in decisions and node_id not in visited:
        visited.add(node_id)
        decision = decisions[node_id]
        value = "True" if decision["value"] else "False"
        path.append(f"{decision['variable']} = {value}")
        node_id = decision.get("parent_id")
    return " → ".join(reversed(path)) if path else "Root"


def _render_tree(result: dict, visible_seq: int, height: int) -> None:
    """Render structural Graphviz output as a scrollable vector SVG."""
    try:
        svg, annotation = render_tree_svg(result, visible_seq)
    except Exception as exc:  # pragma: no cover - depends on the local dot executable
        st.error(f"The vector tree could not be rendered: {exc}")
        diagram = build_tree(result, visible_seq)
        st.graphviz_chart(
            diagram.source,
            width="content",
            alt="Expanded DPLL event tree through the current trace step",
        )
        return
    _TREE_VIEWER(
        key="tree_svg_viewer",
        data={"svg": svg, "annotation": annotation, "visible_seq": visible_seq},
        width="stretch",
        height=height,
    )


def _render_summary(result: dict, current: dict, last_index: int, *, stale: bool) -> None:
    with st.container(key="result_summary", border=True):
        status_col, model_col, step_col, context_col = st.columns([0.75, 2.1, 0.9, 1.25])
        if result["status"] == "SAT":
            status_col.markdown("<div class='result-pill sat'>SAT</div>", unsafe_allow_html=True)
            model = assignment_to_text(result["assignment"], result["variables"], show_unassigned=True)
            model_col.markdown(f"**Model:** {model}")
        else:
            status_col.markdown("<div class='result-pill unsat'>UNSAT</div>", unsafe_allow_html=True)
            model_col.markdown("**Model:** none")
        step_col.markdown(f"**Step:** {current['seq']} / {last_index}")
        context_col.caption(
            f"{SOURCE_LABELS[st.session_state.solved_source]} · "
            f"{RULE_LABELS[st.session_state.solved_rule]}"
        )
        if stale:
            context_col.caption("Previous result · Edit made after last Solve")


def _render_details(current: dict, result: dict) -> None:
    st.markdown(f"**Event** &nbsp;&nbsp; {_event_label(current)}")
    branch = _active_branch_label(current, result["events"])
    st.markdown(f"**Active branch** &nbsp;&nbsp; {branch}")
    st.markdown(
        "**Partial assignment** &nbsp;&nbsp; "
        + assignment_to_text(current["assignment"], result["variables"], show_unassigned=True)
    )
    st.markdown("**Remaining CNF** &nbsp;&nbsp; " + cnf_to_text(current["remaining_cnf"], result["variables"]))
    reason = "—"
    if current.get("reason_clause") is not None:
        reason = clause_to_text(current["reason_clause"], result["variables"])
    st.markdown(f"**Reason clause** &nbsp;&nbsp; {reason}")
    if current["type"] == "backtrack":
        st.markdown(f"**Transition** &nbsp;&nbsp; Resume {branch}")
    with st.container(border=True):
        st.caption(f"Explanation: {current['message']}")


def _render_replay(result: dict) -> None:
    events = result["events"]
    last_index = len(events) - 1
    st.session_state.step_idx = clamp_step(st.session_state.step_idx, len(events))
    interval = st.session_state.speed if st.session_state.playing else None

    @st.fragment(run_every=interval)
    def replay_fragment() -> None:
        if st.session_state.playing:
            if st.session_state.step_idx < last_index:
                st.session_state.step_idx += 1
            if st.session_state.step_idx >= last_index:
                st.session_state.playing = False

        st.session_state.timeline_slider = st.session_state.step_idx
        current = events[st.session_state.step_idx]
        stale = st.session_state.expression != st.session_state.solved_expression
        _render_summary(result, current, last_index, stale=stale)

        with st.container(key="replay_workspace"):
            tree_col, details_col = st.columns([1.8, 1], gap="small")
            with tree_col:
                with st.container(key="tree_panel", border=True):
                    heading_col, toggle_col = st.columns([4, 1.1], vertical_alignment="center")
                    heading_col.subheader("Search tree")
                    toggle_col.toggle("Expand", key="expand_tree", help="Increase the tree viewport height.")
                    tree_height = 760 if st.session_state.expand_tree else 560
                    _render_tree(result, current["seq"], tree_height)
            with details_col:
                with st.container(key="details_panel", height=650 if not st.session_state.expand_tree else 842, border=True):
                    st.subheader("Current step")
                    _render_details(current, result)

        with st.container(key="replay_panel", border=True):
            label_col, first_col, previous_col, play_col, next_col, last_col, speed_col = st.columns(
                [1.3, 1, 1.2, 1.1, 1.1, 1, 1.5], vertical_alignment="center"
            )
            label_col.markdown("**Replay controls**")
            first_col.button("First", disabled=current["seq"] == 0, on_click=_first, width="stretch")
            previous_col.button("Previous", disabled=current["seq"] == 0, on_click=_previous, width="stretch")
            play_label = "Pause" if st.session_state.playing else "Play"
            play_col.button(play_label, type="primary", disabled=current["seq"] == last_index, on_click=_toggle_play, width="stretch")
            next_col.button("Next", disabled=current["seq"] == last_index, on_click=_next, width="stretch")
            last_col.button("Last", disabled=current["seq"] == last_index, on_click=_last, width="stretch")
            speed_col.select_slider(
                "Speed", options=[0.5, 1.0, 1.5, 2.0], key="speed",
                format_func=lambda value: f"{value:.1f}s", label_visibility="collapsed",
            )
            st.slider("Trace step", 0, last_index, key="timeline_slider", on_change=_seek, label_visibility="collapsed")

        rows = [
            {"Step": event["seq"], "Event": event["type"], "Node": event["node_id"], "Message": event["message"]}
            for event in events
        ]
        with st.expander("Event timeline and raw trace"):
            st.dataframe(rows, width="stretch", hide_index=True)
            st.json(result)

    replay_fragment()


def _render_page_styles() -> None:
    st.html(
        """
        <style>
        [data-testid="stHeader"] {display: none;}
        .stMainBlockContainer {max-width: 1680px; padding-top: .6rem; padding-bottom: 1rem;}
        h1 {letter-spacing: -.035em; margin-bottom: 0 !important;}
        h2, h3 {letter-spacing: -.02em;}
        .st-key-formula_panel, .st-key-result_summary, .st-key-tree_panel,
        .st-key-details_panel, .st-key-replay_panel {box-shadow: 0 1px 2px rgba(23,32,51,.04);}
        .st-key-solve_action button {background: #dc2626; border-color: #dc2626; color: white;}
        .st-key-solve_action button:hover {background: #b91c1c; border-color: #b91c1c; color: white;}
        .result-pill {font-weight: 800; border-radius: 10px; padding: .38rem .75rem; text-align: center;}
        .result-pill.sat {background: #dcfce7; color: #08783e;}
        .result-pill.unsat {background: #fee2e2; color: #b91c1c;}
        .st-key-tree_panel h3, .st-key-details_panel h3 {margin-top: 0;}
        .st-key-tree_panel [data-testid="stGraphVizChart"] {display: flex; justify-content: center;}
        @media (max-width: 900px) {
            .stMainBlockContainer {padding-left: .7rem; padding-right: .7rem;}
            .st-key-header_controls > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
            .st-key-replay_workspace > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
                flex-direction: column;
            }
            .st-key-header_controls > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
            .st-key-replay_workspace > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                width: 100%; flex: 1 1 100%;
            }
            .st-key-result_summary > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
            .st-key-action_row > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
            .st-key-replay_panel > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap;
            }
            .st-key-result_summary > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                width: auto; flex: 1 1 45%;
            }
            .st-key-action_row > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
            .st-key-replay_panel > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
                width: auto; flex: 1 1 130px;
            }
        }
        </style>
        """
    )


def main() -> None:
    st.set_page_config(page_title="DPLL SAT Solver", layout="wide")
    _initialize_state()
    _render_page_styles()

    with st.container(key="header_controls"):
        title_col, rule_col = st.columns([4.95, 1.9], vertical_alignment="center")
        with title_col:
            st.title("DPLL SAT Solver")
            st.caption("Interactive visualization of DPLL search and trace replay")
        with rule_col:
            st.segmented_control(
                "Rule mode", options=list(RULE_LABELS), key="rule_mode",
                format_func=RULE_LABELS.get, on_change=_invalidate_solver_context, width="stretch",
            )

    with st.container(key="formula_panel", border=True):
        st.subheader("Enter propositional formula")
        editor_result = formula_editor(
            value=st.session_state.expression,
            revision=st.session_state.editor_revision,
            key="formula_editor_widget",
        )
        editor_value = getattr(editor_result, "value", None)
        editor_value_revision = getattr(editor_result, "revision", None)
        if editor_value_revision == str(st.session_state.editor_revision) and isinstance(editor_value, str):
            st.session_state.expression = editor_value
        if getattr(editor_result, "cleared", None) is not None:
            st.session_state.expression = ""
            st.session_state.editor_revision += 1
            st.rerun()

    with st.container(key="action_row"):
        example_columns = st.columns([1, 1, 1, 1, .85, .85], gap="small")
        for column, (name, expression) in zip(example_columns, EXAMPLES.items()):
            column.button(
                f"Load {name}", key=f"example_{name}", on_click=_load_example,
                args=(expression,), width="stretch",
            )
        solve_clicked = example_columns[4].button("Solve", type="primary", key="solve_action", width="stretch")
        example_columns[5].button("Reset", key="reset_action", on_click=_reset, width="stretch")

    if solve_clicked:
        expression = st.session_state.expression
        if not expression.strip():
            st.error("Enter a propositional formula before solving.")
        elif len(expression) > 1000:
            st.error("The expression is too long (maximum: 1000 characters).")
        else:
            try:
                result = solve_expression(
                    expression,
                    source="backend",
                    rule_mode=st.session_state.rule_mode,
                )
            except (ValueError, RuntimeError) as exc:
                _clear_result()
                st.error(str(exc))
            else:
                st.session_state.result = result
                st.session_state.solved_expression = expression
                st.session_state.solved_source = "backend"
                st.session_state.solved_rule = st.session_state.rule_mode
                st.session_state.step_idx = 0
                st.session_state.timeline_slider = 0
                st.session_state.playing = False

    result = st.session_state.result
    if result is not None:
        _render_replay(result)


if __name__ == "__main__":
    main()
