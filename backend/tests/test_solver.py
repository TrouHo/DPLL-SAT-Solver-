"""Unit tests. Run from the backend folder with:  python -m unittest"""

import itertools
import json
import random
import unittest
from unittest import mock

from dpllsat import solve_request
from dpllsat import cnf, parser
from dpllsat.errors import SolverError


def solve(expression, trace=True):
    return solve_request({"expression": expression, "trace": trace})


def all_assignments(names):
    names = sorted(names)
    for values in itertools.product([False, True], repeat=len(names)):
        yield dict(zip(names, values))


def clauses_hold(clauses, assignment):
    return all(any(assignment[name] == positive for name, positive in clause)
               for clause in clauses)


class ContractExample(unittest.TestCase):
    """The reference example of the BE/FE contract must be reproduced exactly."""

    def test_reference_response(self):
        response = solve("(!A | B) & (!A | !B) & (A | C)")
        self.assertEqual(response["status"], "SAT")
        self.assertEqual(response["assignment"], {"A": False, "C": True})
        self.assertEqual(response["cnf"], "(!A | B) & (!A | !B) & (A | C)")
        self.assertEqual(response["clauses"], [
            {"id": "c1", "literals": ["!A", "B"]},
            {"id": "c2", "literals": ["!A", "!B"]},
            {"id": "c3", "literals": ["A", "C"]},
        ])
        self.assertEqual(response["events"], [
            {"seq": 0, "type": "root", "node_id": "n0", "assignment": {}},
            {"seq": 1, "type": "decision", "node_id": "n1", "parent_id": "n0",
             "variable": "A", "value": True, "assignment": {"A": True}},
            {"seq": 2, "type": "unit_propagation", "node_id": "n1", "variable": "B",
             "value": True, "reason_clause": "c1", "assignment": {"A": True, "B": True}},
            {"seq": 3, "type": "conflict", "node_id": "n1", "reason_clause": "c2",
             "assignment": {"A": True, "B": True}},
            {"seq": 4, "type": "backtrack", "node_id": "n0", "from_node": "n1",
             "assignment": {}},
            {"seq": 5, "type": "decision", "node_id": "n2", "parent_id": "n0",
             "variable": "A", "value": False, "assignment": {"A": False}},
            {"seq": 6, "type": "unit_propagation", "node_id": "n2", "variable": "C",
             "value": True, "reason_clause": "c3", "assignment": {"A": False, "C": True}},
            {"seq": 7, "type": "solution", "node_id": "n2",
             "assignment": {"A": False, "C": True}},
        ])


class Results(unittest.TestCase):
    def test_unit_only_has_no_decision(self):
        response = solve("A & (!A | B)")
        self.assertEqual(response["status"], "SAT")
        self.assertEqual(response["assignment"], {"A": True, "B": True})
        self.assertEqual([e["type"] for e in response["events"]],
                         ["root", "unit_propagation", "unit_propagation", "solution"])
        self.assertTrue(all(e["node_id"] == "n0" for e in response["events"]))

    def test_direct_contradiction(self):
        response = solve("A & !A")
        self.assertEqual(response["status"], "UNSAT")
        self.assertIsNone(response["assignment"])
        self.assertEqual([e["type"] for e in response["events"]],
                         ["root", "unit_propagation", "conflict", "unsat"])

    def test_unsat_after_both_branches_fail(self):
        response = solve("(A | B) & (A | !B) & (!A | B) & (!A | !B)")
        self.assertEqual(response["status"], "UNSAT")
        types = [e["type"] for e in response["events"]]
        self.assertEqual(types.count("decision"), 2)
        self.assertEqual(types.count("conflict"), 2)
        self.assertEqual(types.count("backtrack"), 2)   # the False branch backtracks too
        last = response["events"][-1]
        self.assertEqual((last["type"], last["node_id"], last["assignment"]), ("unsat", "n0", {}))

    def test_true_is_tried_first_in_alphabetical_order(self):
        response = solve("(B | A) & (C | B)")
        first = response["events"][1]
        self.assertEqual((first["type"], first["variable"], first["value"]),
                         ("decision", "A", True))

    def test_variables_are_case_insensitive(self):
        self.assertEqual(solve("a & !A")["status"], "UNSAT")
        self.assertEqual(solve("x1 | X1")["clauses"], [{"id": "c1", "literals": ["X1"]}])

    def test_always_true_expression(self):
        response = solve("A | !A")
        self.assertEqual((response["status"], response["assignment"], response["clauses"]),
                         ("SAT", {}, []))
        self.assertEqual([e["type"] for e in response["events"]], ["root", "solution"])

    def test_trace_can_be_switched_off(self):
        response = solve("(!A | B) & (!A | !B) & (A | C)", trace=False)
        self.assertEqual(response["status"], "SAT")
        self.assertEqual(response["assignment"], {"A": False, "C": True})
        self.assertEqual(response["events"], [])

    def test_response_is_plain_json(self):
        for expression in ["(!A | B) & (!A | !B) & (A | C)", "A & !A", "A |"]:
            response = solve(expression)
            self.assertEqual(json.loads(json.dumps(response)), response)


