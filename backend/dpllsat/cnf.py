"""Convert a syntax tree to conjunctive normal form (CNF).

The conversion keeps the formula logically equivalent (no helper variables):

    1. remove -> and <->
    2. push negations down to the variables (De Morgan, double negation)
    3. distribute OR over AND

Step 3 can make the formula exponentially larger, so the size is checked
all along and a TOO_LARGE error is raised when a limit is passed.

A literal is a pair (name, positive), e.g. ("A", False) for !A.
A clause is a tuple of literals. A CNF formula is a list of clauses.
"""

import re

from .errors import MAX_INTERMEDIATE_CLAUSES, TOO_LARGE, SolverError


def _simplify(clauses):
    """Remove repeated literals, always-true clauses and repeated clauses."""
    result = []
    seen = set()
    for clause in clauses:
        literals = tuple(dict.fromkeys(clause))  # drop repeats, keep order
        present = set(literals)
        if any((name, not positive) in present for name, positive in literals):
            continue  # contains A and !A: always true, so it constrains nothing
        key = frozenset(literals)
        if key not in seen:
            seen.add(key)
            result.append(literals)
    return result


def _and(left, right):
    """CNF of (left AND right): just put the clauses together."""
    return _simplify(left + right)


def _or(left, right):
    """CNF of (left OR right): one clause for every pair of clauses."""
    if len(left) * len(right) > MAX_INTERMEDIATE_CLAUSES:
        raise SolverError(TOO_LARGE, "The expression becomes too large when converted to CNF.")
    return _simplify([a + b for a in left for b in right])


def to_cnf(tree):
    """Return the CNF of the tree as a list of clauses."""
    memo = {}

    def convert(node, positive):
        """CNF of ``node`` if positive, of ``NOT node`` otherwise."""
        key = (id(node), positive)
        if key in memo:
            return memo[key]
        kind = node[0]
        if kind == "var":
            result = [((node[1], positive),)]
        elif kind == "not":
            result = convert(node[1], not positive)
        else:
            a, b = node[1], node[2]
            if kind == "and":
                # !(a & b) = !a | !b
                result = _and(convert(a, True), convert(b, True)) if positive \
                    else _or(convert(a, False), convert(b, False))
            elif kind == "or":
                # !(a | b) = !a & !b
                result = _or(convert(a, True), convert(b, True)) if positive \
                    else _and(convert(a, False), convert(b, False))
            elif kind == "imp":
                # a -> b = !a | b          !(a -> b) = a & !b
                result = _or(convert(a, False), convert(b, True)) if positive \
                    else _and(convert(a, True), convert(b, False))
            else:  # iff
                if positive:
                    # a <-> b = (!a | b) & (!b | a)
                    result = _and(_or(convert(a, False), convert(b, True)),
                                  _or(convert(b, False), convert(a, True)))
                else:
                    # !(a <-> b) = (a | b) & (!a | !b)
                    result = _and(_or(convert(a, True), convert(b, True)),
                                  _or(convert(a, False), convert(b, False)))
        memo[key] = result
        return result

    return convert(tree, True)


def _natural_key(name):
    """Sort key so that X2 comes before X10."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]


def encode(clauses):
    """Number the variables and rewrite the clauses with integers.

    Variables are numbered 1, 2, 3... in alphabetical order. A positive
    integer is the variable, a negative one is its negation:
    [("A", False), ("B", True)] becomes [-1, 2].

    Returns (integer clauses, {number: name}).
    """
    ordered = sorted({name for clause in clauses for name, _ in clause}, key=_natural_key)
    number = {name: index for index, name in enumerate(ordered, 1)}
    encoded = [[number[name] if positive else -number[name] for name, positive in clause]
               for clause in clauses]
    return encoded, {index: name for name, index in number.items()}


def literal_text(literal):
    name, positive = literal
    return name if positive else "!" + name


def cnf_text(clauses):
    """Readable form of the CNF, e.g. "(!A | B) & (A | C)"."""
    parts = []
    for clause in clauses:
        body = " | ".join(literal_text(literal) for literal in clause)
        parts.append(f"({body})" if len(clause) > 1 else body)
    return " & ".join(parts)
