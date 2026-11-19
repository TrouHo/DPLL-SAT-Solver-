"""Event-by-event Graphviz rendering for normalized DPLL traces."""

from __future__ import annotations

from html import escape
from typing import Any

from graphviz import Digraph

try:
    from .formula_display import clause_to_text, cnf_to_text
except ImportError:  # Streamlit executes frontend/app.py as a script.
    from formula_display import clause_to_text, cnf_to_text


ACTIVE = "#2563eb"
FAILED = "#dc2626"
SUCCESS = "#16845b"
BACKTRACK = "#e87918"
NEUTRAL = "#64748b"
UP_BORDER = "#7c3aad"
UP_FILL = "#f3e8ff"
PL_BORDER = "#0f766e"
PL_FILL = "#ccfbf1"


def _clause_preview(clause: list[int], variables: dict[str, int], limit: int = 48) -> str:
    """Shorten a long clause only at literal boundaries and mark the omission."""
    rendered = clause_to_text(clause, variables)
    if len(rendered) <= limit:
        return rendered

    reverse = {identifier: name for name, identifier in variables.items()}
    literals: list[str] = []
    for literal in clause:
        name = reverse.get(abs(literal), f"v{abs(literal)}")
        literals.append(f"¬{name}" if literal < 0 else name)

    shown: list[str] = []
    for literal in literals:
        candidate = " ∨ ".join([*shown, literal])
        if shown and len(candidate) > limit - 16:
            break
        shown.append(literal)
    omitted = len(literals) - len(shown)
    return f"({' ∨ '.join(shown)} ∨ …) (+{omitted} literals)"


def _remaining_lines(
    cnf: list[list[int]],
    variables: dict[str, int],
    *,
    line_limit: int = 52,
    clause_limit: int = 5,
) -> list[str]:
    """Wrap a CNF at clause boundaries without creating a misleading fragment."""
    if not cnf:
        return ["⊤"]
    if any(not clause for clause in cnf):
        return ["⊥"]

    shown = cnf[:clause_limit]
    pieces = [_clause_preview(clause, variables, line_limit) for clause in shown]
    lines: list[str] = []
    current = ""
    for piece in pieces:
        joined = piece if not current else f"{current} ∧ {piece}"
        if current and len(joined) > line_limit:
            lines.append(current)
            current = f"∧ {piece}"
        else:
            current = joined
    if current:
        lines.append(current)
    omitted_clauses = len(cnf) - len(shown)
    if omitted_clauses:
        lines.append(f"∧ … (+{omitted_clauses} clauses)")
    return lines


def _html_label(title: str, rule: str, details: str, remain_lines: list[str]) -> str:
    """Return a safe, auto-sized Graphviz HTML-like node label."""
    rows = [
        f'<TR><TD ALIGN="CENTER"><B>{escape(title, quote=True)}</B></TD></TR>',
    ]
    if rule:
        rows.append(f'<TR><TD ALIGN="CENTER">{escape(rule, quote=True)}</TD></TR>')
    if details:
        rows.append(f'<TR><TD ALIGN="CENTER">{escape(details, quote=True)}</TD></TR>')
    for index, line in enumerate(remain_lines):
        prefix = "Remain: " if index == 0 else ""
        rows.append(
            f'<TR><TD ALIGN="CENTER">{escape(prefix + line, quote=True)}</TD></TR>'
        )
    return (
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3">'
        + "".join(rows)
        + "</TABLE>>"
    )


def _event_label(event: dict[str, Any], variables: dict[str, int]) -> str:
    kind = event["type"]
    remain = _remaining_lines(event["remaining_cnf"], variables)
    if kind == "start":
        return _html_label("Initial formula", "", "", remain)
    if kind == "decision":
        value = "True" if event["value"] else "False"
        return _html_label("Decision", f"Assume {event['variable']} = {value}", "", remain)
    if kind == "unit_propagation":
        value = "True" if event["value"] else "False"
        return _html_label("Unit propagation", f"{event['variable']} = {value}", "", remain)
    if kind == "pure_literal":
        value = "True" if event["value"] else "False"
        return _html_label("Pure literal", f"{event['variable']} = {value}", "", remain)
    raise ValueError(f"No rectangular label for event type: {kind}")


def get_backtrack_annotation(result: dict[str, Any], visible_seq: int) -> dict[str, str] | None:
    """Describe the current reverse transition without adding it to structural DOT."""
    visible = [event for event in result["events"] if event["seq"] <= visible_seq]
    if not visible or visible[-1]["type"] != "backtrack":
        return None

    frontier: dict[str, str] = {}
    fork_point: dict[str, str] = {}
    branch_side: dict[str, str] = {}
    for event in visible:
        kind = event["type"]
        logical = event["node_id"]
        visual_id = f"evt_{event['seq']}"
        if kind == "start":
            frontier[logical] = visual_id
            fork_point[logical] = visual_id
        elif kind == "decision":
            frontier[logical] = visual_id
            fork_point[logical] = visual_id
            branch_side[logical] = "left" if event["value"] else "right"
        elif kind in {"unit_propagation", "pure_literal", "conflict", "solution", "unsat"}:
            frontier[logical] = visual_id

    current = visible[-1]
    failed = current["from_node"]
    target = current["node_id"]
    return {
        "source_id": frontier[failed],
        "target_id": fork_point[target],
        "side": branch_side.get(failed, "left"),
        "label": "Backtrack",
    }


