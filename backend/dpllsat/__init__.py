"""DPLL SAT solver backend (Problem Solving lab project).

Public entry point: ``solve_request(payload: dict) -> dict``.
"""

from .service import solve_request

__all__ = ["solve_request"]
