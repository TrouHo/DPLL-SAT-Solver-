"""Errors and limits shared by every module."""

# Limits agreed with the frontend.
MAX_INPUT_LENGTH = 1000     # characters in the expression
MAX_VARIABLES = 20          # distinct variables
MAX_CLAUSES = 50            # clauses after conversion to CNF
MAX_EVENTS = 2000           # trace events returned to the frontend
MAX_STEPS = 200_000         # solver steps when the trace is switched off
MAX_INTERMEDIATE_CLAUSES = 5000  # guard against blow-up during CNF conversion

# Error codes agreed with the frontend.
EMPTY_INPUT = "EMPTY_INPUT"
SYNTAX_ERROR = "SYNTAX_ERROR"
TOO_LARGE = "TOO_LARGE"
INVALID_REQUEST = "INVALID_REQUEST"
INTERNAL_ERROR = "INTERNAL_ERROR"


class SolverError(Exception):
    """A problem with the request that must be reported to the user.

    ``position`` is the 0-based index of the offending character in the
    expression, when it is known.
    """

    def __init__(self, code, message, position=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.position = position
