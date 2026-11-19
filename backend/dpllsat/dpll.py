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


def _check_conflict(clauses, assignment, node_id, tracer):
    """Report the first unsatisfied clause, independently of inference rules."""
    for index, clause in enumerate(clauses):
        if _free_literals(clause, assignment) == []:
            tracer.conflict(node_id, index, assignment)
            return True
    return False


def _pick_pure_literal(clauses, assignment):
    """Return the smallest pure variable and its satisfying value, if any."""
    polarities = {}
    for clause in clauses:
        free = _free_literals(clause, assignment)
        if free is None:
            continue
        for literal in free:
            polarities.setdefault(abs(literal), set()).add(literal > 0)
    for variable in sorted(polarities):
        signs = polarities[variable]
        if len(signs) == 1:
            return variable, next(iter(signs))
    return None


def _eliminate_pure_literals(clauses, assignment, node_id, tracer):
    """Apply pure-literal elimination to a fixed point, without running UP."""
    while True:
        if _check_conflict(clauses, assignment, node_id, tracer):
            return False
        pure = _pick_pure_literal(clauses, assignment)
        if pure is None:
            return True
        variable, value = pure
        assignment[variable] = value
        tracer.pure_literal(node_id, variable, value, assignment)


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


def solve(clauses, tracer, rule_mode="up_only"):
    """Run DPLL. Returns a satisfying assignment {variable: bool}, or None.

    The assignment may be partial: variables that are not needed to
    satisfy the formula are left out.
    """

    if rule_mode not in ("up_only", "pl_only"):
        raise ValueError("Unsupported rule_mode")

    def search(node_id, assignment):
        if rule_mode == "up_only":
            reduced = _propagate(clauses, assignment, node_id, tracer)
        else:
            reduced = _eliminate_pure_literals(clauses, assignment, node_id, tracer)
        if not reduced:
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
