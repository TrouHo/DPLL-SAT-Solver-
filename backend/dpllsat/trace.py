"""Record what the solver does, step by step, for the frontend.

Every event has: seq, type, node_id and assignment (a snapshot of the
variables assigned at that moment). Some types carry extra fields:

    root              -
    decision          parent_id, variable, value     (creates a new node)
    unit_propagation  variable, value, reason_clause (stays in the node)
    conflict          reason_clause                  (stays in the node)
    backtrack         from_node                      (node_id = node we return to)
    solution / unsat  -
"""

from .errors import MAX_EVENTS, MAX_STEPS, TOO_LARGE, SolverError


class Tracer:
    def __init__(self, names, enabled=True):
        self.names = names        # {variable number: name}
        self.enabled = enabled    # False: count the steps but store nothing
        self.events = []
        self._steps = 0
        self._nodes = 0

    # -- helpers ---------------------------------------------------------

    def _new_node(self):
        node_id = f"n{self._nodes}"
        self._nodes += 1
        return node_id

    def _snapshot(self, assignment):
        """Copy the assignment with names instead of numbers."""
        return {self.names[variable]: value for variable, value in assignment.items()}

    @staticmethod
    def _clause_id(index):
        return f"c{index + 1}"

    def _emit(self, kind, node_id, assignment, **fields):
        self._steps += 1
        if self._steps > (MAX_EVENTS if self.enabled else MAX_STEPS):
            raise SolverError(TOO_LARGE, "The search is too long for this expression.")
        if not self.enabled:
            return
        event = {"seq": len(self.events), "type": kind, "node_id": node_id}
        event.update(fields)
        event["assignment"] = self._snapshot(assignment)
        self.events.append(event)

    # -- one method per event type ---------------------------------------

    def root(self):
        node_id = self._new_node()
        self._emit("root", node_id, {})
        return node_id

    def decision(self, parent_id, variable, value, assignment):
        node_id = self._new_node()
        self._emit("decision", node_id, assignment,
                   parent_id=parent_id, variable=self.names[variable], value=value)
        return node_id

    def unit_propagation(self, node_id, variable, value, clause_index, assignment):
        self._emit("unit_propagation", node_id, assignment,
                   variable=self.names[variable], value=value,
                   reason_clause=self._clause_id(clause_index))

    def conflict(self, node_id, clause_index, assignment):
        self._emit("conflict", node_id, assignment,
                   reason_clause=self._clause_id(clause_index))

    def backtrack(self, node_id, from_node, assignment):
        self._emit("backtrack", node_id, assignment, from_node=from_node)

    def solution(self, node_id, assignment):
        self._emit("solution", node_id, assignment)

    def unsat(self, node_id, assignment):
        self._emit("unsat", node_id, assignment)
