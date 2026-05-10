import random
from typing import Dict, Optional, List, Generator
from fighter import Fighter
from positions import PositionSystem, Position
from strategy import StrategySystem, STRATEGIES
from commentary import CommentaryEngine
import utils

class Judge:
    def __init__(self, name: str, bias: float = 0.0):
        self.name = name
        self.bias = bias
        self.scores = []

    def score_round(self, f1_damage: float, f2_damage: float, f1_control: float, f2_control: float,
                    f1_agg: float, f2_agg: float, knockdowns_f1: int, knockdowns_f2: int) -> tuple:
        f1_score = f1_damage * 0.4 + f1_control * 0.3 + f1_agg * 0.3 + knockdowns_f1 * 2
        f2_score = f2_damage * 0.4 + f2_control * 0.3 + f2_agg * 0.3 + knockdowns_f2 * 2

        f1_score += self.bias * random.uniform(-1, 1)
        f2_score += self.bias * random.uniform(-1, 1)

        diff = f1_score - f2_score
        if abs(diff) < 0.5:
            f1_round = 10
            f2_round = 10
        elif diff > 0:
            f1_round = 10
            f2_round = 9
            if diff > 4:
                f2_round = 8
            if diff > 6:
                f2_round = 7
        else:
            f1_round = 9
            f2_round = 10
            diff = abs(diff)
            if diff > 4:
                f1_round = 8
            if diff > 6:
                f1_round = 7

        f1_round = max(7, min(10, f1_round))
        f2_round = max(7, min(10, f2_round))
        self.scores.append((f1_round, f2_round))
        return (f1_round, f2_round)

