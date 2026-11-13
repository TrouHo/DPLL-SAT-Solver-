"""The DPLL algorithm: depth-first search with backtracking + unit propagation.

Input: a CNF formula as a list of clauses, each clause a list of integers
(3 means variable 3, -3 means NOT variable 3).

Fixed rules, so that the same input always gives the same search tree:
    - unit propagation always runs before a decision;
    - when several clauses are unit, the first one in clause order is used;
    - the decision variable is the smallest-numbered variable still needed;
    - True is tried before False;
    - pure literal elimination is off.
"""


def _free_literals(clause, assignment):
    """Look at a clause under the current assignment.

    Returns None if the clause is already satisfied, otherwise the list of
    its literals that are not assigned yet. An empty list is a conflict:
    every literal is false.
    """
    free = []
    for literal in clause:
        value = assignment.get(abs(literal))
        if value is None:
            free.append(literal)
        elif value == (literal > 0):
            return None
    return free


def _propagate(clauses, assignment, node_id, tracer):
    """Apply unit propagation until nothing is forced any more.

    Changes ``assignment`` in place. Returns False if a conflict is found.
    """
    while True:
        unit = None
        for index, clause in enumerate(clauses):
            free = _free_literals(clause, assignment)
            if free is None:
                continue
            if not free:
                tracer.conflict(node_id, index, assignment)
                return False
            if len(free) == 1 and unit is None:
                unit = (index, free[0])
        if unit is None:
            return True
        index, literal = unit
        assignment[abs(literal)] = literal > 0  # the only way to satisfy the clause
        tracer.unit_propagation(node_id, abs(literal), literal > 0, index, assignment)


def _pick_variable(clauses, assignment):
    """Smallest unassigned variable of the unsatisfied clauses, or None.

    None means every clause is satisfied: the formula is solved.
    """
    best = None
    for clause in clauses:
        free = _free_literals(clause, assignment)
        if free:
            smallest = min(abs(literal) for literal in free)
            if best is None or smallest < best:
                best = smallest
    return best


def solve(clauses, tracer):
    """Run DPLL. Returns a satisfying assignment {variable: bool}, or None.

    The assignment may be partial: variables that are not needed to
    satisfy the formula are left out.
    """

    def search(node_id, assignment):
        if not _propagate(clauses, assignment, node_id, tracer):
            return None                                   # conflict: this branch fails
        variable = _pick_variable(clauses, assignment)
        if variable is None:
            tracer.solution(node_id, assignment)
            return assignment                             # goal: every clause satisfied
        for value in (True, False):
            child = dict(assignment)                      # each branch gets its own copy
            child[variable] = value
            child_id = tracer.decision(node_id, variable, value, child)
            result = search(child_id, child)
            if result is not None:
                return result
            tracer.backtrack(node_id, child_id, assignment)  # undo and try the other value
        return None                                       # both values failed

    root_id = tracer.root()
    root_assignment = {}
    result = search(root_id, root_assignment)
    if result is None:
        tracer.unsat(root_id, root_assignment)
    return result
