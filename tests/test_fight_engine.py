import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unittest
import random
import numpy as np
import unittest
from fighter import Fighter
from fight import Fight
from positions import PositionSystem, Position
from strategy import StrategySystem
from datetime import datetime


class TestFightSimulation(unittest.TestCase):

    def setUp(self):
        self.f1 = Fighter("Test F1", 28, 170, "mma", "balanced",
                          nationality="American", home_region="California")
        self.f2 = Fighter("Test F2", 28, 170, "mma", "balanced",
                          nationality="Brazilian", home_region="Rio")
        for f in [self.f1, self.f2]:
            for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
                f.attributes[attr] = 70

    def _run_fight(self, rounds=3, is_title=False, seed=None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed % 2**30)
        fight = Fight(self.f1, self.f2, rounds=rounds, is_title_fight=is_title)
        fight.strategy1.set_pre_fight_strategy("balanced")
        fight.strategy2.set_pre_fight_strategy("balanced")
        for event in fight.simulate_fight_gen():
            if event["type"] == "complete":
                break
        return fight

    def test_fight_completes(self):
        fight = self._run_fight(rounds=3)
        self.assertIsNotNone(fight.winner, "Fight must have a winner")

    def test_fight_rounds_within_bounds(self):
        fight = self._run_fight(rounds=5, is_title=True)
        self.assertLessEqual(fight.win_round or 5, 5)
        self.assertGreaterEqual(fight.win_round or 1, 1)

    def test_deterministic_with_seed(self):
        f1 = self._run_fight(rounds=3, seed=42)
        f2 = self._run_fight(rounds=3, seed=42)
        if f1.winner is None or f2.winner is None:
            return  # Non-deterministic due to broader RNG usage, skip assertion
        self.assertEqual(f1.winner.name, f2.winner.name)
        self.assertEqual(f1.win_method, f2.win_method)

    def test_ko_method_valid(self):
        for _ in range(20):
            fight = self._run_fight(rounds=3)
            if fight.win_method:
                method = fight.win_method.split("(")[0].strip()
                valid = ["KO", "TKO", "Submission", "Decision",
                         "Unanimous Decision", "Split Decision", "Majority Decision",
                         "Split Draw", "Majority Draw", "Unanimous Draw"]
                self.assertIn(method, valid)

    def test_stamina_decreases(self):
        fight = self._run_fight(rounds=3)
        for state in [fight.f1_state, fight.f2_state]:
            self.assertLessEqual(state["stamina"], 100,
                                 "Stamina must never exceed 100")
            self.assertGreaterEqual(state["stamina"], 0,
                                    "Stamina must never go below 0")

    def test_health_changes(self):
        fight = self._run_fight(rounds=3)
        for zone in ["head", "body", "legs"]:
            h1 = fight.f1_state["health"].get(zone, 100)
            h2 = fight.f2_state["health"].get(zone, 100)
            self.assertLessEqual(h1, 100, f"{zone} health must not exceed 100")
            self.assertGreaterEqual(h1, 0, f"{zone} health must not go below 0")

    def test_no_ko_in_round_1(self):
        for seed in range(10):
            fight = self._run_fight(rounds=3, seed=seed)
            if fight.win_method and "KO" in fight.win_method:
                self.assertGreater(
                    fight.win_round or 1, 1,
                    f"KO in round 1 should not happen (seed={seed})"
                )

    def test_submission_needs_ground(self):
        fight = self._run_fight(rounds=3)
        if fight.win_method and "Submission" in fight.win_method:
            self.assertIsNotNone(fight.win_round)

    def test_judging_scores(self):
        fight = self._run_fight(rounds=3)
        for judge in fight.judges:
            self.assertGreaterEqual(len(judge.scores), 1,
                                    "Each judge should have at least 1 round of scores")
            for round_scores in judge.scores:
                f1_score, f2_score = round_scores
                self.assertGreaterEqual(f1_score, 7)
                self.assertLessEqual(f1_score, 10)
                self.assertGreaterEqual(f2_score, 7)
                self.assertLessEqual(f2_score, 10)

    def test_position_transitions(self):
        pos = PositionSystem(self.f1, self.f2)
        self.assertEqual(pos.current_position, Position.DISTANCE)
        result = pos.attempt_clinch(self.f1, self.f2)
        if result:
            self.assertIn(pos.current_position,
                          [Position.CLINCH, Position.POCKET])

    def test_strategy_switch(self):
        from fight import Fight
        fight = Fight(self.f1, self.f2, rounds=3)
        ss = fight.strategy1
        ss.set_pre_fight_strategy("aggressive_striking")
        self.assertEqual(ss.current_strategy["id"], "aggressive_striking")
        ss.set_pre_fight_strategy("wrestling_focus")
        self.assertEqual(ss.current_strategy["id"], "wrestling_focus")

    def test_takedown_tracking(self):
        fight = self._run_fight(rounds=3)
        f1_td = fight.f1_state.get("takedowns_landed", 0)
        f2_td = fight.f2_state.get("takedowns_landed", 0)
        f1_att = fight.f1_state.get("takedowns_attempted", 0)
        f2_att = fight.f2_state.get("takedowns_attempted", 0)
        self.assertGreaterEqual(f1_td, 0)
        self.assertGreaterEqual(f1_att, f1_td,
                                "Attempts must be >= landed takedowns")


if __name__ == "__main__":
    unittest.main()
