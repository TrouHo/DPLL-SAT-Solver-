"""Turn the text typed by the user into a syntax tree.

Accepted syntax (case-insensitive, spaces ignored):

    variable   A, B, X1, my_var      (a letter, then letters/digits/_)
    not        !A
    and        A & B
    or         A | B
    implies    A -> B                (right-associative)
    iff        A <-> B
    grouping   ( ... )

Precedence, from strongest to weakest:  !  &  |  ->  <->

The tree is made of nested tuples:

    ("var", "A")
    ("not", child)
    ("and", left, right)    ("or", left, right)
    ("imp", left, right)    ("iff", left, right)
"""

from .errors import EMPTY_INPUT, MAX_INPUT_LENGTH, SYNTAX_ERROR, TOO_LARGE, SolverError

SYMBOLS = ("<->", "->", "!", "&", "|", "(", ")")


def tokenize(text):
    """Split the text into (kind, value, position) tokens."""
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        for symbol in SYMBOLS:
            if text.startswith(symbol, i):
                tokens.append((symbol, symbol, i))
                i += len(symbol)
                break
        else:
            if ch.isascii() and ch.isalpha():
                j = i + 1
                while j < len(text) and text[j].isascii() and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                # Variables are case-insensitive: "a" and "A" are the same.
                tokens.append(("VAR", text[i:j].upper(), i))
                i = j
            else:
                raise SolverError(SYNTAX_ERROR, f"Unexpected character {ch!r} at position {i}.", i)
    return tokens


class _Parser:
    """Recursive-descent parser: one method per precedence level."""

    def __init__(self, tokens, length):
        self.tokens = tokens
        self.index = 0
        self.length = length

    def peek(self):
        return self.tokens[self.index][0] if self.index < len(self.tokens) else None

    def position(self):
        return self.tokens[self.index][2] if self.index < len(self.tokens) else self.length

    def take(self):
        token = self.tokens[self.index]
        self.index += 1
        return token

    def parse(self):
        node = self.iff()
        if self.peek() is not None:
            kind, value, pos = self.tokens[self.index]
            raise SolverError(SYNTAX_ERROR, f"Unexpected {value!r} at position {pos}.", pos)
        return node

    def iff(self):
        left = self.implies()
        while self.peek() == "<->":
            self.take()
            left = ("iff", left, self.implies())
        return left

    def implies(self):
        left = self.disjunction()
        if self.peek() == "->":
            self.take()
            return ("imp", left, self.implies())  # A -> B -> C means A -> (B -> C)
        return left

    def disjunction(self):
        left = self.conjunction()
        while self.peek() == "|":
            self.take()
            left = ("or", left, self.conjunction())
        return left

    def conjunction(self):
        left = self.negation()
        while self.peek() == "&":
            self.take()
            left = ("and", left, self.negation())
        return left

    def negation(self):
        count = 0
        while self.peek() == "!":
            self.take()
            count += 1
        node = self.atom()
        # "!!A" is just "A": only an odd number of "!" negates.
        return ("not", node) if count % 2 else node

    def atom(self):
        kind = self.peek()
        if kind == "VAR":
            return ("var", self.take()[1])
        if kind == "(":
            open_pos = self.take()[2]
            node = self.iff()
            if self.peek() != ")":
                raise SolverError(
                    SYNTAX_ERROR,
                    f"Missing ')' for the '(' at position {open_pos}.",
                    self.position(),
                )
            self.take()
            return node
        pos = self.position()
        if kind is None:
            raise SolverError(SYNTAX_ERROR, "The expression ends too early: a variable or '(' is expected.", pos)
        raise SolverError(SYNTAX_ERROR, f"A variable or '(' is expected at position {pos}.", pos)


def parse(text):
    """Parse the expression and return its syntax tree."""
    if not text.strip():
        raise SolverError(EMPTY_INPUT, "The expression is empty.")
    if len(text) > MAX_INPUT_LENGTH:
        raise SolverError(TOO_LARGE, f"The expression is longer than {MAX_INPUT_LENGTH} characters.")
    return _Parser(tokenize(text), len(text)).parse()


def variables(node):
    """Return the set of variable names used in the tree."""
    if node[0] == "var":
        return {node[1]}
    names = set()
    for child in node[1:]:
        names |= variables(child)
    return names


def evaluate(node, assignment, default=False):
    """Compute the truth value of the tree under ``assignment`` (name -> bool).

    Variables missing from the assignment take the value ``default``.
    Used to check that a returned solution really satisfies the input.
    """
    kind = node[0]
    if kind == "var":
        return assignment.get(node[1], default)
    if kind == "not":
        return not evaluate(node[1], assignment, default)
    left = evaluate(node[1], assignment, default)
    right = evaluate(node[2], assignment, default)
    if kind == "and":
        return left and right
    if kind == "or":
        return left or right
    if kind == "imp":
        return (not left) or right
    return left == right  # iff