def build_tree(result: dict[str, Any], visible_seq: int) -> Digraph:
    """Build structural DOT containing only recorded visual events through a step."""
    visible = [event for event in result["events"] if event["seq"] <= visible_seq]
    graph = Digraph(
        "DPLL",
        graph_attr={
            "rankdir": "TB",
            "ordering": "out",
            "bgcolor": "transparent",
            "nodesep": "0.38",
            "ranksep": "0.48",
            "pad": "0.18",
            "splines": "polyline",
            "outputorder": "edgesfirst",
        },
        node_attr={
            "fontname": "Segoe UI Symbol",
            "fontsize": "12",
            "margin": "0.14,0.10",
            "shape": "box",
            "style": "rounded,filled",
            "fontcolor": "#172033",
        },
        edge_attr={
            "fontname": "Segoe UI Symbol",
            "fontsize": "11",
            "arrowsize": "0.75",
            "color": NEUTRAL,
            "fontcolor": "#334155",
        },
    )

    variables = result["variables"]
    frontier: dict[str, str] = {}
    fork_point: dict[str, str] = {}
    failed_logical: set[str] = set()
    successful_logical: set[str] = set()
    visual_nodes: list[tuple[str, dict[str, Any]]] = []
    normal_edges: list[tuple[str, str, dict[str, str]]] = []

    for event in visible:
        kind = event["type"]
        seq = event["seq"]
        logical = event["node_id"]
        visual_id = f"evt_{seq}"

        if kind == "start":
            visual_nodes.append((visual_id, event))
            frontier[logical] = visual_id
            fork_point[logical] = visual_id
        elif kind == "decision":
            parent = event["parent_id"]
            visual_nodes.append((visual_id, event))
            normal_edges.append(
                (
                    fork_point.get(parent, frontier[parent]),
                    visual_id,
                    {
                        "label": f"{event['variable']} = {'True' if event['value'] else 'False'}",
                        "logical": logical,
                        "kind": "decision",
                    },
                )
            )
            frontier[logical] = visual_id
            fork_point[logical] = visual_id
        elif kind in {"unit_propagation", "pure_literal"}:
            visual_nodes.append((visual_id, event))
            normal_edges.append((frontier[logical], visual_id, {"label": "", "logical": logical, "kind": kind}))
            frontier[logical] = visual_id
        elif kind in {"conflict", "solution", "unsat"}:
            visual_nodes.append((visual_id, event))
            normal_edges.append((frontier[logical], visual_id, {"label": "", "logical": logical, "kind": kind}))
            frontier[logical] = visual_id
            if kind in {"conflict", "unsat"}:
                failed_logical.add(logical)
            else:
                successful_logical.add(logical)
        elif kind == "backtrack":
            failed_logical.add(event["from_node"])

    current_kind = visible[-1]["type"] if visible else None
    current_seq = visible[-1]["seq"] if visible else -1
    current_target = visible[-1]["node_id"] if current_kind == "backtrack" else None

    for visual_id, event in visual_nodes:
        kind = event["type"]
        is_current = event["seq"] == current_seq
        tooltip = (
            f"Event {event['seq']} | {event['message']} | Remaining CNF: "
            f"{cnf_to_text(event['remaining_cnf'], variables)}"
        )
        if kind in {"conflict", "unsat", "solution"}:
            success = kind == "solution"
            status = "SAT" if success else ("UNSAT" if kind == "unsat" else "Conflict")
            graph.node(
                visual_id,
                f"{'✓' if success else '×'} {status}",
                shape="box",
                style="rounded,filled",
                margin="0.16,0.10",
                fontsize="12",
                fontcolor="#ffffff",
                color=SUCCESS if success else FAILED,
                fillcolor=SUCCESS if success else FAILED,
                penwidth="2.2" if is_current else "1.8",
                tooltip=tooltip,
            )
            continue

        if kind == "unit_propagation":
            border, fill = UP_BORDER, UP_FILL
        elif kind == "pure_literal":
            border, fill = PL_BORDER, PL_FILL
        else:
            border, fill = NEUTRAL, "#f8fafc"
        if is_current:
            border = ACTIVE
        if current_kind == "backtrack" and event["node_id"] == current_target:
            border, fill = BACKTRACK, "#fff7ed"
        graph.node(
            visual_id,
            label=_event_label(event, variables),
            color=border,
            fillcolor=fill,
            penwidth=(
                "2.3"
                if is_current or (current_kind == "backtrack" and event["node_id"] == current_target)
                else "1.5"
            ),
            tooltip=tooltip,
        )

    for tail, head, meta in normal_edges:
        color = NEUTRAL
        penwidth = "1.2"
        if meta["kind"] == "conflict" or meta["logical"] in failed_logical:
            color, penwidth = FAILED, "1.7"
        elif meta["kind"] == "solution" or meta["logical"] in successful_logical:
            color, penwidth = SUCCESS, "1.7"
        graph.edge(tail, head, label=meta["label"], color=color, penwidth=penwidth)

    return graph


def render_tree_svg(result: dict[str, Any], visible_seq: int) -> tuple[str, dict[str, str] | None]:
    """Render structural DOT as real SVG plus optional browser overlay metadata."""
    svg = build_tree(result, visible_seq).pipe(format="svg").decode("utf-8")
    if "<svg" not in svg or "viewBox=" not in svg:
        raise RuntimeError("Graphviz did not return a viewBox-based SVG.")
    return svg, get_backtrack_annotation(result, visible_seq)