class CnfConversion(unittest.TestCase):
    def cnf_of(self, expression):
        return cnf.cnf_text(cnf.to_cnf(parser.parse(expression)))

    def test_rewrites(self):
        self.assertEqual(self.cnf_of("A -> B"), "(!A | B)")
        self.assertEqual(self.cnf_of("A <-> B"), "(!A | B) & (!B | A)")
        self.assertEqual(self.cnf_of("!(A & B)"), "(!A | !B)")
        self.assertEqual(self.cnf_of("!(A | B)"), "!A & !B")
        self.assertEqual(self.cnf_of("!!A"), "A")
        self.assertEqual(self.cnf_of("A | (B & C)"), "(A | B) & (A | C)")

    def test_precedence(self):
        # & binds tighter than |, which binds tighter than ->
        self.assertEqual(parser.parse("A | B & C"), parser.parse("A | (B & C)"))
        self.assertEqual(parser.parse("A & B -> C | D"), parser.parse("(A & B) -> (C | D)"))
        self.assertEqual(parser.parse("A -> B -> C"), parser.parse("A -> (B -> C)"))
        self.assertEqual(parser.parse("!A & B"), parser.parse("(!A) & B"))

    def test_duplicates_and_tautologies_are_removed(self):
        self.assertEqual(self.cnf_of("(A | A) & (A | B | !A) & (B | C) & (C | B)"),
                         "A & (B | C)")

    def test_natural_variable_order(self):
        _, names = cnf.encode(cnf.to_cnf(parser.parse("X10 | X2 | B | A")))
        self.assertEqual([names[i] for i in sorted(names)], ["A", "B", "X2", "X10"])


class Errors(unittest.TestCase):
    def assert_error(self, response, code):
        self.assertEqual(response["status"], "ERROR")
        self.assertEqual(response["error"]["code"], code)
        self.assertTrue(response["error"]["message"])
        self.assertEqual(response["events"], [])
        self.assertIsNone(response["assignment"])

    def test_empty_input(self):
        self.assert_error(solve(""), "EMPTY_INPUT")
        self.assert_error(solve("   "), "EMPTY_INPUT")

    def test_syntax_errors(self):
        for expression in ["A |", "(A | B", "A B", "A & & B", "A | B)", "A $ B", "()", "1A", "A - B"]:
            with self.subTest(expression=expression):
                self.assert_error(solve(expression), "SYNTAX_ERROR")

    def test_error_position(self):
        self.assertEqual(solve("A $ B")["error"]["position"], 2)
        self.assertEqual(solve("A & (B | ")["error"]["position"], 9)

    def test_too_large(self):
        self.assert_error(solve("A" * 1001), "TOO_LARGE")
        self.assert_error(solve(" | ".join(f"X{i}" for i in range(21))), "TOO_LARGE")
        # 8 pairs give 2^8 = 256 clauses after distribution: over the limit of 50.
        self.assert_error(solve(" | ".join(f"(A{i} & B{i})" for i in range(8))), "TOO_LARGE")
        self.assert_error(solve(" <-> ".join(f"X{i}" for i in range(20))), "TOO_LARGE")
        # Reasonable nesting works; absurd nesting is refused without crashing.
        self.assertEqual(solve("(" * 20 + "A" + ")" * 20)["status"], "SAT")
        self.assert_error(solve("(" * 400 + "A" + ")" * 400), "TOO_LARGE")

    def test_invalid_requests(self):
        self.assert_error(solve_request(None), "INVALID_REQUEST")
        self.assert_error(solve_request({}), "INVALID_REQUEST")
        self.assert_error(solve_request({"expression": 42}), "INVALID_REQUEST")
        self.assert_error(solve_request({"expression": "A", "trace": "yes"}), "INVALID_REQUEST")

    def test_hard_instance_and_event_limit(self):
        # Pigeonhole principle: 5 pigeons do not fit in 4 holes. UNSAT, with
        # 20 variables and 45 clauses: the hardest kind of input we accept.
        pigeons, holes = 5, 4
        name = lambda p, h: "ABCDEFGHIJKLMNOPQRST"[p * holes + h]
        parts = ["(" + " | ".join(name(p, h) for h in range(holes)) + ")" for p in range(pigeons)]
        parts += [f"(!{name(p, h)} | !{name(q, h)})" for h in range(holes)
                  for p in range(pigeons) for q in range(p + 1, pigeons)]
        expression = " & ".join(parts)
        response = solve(expression)
        self.assertEqual(response["status"], "UNSAT")
        self.assertGreater(len(response["events"]), 100)
        # With a smaller event limit the same search is stopped cleanly.
        with mock.patch("dpllsat.trace.MAX_EVENTS", 100):
            self.assert_error(solve(expression), "TOO_LARGE")


