import itertools
import random
import unittest

from dpllsat import parser
from dpllsat.service import solve_request


def solve(expression, rule_mode="up_only", trace=True):
    return solve_request({
        "expression": expression,
        "rule_mode": rule_mode,
        "trace": trace,
    })


class IndependentRuleModes(unittest.TestCase):
    EXAMPLES = [
        "(A | B) & (!A | B)",
        "A & (!A | B) & (!B | C)",
        "A & !A",
        "(A | B) & (A | !B) & (!A | B) & (!A | !B)",
        "(!A | B) & (!A | !B) & (A | C)",
        "A | !A",
        "(A -> B) & (B -> C) & !(A <-> C)",
    ]

    def test_modes_agree_and_never_emit_the_other_inference_rule(self):
        for expression in self.EXAMPLES:
            with self.subTest(expression=expression):
                up = solve(expression, "up_only")
                pl = solve(expression, "pl_only")
                self.assertEqual(up["status"], pl["status"])
                self.assertNotEqual(up["status"], "ERROR")
                self.assertFalse(any(e["type"] == "pure_literal" for e in up["events"]))
                self.assertFalse(any(e["type"] == "unit_propagation" for e in pl["events"]))

    def test_omitted_mode_is_exactly_up_only(self):
        payload = {"expression": self.EXAMPLES[0], "trace": True}
        self.assertEqual(solve_request(payload), solve(self.EXAMPLES[0], "up_only"))

    def test_invalid_mode_is_a_structured_request_error(self):
        response = solve_request({"expression": "A", "rule_mode": "combined"})
        self.assertEqual(response["status"], "ERROR")
        self.assertEqual(response["error"]["code"], "INVALID_REQUEST")

    def test_pure_literal_polarity_and_repeated_elimination(self):
        positive = solve("(A | B) & (!A | B)", "pl_only")
        negative = solve("(A | !B) & (!A | !B)", "pl_only")
        self.assertEqual(positive["events"][1]["type"], "pure_literal")
        self.assertEqual((positive["events"][1]["variable"], positive["events"][1]["value"]),
                         ("B", True))
        self.assertEqual((negative["events"][1]["variable"], negative["events"][1]["value"]),
                         ("B", False))
        chain = solve("A & (!A | B) & (!B | C)", "pl_only")
        pure_events = [e for e in chain["events"] if e["type"] == "pure_literal"]
        self.assertEqual(len({e["variable"] for e in pure_events}), len(pure_events))
        self.assertTrue(all("reason_clause" not in e for e in pure_events))

    def test_pl_only_branches_and_backtracks_without_up(self):
        response = solve("A & !A", "pl_only")
        kinds = [event["type"] for event in response["events"]]
        self.assertEqual(response["status"], "UNSAT")
        self.assertIn("decision", kinds)
        self.assertIn("backtrack", kinds)
        self.assertNotIn("unit_propagation", kinds)

    def test_trace_false_solves_both_modes_without_events(self):
        for mode in ("up_only", "pl_only"):
            with self.subTest(mode=mode):
                response = solve("A & (!A | B)", mode, trace=False)
                self.assertEqual(response["status"], "SAT")
                self.assertEqual(response["events"], [])

    def test_small_random_formulas_match_truth_tables_in_both_modes(self):
        rng = random.Random(731)
        names = ("A", "B", "C")
        for _ in range(100):
            clauses = []
            for _ in range(rng.randint(1, 5)):
                literals = []
                for name in rng.sample(names, rng.randint(1, 3)):
                    literals.append(("!" if rng.choice((False, True)) else "") + name)
                clauses.append("(" + " | ".join(literals) + ")")
            expression = " & ".join(clauses)
            tree = parser.parse(expression)
            expected = any(
                parser.evaluate(tree, dict(zip(names, values)))
                for values in itertools.product((False, True), repeat=len(names))
            )
            for mode in ("up_only", "pl_only"):
                response = solve(expression, mode)
                self.assertNotEqual(response["status"], "ERROR", expression)
                self.assertEqual(response["status"] == "SAT", expected, expression)


if __name__ == "__main__":
    unittest.main()