class Fight:
    def __init__(self, fighter1: Fighter, fighter2: Fighter, rounds: int = 3, is_title_fight: bool = False, context: Optional[Dict] = None):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.rounds = 5 if is_title_fight else rounds
        self.is_title_fight = is_title_fight
        self.context = context or {}

        self.position_system = PositionSystem(fighter1, fighter2)
        self.commentary = CommentaryEngine()
        self.strategy1 = StrategySystem(fighter1)
        self.strategy2 = StrategySystem(fighter2)

        self.f1_state = self._init_fighter_state()
        self.f2_state = self._init_fighter_state()

        self.current_round = 1
        self.fight_log = []
        self.winner = None
        self.loser = None
        self.win_method = None
        self.win_round = None

        self.judges = [
            Judge("Judge A", bias=0.5),
            Judge("Judge B", bias=0.0),
            Judge("Judge C", bias=-0.5),
        ]

        self.f1_round_scores = []
        self.f2_round_scores = []
        self.f1_knockdowns_this_round = 0
        self.f2_knockdowns_this_round = 0
        self.f1_control_time = 0
        self.f2_control_time = 0
        self.f1_actions_landed = 0
        self.f2_actions_landed = 0

    def _init_fighter_state(self) -> Dict:
        return {
            "health": {"head": 100, "body": 100, "legs": 100},
            "stamina": 100,
            "cuts": [],
            "swelling": 0,
            "leg_damage": 0,
            "knockdown": False,
            "knockdown_count": 0,
            "recovering": False,
            "accumulated_damage": 0,
            "rounds_stamina_burn": [],
            "rounds_damage_dealt": [],
            "fatigue_level": 0.0,
        }

    def simulate_fight_gen(self, speed: float = 1.0) -> Generator:
        buildup_parts = self.commentary.generate_pre_fight_buildup(self.fighter1, self.fighter2, self.context)
        for part in buildup_parts:
            yield {"type": "pre_fight", "text": part}

        yield {"type": "walkout", "text": self.commentary.generate_walkout(self.fighter1, self.is_title_fight)}
        yield {"type": "walkout", "text": self.commentary.generate_walkout(self.fighter2, False)}

        for round_num in range(1, self.rounds + 1):
            self.current_round = round_num
            self.f1_knockdowns_this_round = 0
            self.f2_knockdowns_this_round = 0
            self.f1_control_time = 0
            self.f2_control_time = 0
            self.f1_actions_landed = 0
            self.f2_actions_landed = 0

            round_phase = "feeling_out"
            total_actions = random.randint(25, 40)

            yield {"type": "round_start", "round": round_num,
                   "text": self.commentary.generate_round_start(round_num, self.fighter1, self.fighter2)}

            for action_idx in range(total_actions):
                if self.winner:
                    break

                phase_progress = action_idx / max(1, total_actions)
                if phase_progress < 0.15:
                    round_phase = "feeling_out"
                elif phase_progress > 0.75:
                    round_phase = "desperation"
                else:
                    round_phase = "exchanges"

                self._simulate_action(phase=round_phase)

                cuts_texts = []
                swelling_texts = []
                leg_texts = []

                f1_cuts = self.f1_state.get("cuts", [])
                if f1_cuts and random.random() < 0.15:
                    cuts_texts.append(self.commentary.generate_cut_commentary(self.fighter1))
                f2_cuts = self.f2_state.get("cuts", [])
                if f2_cuts and random.random() < 0.15:
                    cuts_texts.append(self.commentary.generate_cut_commentary(self.fighter2))

                if self.f1_state["swelling"] > 25 and random.random() < 0.1:
                    swelling_texts.append(self.commentary.generate_swelling_commentary(self.fighter1))
                if self.f2_state["swelling"] > 25 and random.random() < 0.1:
                    swelling_texts.append(self.commentary.generate_swelling_commentary(self.fighter2))

                if self.f1_state["leg_damage"] > 25 and random.random() < 0.1:
                    leg_texts.append(self.commentary.generate_leg_damage_commentary(self.fighter1))
                if self.f2_state["leg_damage"] > 25 and random.random() < 0.1:
                    leg_texts.append(self.commentary.generate_leg_damage_commentary(self.fighter2))

                if self.fight_log:
                    last = self.fight_log[-1]
                    yield {"type": "action", "text": last, "round": round_num,
                           "f1_health": self.f1_state["health"]["head"],
                           "f2_health": self.f2_state["health"]["head"]}

                    for ct in cuts_texts:
                        yield {"type": "damage", "text": ct}
                    for st in swelling_texts:
                        yield {"type": "damage", "text": st}
                    for lt in leg_texts:
                        yield {"type": "damage", "text": lt}

                if action_idx % 8 == 7 and round_num > 1 and not self.winner:
                    self._check_ai_mid_round()

            if self.winner:
                if "KO" in self.win_method or "TKO" in self.win_method:
                    yield {"type": "knockout", "text": self.commentary.generate_knockout_commentary(self.winner),
                           "winner": self.winner.name, "method": self.win_method, "round": self.current_round}
                elif "Submission" in self.win_method:
                    sub_name = self.win_method.replace("Submission (", "").replace(")", "")
                    sub_text = f"{self.winner.name} sinks in the {sub_name}!"
                    yield {"type": "submission", "text": sub_text,
                           "winner": self.winner.name, "method": self.win_method, "round": self.current_round}
                yield {"type": "post_fight",
                       "text": self.commentary.generate_post_fight(self.winner, self.win_method, self.current_round, False, self.loser)}
                if self.winner and self.loser:
                    win_reaction = self.commentary.generate_post_fight_reaction(self.winner, self.loser)
                    if win_reaction:
                        yield {"type": "post_fight_reaction", "text": win_reaction}
                    loss_reaction = self.commentary.generate_post_fight_loss(self.loser, self.winner)
                    if loss_reaction:
                        yield {"type": "post_fight_reaction", "text": loss_reaction}
                return

            doctor_stoppage = self._check_doctor_stoppage()
            if doctor_stoppage:
                yield {"type": "action", "text": doctor_stoppage, "round": round_num,
                       "f1_health": self.f1_state["health"]["head"],
                       "f2_health": self.f2_state["health"]["head"]}
                yield {"type": "knockout" if "TKO" in self.win_method else "damage",
                       "text": f"Doctor stoppage! {self.winner.name} wins by {self.win_method}!",
                       "winner": self.winner.name, "method": self.win_method, "round": self.current_round}
                yield {"type": "post_fight",
                       "text": self.commentary.generate_post_fight(self.winner, self.win_method, self.current_round, False, self.loser)}
                return

            round_desc = self._describe_round(round_num)
            round_summary = self.commentary.generate_round_summary(self.fighter1, self.fighter2)
            yield {"type": "round_end", "round": round_num,
                   "text": self.commentary.generate_round_end(round_num, self.fighter1, self.fighter2, round_desc)}
            if round_summary:
                yield {"type": "round_summary", "text": round_summary, "round": round_num}

            for judge in self.judges:
                f1_score, f2_score = judge.score_round(
                    self._calc_damage_score(self.f1_state, self.f2_state),
                    self._calc_damage_score(self.f2_state, self.f1_state),
                    self.f1_control_time / max(1, self.f1_control_time + self.f2_control_time),
                    self.f2_control_time / max(1, self.f1_control_time + self.f2_control_time),
                    self.f1_actions_landed / max(1, self.f1_actions_landed + self.f2_actions_landed),
                    self.f2_actions_landed / max(1, self.f1_actions_landed + self.f2_actions_landed),
                    self.f1_knockdowns_this_round, self.f2_knockdowns_this_round
                )

            r_idx = len(self.judges[0].scores) - 1
            self.f1_round_scores.append([j.scores[r_idx][0] for j in self.judges])
            self.f2_round_scores.append([j.scores[r_idx][1] for j in self.judges])

            f1_avg = sum(j.scores[-1][0] for j in self.judges) / 3.0
            f2_avg = sum(j.scores[-1][1] for j in self.judges) / 3.0
            f1_r = round(f1_avg)
            f2_r = round(f2_avg)
            score_text = f"{f1_r}-{f2_r}"
            yield {"type": "score_update", "round": round_num, "score": score_text}

            cardio1 = self.fighter1.get_effective_attribute("cardio", self.f1_state["fatigue_level"])
            cardio2 = self.fighter2.get_effective_attribute("cardio", self.f2_state["fatigue_level"])
            stamina_recovery1 = int(20 + (cardio1 / 100) * 20)
            stamina_recovery2 = int(20 + (cardio2 / 100) * 20)
            self.f1_state["stamina"] = min(100, self.f1_state["stamina"] + stamina_recovery1)
            self.f2_state["stamina"] = min(100, self.f2_state["stamina"] + stamina_recovery2)
            self.f1_state["fatigue_level"] = 1.0 - (self.f1_state["stamina"] / 100)
            self.f2_state["fatigue_level"] = 1.0 - (self.f2_state["stamina"] / 100)

            self.f1_state["rounds_stamina_burn"].append(100 - self.f1_state["stamina"])
            self.f2_state["rounds_stamina_burn"].append(100 - self.f2_state["stamina"])

            self._apply_cutman()

            if round_num < self.rounds and not self.winner:
                f1_cumulative = sum(sum(j.scores[r][0] for j in self.judges) / 3.0 for r in range(len(self.judges[0].scores)))
                f2_cumulative = sum(sum(j.scores[r][1] for j in self.judges) / 3.0 for r in range(len(self.judges[0].scores)))
                needs_finish = f2_cumulative > f1_cumulative + 2

                score_detail = f"{self.fighter1.name}: {f1_cumulative:.0f}, {self.fighter2.name}: {f2_cumulative:.0f}"
                corner_text = self.commentary.generate_between_round(self.fighter1, round_num, needs_finish, score_detail)
                yield {"type": "between_round", "text": corner_text, "round": round_num,
                       "needs_finish": needs_finish, "score_detail": score_detail}

                ai_new_strat = StrategySystem.pick_ai_strategy(
                    self.fighter2, self.fighter1,
                    [int(sum(j.scores[r][1] - j.scores[r][0] for j in self.judges) / 3.0)
                     for r in range(len(self.judges[0].scores))],
                    round_num, self.rounds, self.strategy2.current_strategy
                )
                self.strategy2.adjust_strategy(ai_new_strat)

                yield {"type": "strategy_prompt", "round": round_num,
                       "f1_stamina": self.f1_state["stamina"],
                       "f2_stamina": self.f2_state["stamina"],
                       "score_detail": score_detail}

            if round_num < self.rounds:
                self.f1_state["knockdown"] = False
                self.f2_state["knockdown"] = False
                self.f1_state["recovering"] = False
                self.f2_state["recovering"] = False

        if not self.winner:
            self._determine_decision()
            yield {"type": "decision",
                   "text": self.commentary.generate_post_fight(self.winner, self.win_method, None, True),
                   "winner": self.winner.name if self.winner else "Draw",
                   "method": self.win_method, "details": self._get_decision_details()}

        yield {"type": "complete", "winner": self.winner.name if self.winner else "Draw",
               "method": self.win_method, "round": self.win_round,
               "f1_health": self.f1_state["health"],
               "f2_health": self.f2_state["health"]}

    def _calc_damage_score(self, state: Dict, opponent_state: Dict) -> float:
        dealt = (100 - opponent_state["health"]["head"]) * 0.6 + (100 - opponent_state["health"]["body"]) * 0.25 + (100 - opponent_state["health"]["legs"]) * 0.15
        return dealt / 100.0

    def _describe_round(self, round_num: int) -> str:
        if self.winner:
            return f"{self.winner.name} ends it!"
        f1_total = sum(j.scores[-1][0] for j in self.judges) / 3.0 if self.judges[0].scores else 10
        f2_total = sum(j.scores[-1][1] for j in self.judges) / 3.0 if self.judges[0].scores else 10
        if f1_total > f2_total:
            return f"{self.fighter1.name} takes the round"
        elif f2_total > f1_total:
            return f"{self.fighter2.name} takes the round"
        return "close round"

    def _get_decision_details(self) -> str:
        f1_total = sum(sum(j.scores[r][0] for j in self.judges) for r in range(len(self.judges[0].scores)))
        f2_total = sum(sum(j.scores[r][1] for j in self.judges) for r in range(len(self.judges[0].scores)))
        return f"Total: {self.fighter1.name} {f1_total:.0f} - {self.fighter2.name} {f2_total:.0f}"

    def _apply_cutman(self):
        for fighter, state in [(self.fighter1, self.f1_state), (self.fighter2, self.f2_state)]:
            cuts = state.get("cuts", [])
            if cuts:
                for cut in cuts:
                    if state["accumulated_damage"] > 30:
                        cut["severity"] = min(1.0, cut["severity"] + random.uniform(0.0, 0.1))
                    else:
                        cut["severity"] = max(0.1, cut["severity"] - random.uniform(0.1, 0.2))
                state["cuts"] = [c for c in cuts if c["severity"] > 0.1]
            if state["accumulated_damage"] > 30:
                state["swelling"] = min(100, state["swelling"] + random.randint(1, 4))
            else:
                state["swelling"] = max(0, state["swelling"] - random.randint(1, 5))
            state["leg_damage"] = max(0, state["leg_damage"] - random.randint(1, 4))

    def _check_ai_mid_round(self):
        f1_total = sum(sum(j.scores[r][0] for j in self.judges) for r in range(len(self.judges[0].scores))) if self.judges[0].scores else 0
        f2_total = sum(sum(j.scores[r][1] for j in self.judges) for r in range(len(self.judges[0].scores))) if self.judges[0].scores else 0
        round_diffs = [int(sum(j.scores[r][1] - j.scores[r][0] for j in self.judges) / 3.0) for r in range(len(self.judges[0].scores))]
        new_strat = StrategySystem.pick_ai_strategy(self.fighter2, self.fighter1, round_diffs, self.current_round, self.rounds, self.strategy2.current_strategy)
        self.strategy2.adjust_strategy(new_strat)

    def _check_doctor_stoppage(self):
        for fighter, state in [(self.fighter1, self.f1_state), (self.fighter2, self.f2_state)]:
            if state["swelling"] > 70 and random.random() < 0.3:
                self.winner = self.fighter2 if fighter == self.fighter1 else self.fighter1
                self.loser = fighter
                self.win_method = "TKO (Doctor Stoppage)"
                self.win_round = self.current_round
                return f"The doctor checks {fighter.name}'s badly swollen eye... and waves it off!"
            if len(state.get("cuts", [])) > 2 and random.random() < 0.2:
                worst = max(state["cuts"], key=lambda c: c["severity"])
                if worst["severity"] > 0.7:
                    self.winner = self.fighter2 if fighter == self.fighter1 else self.fighter1
                    self.loser = fighter
                    self.win_method = "TKO (Doctor Stoppage)"
                    self.win_round = self.current_round
                    return f"The doctor checks {fighter.name}'s deep gash... the fight is stopped!"
        return None

    def _simulate_action(self, phase="exchanges"):
        attacker, defender, atk_state, def_state, atk_strategy = (
            (self.fighter1, self.fighter2, self.f1_state, self.f2_state, self.strategy1)
            if random.choice([True, False]) else
            (self.fighter2, self.fighter1, self.f2_state, self.f1_state, self.strategy2)
        )

        fatigue = 1.0 - (atk_state["stamina"] / 100)
        position = self.position_system.current_position

        action_weights = atk_strategy.get_action_weights()
        if position == Position.STANDING:
            if random.random() < 0.08:
                self._check_cut_progression(atk_state, def_state)
                self._check_swelling_progression(atk_state, def_state)
                self._check_leg_damage_effect(defender, def_state)

            if phase == "feeling_out":
                strike_chance = action_weights.get("strike", 0.7) * 0.7
                if random.random() < 0.25:
                    self.fight_log.append(f"{attacker.name} circles, measuring distance.")
                    return
            elif phase == "desperation":
                strike_chance = action_weights.get("strike", 0.7) * 1.2
            else:
                strike_chance = action_weights.get("strike", 0.7)

            if random.random() < strike_chance:
                self._simulate_strike(attacker, defender, atk_state, def_state, fatigue, atk_strategy, phase)
            elif random.random() < action_weights.get("takedown", 0.15) / (action_weights.get("takedown", 0.15) + action_weights.get("clinch", 0.15) + 0.001):
                self._simulate_takedown(attacker, defender, fatigue, atk_strategy)
            else:
                self._simulate_clinch_attempt(attacker, defender, fatigue, atk_strategy)
        elif position == Position.CLINCH:
            if random.random() < 0.6:
                self._simulate_clinch_strike(attacker, defender, atk_state, def_state, fatigue, atk_strategy)
            else:
                self._simulate_clinch_break(attacker, defender, fatigue, atk_strategy)
        elif position == Position.GROUND_TOP:
            top = self.position_system.top_fighter
            if top == self.fighter1:
                actual_attacker, actual_defender = self.fighter1, self.fighter2
                actual_atk_state, actual_def_state = self.f1_state, self.f2_state
                actual_strategy = self.strategy1
            else:
                actual_attacker, actual_defender = self.fighter2, self.fighter1
                actual_atk_state, actual_def_state = self.f2_state, self.f1_state
                actual_strategy = self.strategy2
            sub_chance = action_weights.get("submission", 0.3) if actual_strategy.current_strategy else 0.3
            if random.random() < sub_chance:
                self._simulate_submission_attempt(actual_attacker, actual_defender, fatigue, actual_strategy)
            else:
                self._simulate_ground_strike(actual_attacker, actual_defender, actual_atk_state, actual_def_state, fatigue, actual_strategy)
        elif position == Position.GROUND_BOTTOM:
            bottom = self.position_system.top_fighter
            if bottom == self.fighter1:
                actual_bottom = self.fighter2
                actual_top = self.fighter1
            else:
                actual_bottom = self.fighter1
                actual_top = self.fighter2
            bottom_strategy = self.strategy2 if actual_bottom == self.fighter2 else self.strategy1
            if random.random() < 0.5:
                self._simulate_sweep(actual_bottom, actual_top, fatigue, bottom_strategy)
            else:
                self._simulate_ground_stand_up(actual_bottom, actual_top, fatigue, bottom_strategy)

        if position in (Position.GROUND_TOP, Position.GROUND_BOTTOM):
            if self.position_system.top_fighter == self.fighter1:
                self.f1_control_time += 1
            else:
                self.f2_control_time += 1

        phase_stamina_mod = 0.5 if phase == "feeling_out" else (1.5 if phase == "desperation" else 1.0)
        base_drain = random.randint(1, 3)
        atk_state["stamina"] = max(0, atk_state["stamina"] - int(base_drain * phase_stamina_mod))
        if atk_strategy.current_strategy:
            cd = atk_strategy.current_strategy.get("modifiers", {}).get("cardio_drain", 1.0)
            if cd > 1:
                atk_state["stamina"] = max(0, atk_state["stamina"] - int((cd - 1.0) * 5 * phase_stamina_mod))

    def _get_mod(self, attr: str, strategy: StrategySystem) -> float:
        return strategy.get_modifier_for_attr(attr)

    def _simulate_strike(self, attacker, defender, atk_state, def_state, fatigue, strategy, phase="exchanges"):
        strike_type = random.choice(["jab", "cross", "hook", "uppercut", "kick"])
        target = random.choice(["head", "body", "legs"])

        modifiers = strategy.get_modifiers()
        sp_mod = modifiers.get("striking_power", 1.0)
        sa_mod = modifiers.get("striking_accuracy", 1.0)
        hs_mod = modifiers.get("hand_speed", 1.0)

        power_attr = f"{'kick' if 'kick' in strike_type else 'striking'}_power"
        accuracy_attr = f"{'kick' if 'kick' in strike_type else 'striking'}_accuracy"

        phase_power_mod = 0.7 if phase == "feeling_out" else (1.3 if phase == "desperation" else 1.0)
        phase_accuracy_mod = 0.8 if phase == "feeling_out" else (1.1 if phase == "desperation" else 1.0)

        power = attacker.get_effective_attribute(power_attr, fatigue) * sp_mod * phase_power_mod
        accuracy = attacker.get_effective_attribute(accuracy_attr, fatigue) * sa_mod * hs_mod * phase_accuracy_mod
        durability = defender.get_effective_attribute("durability", 1.0 - (def_state["stamina"] / 100))

        if utils.random_roll(1, 100) <= int(accuracy):
            damage = max(1, (power * 0.5) - (durability * 0.3))
            old_head = def_state["health"]["head"]
            def_state["health"][target] = max(0, def_state["health"][target] - damage)
            def_state["accumulated_damage"] += damage
            if attacker == self.fighter1:
                self.f1_state["rounds_damage_dealt"].append(damage)
            else:
                self.f2_state["rounds_damage_dealt"].append(damage)
            self.fight_log.append(self.commentary.generate_strike_commentary(attacker, defender, strike_type, target, self.position_system.current_position))

            if attacker == self.fighter1:
                self.f1_actions_landed += 1
            else:
                self.f2_actions_landed += 1

            if target == "head":
                if random.random() < 0.02 * (1 - durability / 100):
                    cut = {"severity": random.uniform(0.2, 0.5)}
                    def_state.setdefault("cuts", []).append(cut)
                def_state["swelling"] = min(100, def_state["swelling"] + damage * 0.3)

                if def_state["health"]["head"] <= 0 and old_head > 0:
                    self.fight_log.append(self.commentary.generate_knockdown_commentary(defender))
                    def_state["knockdown"] = True
                    def_state["knockdown_count"] += 1
                    if attacker == self.fighter1:
                        self.f1_knockdowns_this_round += 1
                    else:
                        self.f2_knockdowns_this_round += 1

                    heart = defender.get_effective_attribute("heart", fatigue)
                    recovery_chance = heart * 0.5 + def_state["stamina"] * 0.2
                    if utils.random_roll(1, 100) > int(recovery_chance):
                        self.winner = attacker
                        self.loser = defender
                        self.win_method = "KO"
                        self.win_round = self.current_round
                        self.fight_log.append(f"{defender.name} is out! It's over!")
                    else:
                        self.fight_log.append(self.commentary.generate_recovery_commentary(defender))
                        def_state["recovering"] = True

            if target == "legs":
                def_state["leg_damage"] = min(100, def_state["leg_damage"] + damage * 0.5)

            if target == "body" and random.random() < 0.3:
                def_state["stamina"] = max(0, def_state["stamina"] - damage * 0.2)
        else:
            self.fight_log.append(f"{attacker.name} misses with a {strike_type}.")

    def _check_cut_progression(self, atk_state, def_state):
        for cut in def_state.get("cuts", []):
            if random.random() < 0.1:
                cut["severity"] = min(1.0, cut["severity"] + 0.05)

    def _check_swelling_progression(self, atk_state, def_state):
        if def_state["swelling"] > 0 and random.random() < 0.15:
            def_state["swelling"] = min(100, def_state["swelling"] + 2)

    def _check_leg_damage_effect(self, defender_fighter, def_state):
        if def_state["leg_damage"] > 40 and random.random() < 0.1:
            self.fight_log.append(f"{defender_fighter.name}'s leg is giving out!")

    def _simulate_takedown(self, attacker, defender, fatigue, strategy):
        td_mod = self._get_mod("takedown_power", strategy)
        tda_mod = self._get_mod("takedown_accuracy", strategy)
        wd_mod = self._get_mod("wrestling_defense", strategy)

        at_attrs = attacker.attributes
        temp_power = at_attrs.get("takedown_power", 50) * td_mod
        temp_accuracy = at_attrs.get("takedown_accuracy", 50) * tda_mod

        attacker.takedown_power_temp = temp_power
        attacker.takedown_accuracy_temp = temp_accuracy

        defender_attrs = defender.attributes
        defender.wrestling_defense_temp = defender_attrs.get("wrestling_defense", 50) * wd_mod

        leg_penalty = max(0, (100 - self._get_opponent_state(defender)["leg_damage"]) / 100.0)
        attacker.takedown_power_temp *= leg_penalty

        success = self.position_system.attempt_takedown(attacker, defender, fatigue)
        text = self.commentary.generate_takedown_commentary(attacker, defender, success)
        self.fight_log.append(text)

        if success:
            if attacker == self.fighter1:
                self.f1_control_time += 2
            else:
                self.f2_control_time += 2

    def _get_opponent_state(self, fighter):
        return self.f2_state if fighter == self.fighter1 else self.f1_state

    def _simulate_clinch_attempt(self, attacker, defender, fatigue, strategy):
        cc_mod = self._get_mod("clinch_control", strategy)
        attacker.clinch_control_temp = attacker.attributes.get("clinch_control", 50) * cc_mod
        success = self.position_system.attempt_clinch(attacker, defender, fatigue)
        if success:
            text = self.commentary.generate_clinch_commentary(attacker, defender, "enter")
            self.fight_log.append(text)

    def _simulate_clinch_strike(self, attacker, defender, atk_state, def_state, fatigue, strategy):
        strike_type = random.choice(["knee", "elbow"])
        target = random.choice(["head", "body"])
        sp_mod = self._get_mod("striking_power", strategy)
        power = attacker.get_effective_attribute("striking_power", fatigue) * sp_mod
        durability = defender.get_effective_attribute("durability", 1.0 - (def_state["stamina"] / 100))
        damage = max(1, (power * 0.4) - (durability * 0.2))
        def_state["health"][target] = max(0, def_state["health"][target] - damage)
        def_state["accumulated_damage"] += damage

        if target == "head" and random.random() < 0.03:
            def_state.setdefault("cuts", []).append({"severity": random.uniform(0.3, 0.6)})

        text = self.commentary.generate_strike_commentary(attacker, defender, strike_type, target, Position.CLINCH)
        self.fight_log.append(text)

        if attacker == self.fighter1:
            self.f1_actions_landed += 1
        else:
            self.f2_actions_landed += 1

    def _simulate_clinch_break(self, attacker, defender, fatigue, strategy):
        success = self.position_system.break_clinch(attacker, defender, fatigue)
        if success:
            text = self.commentary.generate_clinch_commentary(attacker, defender, "break")
            self.fight_log.append(text)

    def _simulate_ground_strike(self, attacker, defender, atk_state, def_state, fatigue, strategy):
        strike_type = random.choice(["hammerfist", "elbow", "punch"])
        target = random.choice(["head", "body"])
        sp_mod = self._get_mod("striking_power", strategy)
        power = attacker.get_effective_attribute("striking_power", fatigue) * sp_mod
        durability = defender.get_effective_attribute("durability", 1.0 - (def_state["stamina"] / 100))
        tc_mod = self._get_mod("top_control", strategy)
        top_bonus = 1.0 + (tc_mod - 1.0) * 0.5

        damage = max(1, (power * 0.3 * top_bonus) - (durability * 0.15))
        def_state["health"][target] = max(0, def_state["health"][target] - damage)
        def_state["accumulated_damage"] += damage
        text = self.commentary.generate_strike_commentary(attacker, defender, strike_type, target, Position.GROUND_TOP)
        self.fight_log.append(text)

        if attacker == self.fighter1:
            self.f1_actions_landed += 1
        else:
            self.f2_actions_landed += 1

        if def_state["health"]["head"] <= 0:
            self.winner = attacker
            self.loser = defender
            self.win_method = "TKO (Ground Strikes)"
            self.win_round = self.current_round
            self.fight_log.append(f"The referee steps in! {defender.name} can't defend themselves!")

    def _simulate_submission_attempt(self, attacker, defender, fatigue, strategy):
        submission = random.choice(["armbar", "rear_naked_choke", "triangle", "guillotine", "kimura", "d'arce"])
        so_mod = self._get_mod("submission_offense", strategy)
        sd_mod = self._get_mod("submission_defense", strategy)

        sub_off = attacker.get_effective_attribute("submission_offense", fatigue) * so_mod
        sub_def = defender.get_effective_attribute("submission_defense", fatigue) * sd_mod

        self.fight_log.append(self.commentary.generate_ground_commentary("submission_attempt", attacker=attacker.name, submission=submission))

        success_chance = max(5, min(60, sub_off * 0.6 - sub_def * 0.4))
        if utils.random_roll(1, 100) <= int(success_chance):
            self.fight_log.append(self.commentary.generate_ground_commentary("submission_tap", attacker=attacker.name, defender=defender.name, submission=submission))
            self.winner = attacker
            self.loser = defender
            self.win_method = f"Submission ({submission})"
            self.win_round = self.current_round
        else:
            self.fight_log.append(self.commentary.generate_ground_commentary("submission_defend", attacker=attacker.name, defender=defender.name, submission=submission))

    def _simulate_sweep(self, attacker, defender, fatigue, strategy):
        success = self.position_system.sweep_from_bottom(attacker, defender, fatigue)
        if success:
            text = self.commentary.generate_ground_commentary("sweep", bottom=attacker.name, top=defender.name)
            self.fight_log.append(text)
            if attacker == self.fighter1:
                self.f1_control_time += 3
            else:
                self.f2_control_time += 3

    def _simulate_ground_stand_up(self, attacker, defender, fatigue, strategy):
        success = self.position_system.stand_up_from_bottom(attacker, defender, fatigue)
        if success:
            text = self.commentary.generate_ground_commentary("stand_up", fighter=attacker.name)
            self.fight_log.append(text)

    def _determine_decision(self):
        f1_total = sum(sum(j.scores[r][0] for j in self.judges) for r in range(len(self.judges[0].scores)))
        f2_total = sum(sum(j.scores[r][1] for j in self.judges) for r in range(len(self.judges[0].scores)))

        unanimous = all(
            sum(j.scores[r][0] for r in range(len(j.scores))) > sum(j.scores[r][1] for r in range(len(j.scores)))
            for j in self.judges
        ) or all(
            sum(j.scores[r][1] for r in range(len(j.scores))) > sum(j.scores[r][0] for r in range(len(j.scores)))
            for j in self.judges
        )

        if f1_total > f2_total:
            self.winner = self.fighter1
            self.loser = self.fighter2
            self.win_method = "Decision (Unanimous)" if unanimous else "Decision (Split)"
        elif f2_total > f1_total:
            self.winner = self.fighter2
            self.loser = self.fighter1
            self.win_method = "Decision (Unanimous)" if unanimous else "Decision (Split)"
        else:
            self.winner = None
            self.loser = None
            self.win_method = "Draw"

    def _generate_result(self) -> Dict:
        return {
            "winner": self.winner.name if self.winner else "Draw",
            "method": self.win_method,
            "round": self.win_round,
            "log": self.fight_log
        }

    def simulate_full(self) -> Dict:
        gen = self.simulate_fight_gen(speed=0)
        try:
            while True:
                event = next(gen)
                if event["type"] == "strategy_prompt":
                    self.strategy1.adjust_strategy(
                        StrategySystem.pick_ai_strategy(
                            self.fighter1, self.fighter2,
                            [int(sum(j.scores[r][0] - j.scores[r][1] for j in self.judges) / 3.0)
                             for r in range(len(self.judges[0].scores))],
                            self.current_round, self.rounds, self.strategy1.current_strategy
                        )
                    )
                    self.strategy2.adjust_strategy(
                        StrategySystem.pick_ai_strategy(
                            self.fighter2, self.fighter1,
                            [int(sum(j.scores[r][1] - j.scores[r][0] for j in self.judges) / 3.0)
                             for r in range(len(self.judges[0].scores))],
                            self.current_round, self.rounds, self.strategy2.current_strategy
                        )
                    )
        except StopIteration:
            pass
        return self._generate_result()

    def start_web_fight(self):
        self._web_gen = self.simulate_fight_gen(speed=0)
        return self.advance_web_fight()

    def advance_web_fight(self):
        events = []
        while True:
            try:
                event = next(self._web_gen)
                events.append(event)
                if event["type"] == "strategy_prompt":
                    return {"status": "strategy_needed", "events": events, "data": event}
            except StopIteration:
                return {"status": "complete", "events": events}

    def submit_strategy_web(self, strategy_id: str):
        if strategy_id:
            self.strategy1.adjust_strategy(strategy_id)
        return self.advance_web_fight()