def random_tree(rng, names, depth):
    if depth == 0 or rng.random() < 0.25:
        return ("var", rng.choice(names))
    kind = rng.choice(["not", "and", "or", "imp", "iff"])
    if kind == "not":
        return ("not", random_tree(rng, names, depth - 1))
    return (kind, random_tree(rng, names, depth - 1), random_tree(rng, names, depth - 1))


def to_text(tree):
    kind = tree[0]
    if kind == "var":
        return tree[1]
    if kind == "not":
        return f"!({to_text(tree[1])})"
    symbol = {"and": "&", "or": "|", "imp": "->", "iff": "<->"}[kind]
    return f"({to_text(tree[1])} {symbol} {to_text(tree[2])})"


class RandomFormulas(unittest.TestCase):
    """Compare the solver with a brute-force truth table on random inputs."""

    def test_against_truth_table(self):
        rng = random.Random(2026)
        names = ["A", "B", "C", "D", "E"]
        solved = {"SAT": 0, "UNSAT": 0}
        for _ in range(600):
            tree = random_tree(rng, names, depth=4)
            text = to_text(tree)
            response = solve(text)
            if response["status"] == "ERROR":
                self.assertEqual(response["error"]["code"], "TOO_LARGE", text)
                continue
            solved[response["status"]] += 1
            truth = [a for a in all_assignments(names) if parser.evaluate(tree, a)]

            # 1. The CNF is equivalent to the original expression.
            clauses = cnf.to_cnf(parser.parse(text))
            for assignment in all_assignments(names):
                self.assertEqual(clauses_hold(clauses, assignment),
                                 parser.evaluate(tree, assignment), text)

            # 2. SAT/UNSAT is right, and the assignment satisfies the ORIGINAL
            #    expression whatever value the unassigned variables take.
            self.assertEqual(response["status"], "SAT" if truth else "UNSAT", text)
            if response["status"] == "SAT":
                for default in (False, True):
                    self.assertTrue(parser.evaluate(tree, response["assignment"], default), text)

            self.check_trace(response, text)
        self.assertGreater(solved["SAT"], 50)
        self.assertGreater(solved["UNSAT"], 10)

    def check_trace(self, response, text):
        events = response["events"]
        clause_ids = {clause["id"] for clause in response["clauses"]}
        self.assertEqual([e["seq"] for e in events], list(range(len(events))), text)
        self.assertEqual(events[0], {"seq": 0, "type": "root", "node_id": "n0", "assignment": {}})
        self.assertEqual(events[-1]["type"], "solution" if response["status"] == "SAT" else "unsat")

        nodes = {"n0"}
        current = "n0"
        latest = {"n0": {}}          # last assignment seen in each node
        for event in events[1:]:
            kind = event["type"]
            if kind == "decision":
                self.assertNotIn(event["node_id"], nodes, text)      # unique node ids
                self.assertEqual(event["parent_id"], current, text)  # valid parent
                nodes.add(event["node_id"])
                expected = dict(latest[current])
                expected[event["variable"]] = event["value"]
                self.assertEqual(event["assignment"], expected, text)
            elif kind == "backtrack":
                self.assertEqual(event["from_node"], current, text)
                self.assertIn(event["node_id"], nodes, text)
                # Back in the parent, the assignment is what it was there.
                self.assertEqual(event["assignment"], latest[event["node_id"]], text)
            else:
                self.assertEqual(event["node_id"], current, text)    # stays in the node
            if "reason_clause" in event:
                self.assertIn(event["reason_clause"], clause_ids, text)
            current = event["node_id"]
            latest[current] = event["assignment"]
        if response["status"] == "SAT":
            self.assertEqual(events[-1]["assignment"], response["assignment"], text)
        else:
            self.assertEqual(events[-1]["node_id"], "n0", text)


if __name__ == "__main__":
    unittest.main()
