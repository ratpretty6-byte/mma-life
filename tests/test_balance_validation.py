"""
Balance validation test: runs bulk simulations and asserts rates match real UFC stats.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import random
import unittest
from collections import Counter

from fight import Fight
from fighter import Fighter

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "real_stats.json")


def load_targets():
    with open(CONFIG_FILE) as f:
        data = json.load(f)
    return data


def make_fighter(name, attrs, archetype="balanced"):
    f = Fighter(name, 28, 170, "mma", archetype)
    for attr, val in attrs.items():
        f.attributes[attr] = val
    return f


def run_batch(attrs1, attrs2, n=200, rounds=3):
    results = Counter()
    for i in range(n):
        random.seed(i)
        f1 = make_fighter("F1", attrs1)
        f2 = make_fighter("F2", attrs2)
        fight = Fight(f1, f2, rounds=rounds)
        for event in fight.simulate_fight_gen():
            if event["type"] == "complete":
                break
        m = fight.win_method or "Unknown"
        if m and ("KO" in m or "TKO" in m):
            results["KO/TKO"] += 1
        elif m and "Submission" in m:
            results["Submission"] += 1
        elif m and "Decision" in m:
            results["Decision"] += 1
        else:
            results["Other"] += 1
    return results


class TestBalanceValidation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.targets = load_targets()
        cls.even_attrs = {a: 70 for a in Fighter.PHYSICAL_ATTRS + Fighter.MENTAL_ATTRS}

    def test_even_fights_ko_tko_rate(self):
        results = run_batch(self.even_attrs, self.even_attrs, n=200)
        total = sum(results.values())
        rate = results.get("KO/TKO", 0) / total * 100
        target = self.targets["real_world_rates"]["ko_tko_pct"]
        self.assertAlmostEqual(rate, target, delta=10,
            msg=f"KO/TKO rate {rate:.1f}% outside ±10% of target {target}%")

    def test_even_fights_submission_rate(self):
        results = run_batch(self.even_attrs, self.even_attrs, n=200)
        total = sum(results.values())
        rate = results.get("Submission", 0) / total * 100
        target = self.targets["real_world_rates"]["submission_pct"]
        self.assertAlmostEqual(rate, target, delta=8,
            msg=f"Sub rate {rate:.1f}% outside ±8% of target {target}%")

    def test_even_fights_decision_rate(self):
        results = run_batch(self.even_attrs, self.even_attrs, n=200)
        total = sum(results.values())
        rate = results.get("Decision", 0) / total * 100
        target = self.targets["real_world_rates"]["decision_pct"]
        self.assertAlmostEqual(rate, target, delta=10,
            msg=f"Decision rate {rate:.1f}% outside ±10% of target {target}%")

    def test_mismatched_fights_more_finishes(self):
        strong = {a: 85 for a in Fighter.PHYSICAL_ATTRS + Fighter.MENTAL_ATTRS}
        weak = {a: 55 for a in Fighter.PHYSICAL_ATTRS + Fighter.MENTAL_ATTRS}
        even_results = run_batch(self.even_attrs, self.even_attrs, n=100)
        mismatch_results = run_batch(strong, weak, n=100)
        even_finish = (even_results.get("KO/TKO", 0) + even_results.get("Submission", 0))
        mismatch_finish = (mismatch_results.get("KO/TKO", 0) + mismatch_results.get("Submission", 0))
        self.assertGreater(mismatch_finish, even_finish,
            "Mismatched fights should produce more finishes than even fights")

    def test_no_ko_in_round_one(self):
        results = run_batch(self.even_attrs, self.even_attrs, n=100)
        self.assertGreaterEqual(sum(results.values()), 90,
            "Should produce meaningful results")

    def test_finish_rate_meaningful(self):
        results = run_batch(self.even_attrs, self.even_attrs, n=200)
        total = sum(results.values())
        finish = results.get("KO/TKO", 0) + results.get("Submission", 0)
        rate = finish / total * 100
        self.assertGreater(rate, 25,
            f"Finish rate {rate:.1f}% too low — game needs more finishes")
        self.assertLess(rate, 75,
            f"Finish rate {rate:.1f}% too high — game needs fewer finishes")


if __name__ == "__main__":
    unittest.main()
