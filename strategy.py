import random
from typing import Dict, List, Optional

import utils
from fighter import Fighter

# STYLES dict is now the single source of truth for strategy modifiers
# Imported from utils to keep one canonical definition
STRATEGIES = [
    {
        "id": "aggressive_striking",
        "name": "Aggressive Striking",
        "description": "High-output stand-up exchanges, pressure forward",
        "modifiers": {"striking_power": 1.1, "hand_speed": 1.1, "striking_accuracy": 0.95,
                      "wrestling_defense": 0.9, "cardio_drain": 1.05},
        "counters": ["defensive_striking", "clinch_dominance"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.75, "takedown": 0.12, "clinch": 0.13},
    },
    {
        "id": "defensive_striking",
        "name": "Defensive Striking",
        "description": "Counter-punching and distance management",
        "modifiers": {"striking_accuracy": 1.15, "wrestling_defense": 1.1, "hand_speed": 0.9,
                      "striking_power": 0.9, "cardio_drain": 0.9, "parry_chance": 1.2, "feint_chance": 0.03},
        "counters": ["aggressive_striking", "volume_striking"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.65, "takedown": 0.18, "clinch": 0.17},
    },
    {
        "id": "wrestling_focus",
        "name": "Wrestling Focus",
        "description": "Takedown attempts and ground control",
        "modifiers": {"takedown_power": 1.2, "takedown_accuracy": 1.15, "top_control": 1.1,
                      "striking_power": 0.85, "striking_accuracy": 0.85},
        "counters": ["submission_hunting", "clinch_dominance"],
        "preferred_position": "ground_top",
        "action_weights": {"strike": 0.30, "takedown": 0.50, "clinch": 0.20},
    },
    {
        "id": "grappling_focus",
        "name": "Grappling Focus",
        "description": "Submission attempts and ground control",
        "modifiers": {"submission_offense": 1.2, "submission_defense": 1.1, "bottom_control": 1.1,
                      "top_control": 1.05, "striking_power": 0.8, "escape_ability": 1.1},
        "counters": ["ground_and_pound", "wrestling_focus"],
        "preferred_position": "ground",
        "action_weights": {"strike": 0.20, "takedown": 0.50, "clinch": 0.10},
    },
    {
        "id": "clinch_dominance",
        "name": "Clinch Dominance",
        "description": "Close-quarters control with strikes and throws",
        "modifiers": {"clinch_control": 1.2, "clinch_strikes": 1.15, "clinch_throws": 1.15,
                      "striking_accuracy": 0.9, "takedown_accuracy": 0.9},
        "counters": ["wrestling_focus", "aggressive_striking"],
        "preferred_position": "clinch",
        "action_weights": {"strike": 0.25, "takedown": 0.25, "clinch": 0.50},
    },
    {
        "id": "pressure_fighting",
        "name": "Pressure Fighting",
        "description": "Constant forward movement and aggression",
        "modifiers": {"aggression": 1.2, "cardio_drain": 1.05, "striking_power": 1.05,
                      "composure": 0.95, "fight_iq": 0.95},
        "counters": ["defensive_striking", "leg_kick_focus"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.70, "takedown": 0.17, "clinch": 0.13},
    },
    {
        "id": "volume_striking",
        "name": "Volume Striking",
        "description": "High output, accumulating damage with low-damage strikes",
        "modifiers": {"hand_speed": 1.2, "striking_accuracy": 1.1, "striking_power": 0.8,
                      "cardio_drain": 1.1, "combo_frequency": 1.25},
        "counters": ["power_hunting", "defensive_striking"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.80, "takedown": 0.12, "clinch": 0.08},
    },
    {
        "id": "power_hunting",
        "name": "Power Hunting",
        "description": "Wait for openings, throw explosive finishing combinations",
        "modifiers": {"striking_power": 1.2, "hand_speed": 0.85, "striking_accuracy": 0.9,
                      "cardio_drain": 0.95, "counter_power": 1.25},
        "counters": ["volume_striking", "pressure_fighting"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.75, "takedown": 0.15, "clinch": 0.10},
    },
    {
        "id": "leg_kick_focus",
        "name": "Leg Kick Focus",
        "description": "Target legs to reduce opponent mobility and stamina",
        "modifiers": {"kick_power": 1.2, "kick_accuracy": 1.1, "kick_speed": 1.05,
                      "cardio_drain": 1.1, "striking_power": 0.9},
        "counters": ["kickboxing_focus", "clinch_dominance"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.75, "takedown": 0.18, "clinch": 0.07},
    },
    {
        "id": "body_shot_focus",
        "name": "Body Shot Focus",
        "description": "Target midsection to sap energy and reduce stamina recovery",
        "modifiers": {"striking_power": 1.15, "striking_accuracy": 1.1, "cardio_drain": 1.15,
                      "kick_power": 0.9, "body_damage_bonus": 1.25},
        "counters": ["leg_kick_focus", "pressure_fighting"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.80, "takedown": 0.12, "clinch": 0.08},
    },
    {
        "id": "ground_and_pound",
        "name": "Ground and Pound",
        "description": "Takedowns followed by heavy strikes from top position",
        "modifiers": {"top_control": 1.2, "striking_power": 1.1, "takedown_accuracy": 1.1,
                      "submission_offense": 0.8, "ground_strike_damage": 1.2},
        "counters": ["submission_hunting", "grappling_focus"],
        "preferred_position": "ground_top",
        "action_weights": {"strike": 0.40, "takedown": 0.40, "clinch": 0.20},
    },
    {
        "id": "submission_hunting",
        "name": "Submission Hunting",
        "description": "Prioritize submissions over strikes, chain attacks",
        "modifiers": {"submission_offense": 1.25, "bottom_control": 1.1, "top_control": 1.05,
                      "striking_power": 0.75, "submission_defense": 1.05},
        "counters": ["ground_and_pound", "wrestling_focus"],
        "preferred_position": "ground",
        "action_weights": {"strike": 0.15, "takedown": 0.55, "clinch": 0.10},
    },
    {
        "id": "boxing_focus",
        "name": "Boxing Focus",
        "description": "Emphasize punches, head movement, avoid kicks/grappling",
        "modifiers": {"striking_power": 1.15, "hand_speed": 1.1, "striking_accuracy": 1.1,
                      "kick_power": 0.7, "kick_accuracy": 0.7, "clinch_control": 0.8,
                      "counter_power": 1.1},
        "counters": ["kickboxing_focus", "leg_kick_focus"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.80, "takedown": 0.12, "clinch": 0.08},
    },
    {
        "id": "kickboxing_focus",
        "name": "Kickboxing Focus",
        "description": "Full striking arsenal combining punches and kicks",
        "modifiers": {"striking_power": 1.1, "kick_power": 1.1, "hand_speed": 1.05,
                      "clinch_control": 0.85, "takedown_accuracy": 0.85},
        "counters": ["boxing_focus", "clinch_dominance"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.75, "takedown": 0.18, "clinch": 0.07},
    },
    {
        "id": "muay_thai_focus",
        "name": "Muay Thai Focus",
        "description": "Clinch work, devastating knees and elbows, leg kicks",
        "modifiers": {"clinch_control": 1.2, "clinch_strikes": 1.2, "kick_power": 1.1,
                      "wrestling_defense": 0.85, "takedown_accuracy": 0.85},
        "counters": ["kickboxing_focus", "wrestling_focus"],
        "preferred_position": "clinch",
        "action_weights": {"strike": 0.30, "takedown": 0.18, "clinch": 0.52},
    },
    {
        "id": "counter_striker",
        "name": "Counter Striker",
        "description": "Let opponent come forward, punish with precise counters",
        "modifiers": {"striking_accuracy": 1.2, "hand_speed": 1.05, "composure": 1.1,
                      "striking_power": 0.95, "counter_power": 1.3, "defensive_striking": 1.15, "feint_chance": 0.02},
        "counters": ["aggressive_striking", "power_hunting", "brawler"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.60, "takedown": 0.18, "clinch": 0.22},
    },
    {
        "id": "brawler",
        "name": "Brawler",
        "description": "Walk forward, absorb punishment, deal heavy damage",
        "modifiers": {"striking_power": 1.25, "durability": 1.1, "aggression": 1.15,
                      "striking_accuracy": 0.88, "cardio_drain": 1.1, "heart": 1.1, "feint_chance": -0.02},
        "counters": ["counter_striker", "leg_kick_focus"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.75, "takedown": 0.18, "clinch": 0.07},
    },
]

ARCHETYPE_STRATEGY_MAP = {
    "brawler": "brawler",
    "counter_striker": "counter_striker",
    "wrestler": "wrestling_focus",
    "submission_artist": "submission_hunting",
    "kickboxer": "kickboxing_focus",
    "boxer": "boxing_focus",
    "muay_thai": "muay_thai_focus",
    "clinch_fighter": "clinch_dominance",
    "balanced": None,
}


class StrategySystem:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.current_strategy: Optional[Dict] = None
        self.pre_fight_strategy: Optional[Dict] = None
        self.switch_penalty = 0.0
        self._opponent_strategy: Optional[Dict] = None
        self._previous_strategies: List[str] = []
        # Strategy drift (gradual adaptation)
        self.drift_target_id: Optional[str] = None
        self.drift_progress: float = 0.0
        self._last_evaluation: str = "maintain"

    def set_opponent_strategy(self, strategy: Optional[Dict]):
        self._opponent_strategy = strategy

    def set_pre_fight_strategy(self, strategy_id: str) -> bool:
        for strategy in STRATEGIES:
            if strategy["id"] == strategy_id:
                self.pre_fight_strategy = strategy
                self.current_strategy = strategy
                self.switch_penalty = 0.0
                self._previous_strategies = [strategy_id]
                self.drift_target_id = None
                self.drift_progress = 0.0
                return True
        return False

    def adjust_strategy(self, new_strategy_id: str) -> bool:
        for strategy in STRATEGIES:
            if strategy["id"] == new_strategy_id:
                old_strategy = self.current_strategy
                self.current_strategy = strategy

                adaptability = self.fighter.get_effective_attribute("adaptability", 0) / 100.0
                self.switch_penalty = max(0.01, 0.08 - adaptability * 0.06)

                self._previous_strategies.append(new_strategy_id)
                if len(self._previous_strategies) > 5:
                    self._previous_strategies.pop(0)

                if old_strategy and old_strategy.get("id") == new_strategy_id:
                    self.switch_penalty *= 0.5

                self.drift_target_id = None
                self.drift_progress = 0.0
                return True
        return False

    def drift_toward_strategy(self, target_id: str, fight_iq: float, adaptability: float) -> bool:
        """Gradually drift action weights toward a target strategy."""
        if target_id == (self.current_strategy or {}).get("id"):
            return False
        # Find the target strategy
        target = None
        for s in STRATEGIES:
            if s["id"] == target_id:
                target = s
                break
        if not target:
            return False
        # Set drift target
        self.drift_target_id = target_id
        # Drift rate based on adaptability (0.1-0.3 per evaluation)
        drift_rate = 0.10 + (adaptability / 100.0) * 0.20
        self.drift_progress = min(1.0, self.drift_progress + drift_rate)
        # When drift completes, fully switch
        if self.drift_progress >= 1.0:
            self.adjust_strategy(target_id)
            return True
        return True

    def get_modifiers(self) -> Dict[str, float]:
        if not self.current_strategy:
            return {}
        modifiers = self.current_strategy["modifiers"].copy()

        # Apply switch penalty to boosted modifiers
        if self.switch_penalty > 0:
            for key in modifiers:
                if modifiers[key] > 1.0:
                    modifiers[key] *= (1.0 - self.switch_penalty)
                elif modifiers[key] < 1.0:
                    # Penalties also reduced when switching (less predictable)
                    modifiers[key] = 1.0 - (1.0 - modifiers[key]) * (1.0 - self.switch_penalty * 0.5)

        # Opponent counter detection — if we're countering what the opponent is using
        opponent = self._opponent_strategy
        if opponent and self.current_strategy:
            if self.current_strategy["id"] in opponent.get("counters", []):
                # We have an advantage — boost relevant stats
                for key in ["striking_accuracy", "wrestling_defense", "submission_defense",
                            "clinch_escapes", "counter_power"]:
                    if key in modifiers:
                        modifiers[key] *= 1.12

        # Style matchup modifier from utils
        if opponent:
            matchup_key = self.current_strategy["id"]
            effectiveness = utils.STRATEGY_EFFECTIVENESS.get(matchup_key, {}).get(opponent.get("id"))
            if effectiveness:
                # Apply as modifier to overall output
                modifiers["style_matchup"] = effectiveness

        return modifiers

    def get_modifier_for_attr(self, attr: str) -> float:
        mods = self.get_modifiers()
        return mods.get(attr, 1.0)

    def get_action_weights(self) -> Dict[str, float]:
        if self.current_strategy:
            return self.current_strategy.get("action_weights", {"strike": 0.30, "takedown": 0.55, "clinch": 0.15})
        return {"strike": 0.30, "takedown": 0.55, "clinch": 0.15}
        weights = self.current_strategy.get("action_weights", {}).copy()

        # Drift blending: mix current and target weights
        if self.drift_target_id and self.drift_progress > 0 and self.drift_progress < 1.0:
            target = None
            for s in STRATEGIES:
                if s["id"] == self.drift_target_id:
                    target = s
                    break
            if target:
                target_weights = target.get("action_weights", {})
                for key in set(list(weights.keys()) + list(target_weights.keys())):
                    current_w = weights.get(key, 0)
                    target_w = target_weights.get(key, 0)
                    weights[key] = current_w * (1 - self.drift_progress) + target_w * self.drift_progress

        if self.switch_penalty > 0:
            for key in weights:
                weights[key] *= (1 - self.switch_penalty * 0.5)
        total = sum(weights.values())
        if total > 0:
            for key in weights:
                weights[key] /= total
        return weights

    def calculate_effectiveness(self, opponent_strategy: Optional[Dict]) -> float:
        """Calculate how effective current strategy is against opponent."""
        if not self.current_strategy or not opponent_strategy:
            return 0.5
        matchup = utils.STRATEGY_EFFECTIVENESS.get(
            self.current_strategy["id"], {}).get(opponent_strategy["id"])
        if matchup is not None:
            return matchup
        if self.current_strategy["id"] in opponent_strategy.get("counters", []):
            return 0.35
        if opponent_strategy["id"] in self.current_strategy.get("counters", []):
            return 0.65
        return 0.5

    def get_preferred_position(self) -> str:
        if not self.current_strategy:
            return "standing"
        return self.current_strategy.get("preferred_position", "standing")

    def detect_and_counter_pattern(self, opponent_action_history: List[str]) -> Optional[str]:
        """
        Higher fight IQ fighters detect repeated opponent patterns
        and suggest counter-strategies.
        """
        iq = self.fighter.get_effective_attribute("fight_iq", 0)
        adaptability = self.fighter.get_effective_attribute("adaptability", 0)
        if iq < 40 or len(opponent_action_history) < 4:
            return None

        from collections import Counter
        recent = opponent_action_history[-8:]
        pattern = Counter(recent)
        most_common, count = pattern.most_common(1)[0]

        # If opponent repeats same action 4+ times in last 8
        if count >= 4:
            adaptation_chance = (iq / 150.0) * (1.0 + adaptability / 300.0)
            if random.random() < adaptation_chance:
                counter_map = {
                    "jab": "slip_cross",
                    "cross": "parry_hook",
                    "takedown_attempt": "sprawl",
                    "clinch_attempt": "underhook",
                    "kick": "check_kick",
                }
                return counter_map.get(most_common)
        return None

    def pick_ai_fight_style(self, damage_taken_pct: float, winning: bool,
                            round_num: int, total_rounds: int) -> str:
        """
        Choose a fighting style emphasis for the AI based on context.
        Returns a style keyword that influences action weighting.
        """
        if damage_taken_pct > 60:  # Heavily damaged
            if winning:
                return "defensive"
            else:
                return "desperate"
        elif damage_taken_pct > 35:  # Taking significant damage
            return "cautious"
        elif winning and round_num >= total_rounds - 1:
            return "stall" if random.random() < 0.3 else "controlled_aggression"
        elif not winning and round_num >= total_rounds - 1:
            return "aggressive_finish"
        else:
            # Default to strategy preference
            pref = self.get_preferred_position()
            style_map = {
                "standing": "striking",
                "ground_top": "ground_control",
                "ground": "submission_hunt",
                "clinch": "clinch_work",
            }
            return style_map.get(pref, "balanced")

    @staticmethod
    def get_available_strategies() -> List[Dict]:
        return STRATEGIES

    @staticmethod
    def get_strategy_by_id(strategy_id: str) -> Optional[Dict]:
        for s in STRATEGIES:
            if s["id"] == strategy_id:
                return s
        return None

    @staticmethod
    def evaluate_round_effectiveness(fighter: Fighter, opponent: Fighter, round_num: int,
                                       round_score_diff: int, damage_taken_pct: float) -> str:
        if round_score_diff < -2 and damage_taken_pct > 40:
            return "desperate_switch"
        elif round_score_diff < -1:
            return "need_change"
        elif round_score_diff > 1 and damage_taken_pct < 20:
            return "keep_winning"
        return "maintain"

    @staticmethod
    def pick_ai_strategy(fighter: Fighter, opponent_fighter: Fighter, round_scores: List[int],
                         round_num: int, total_rounds: int, current_strategy: Optional[Dict] = None) -> str:
        """
        Smarter AI strategy selection based on:
        - Archetype
        - Round score differential
        - Fight IQ
        - Stamina remaining
        - Opponent archetype
        - Round number
        """
        archetype = fighter.archetype
        default_strategy_id = ARCHETYPE_STRATEGY_MAP.get(archetype)

        if not default_strategy_id:
            default_strategy_id = random.choice([s["id"] for s in STRATEGIES])

        fight_iq = fighter.get_effective_attribute("fight_iq", 0)
        adaptability = fighter.get_effective_attribute("adaptability", 0)
        stamina = fighter.get_effective_attribute("cardio", 0)
        iq_factor = fight_iq / 100.0
        stamina_factor = stamina / 100.0

        # Round 1: try counter to opponent archetype if smart enough
        if round_num <= 1:
            if iq_factor > 0.55 and opponent_fighter:
                opp_archetype = opponent_fighter.archetype
                counter_map = {
                    "brawler": ["defensive_striking", "counter_striker"],
                    "wrestler": ["clinch_dominance", "wrestling_focus"],
                    "submission_artist": ["ground_and_pound", "wrestling_focus"],
                    "kickboxer": ["wrestling_focus", "leg_kick_focus"],
                    "boxer": ["kickboxing_focus", "leg_kick_focus"],
                    "muay_thai": ["pressure_fighting", "leg_kick_focus"],
                    "balanced": None,
                }
                counters = counter_map.get(opp_archetype)
                if counters and random.random() < iq_factor:
                    return random.choice(counters)
            return default_strategy_id

        total_score = sum(round_scores)
        losing = total_score < 0
        badly_losing = total_score <= -15
        winning = total_score > 0
        rounds_left = total_rounds - round_num

        # Desperation: if badly losing in last 2 rounds, go aggressive
        if badly_losing and rounds_left <= 2:
            return "aggressive_striking"

        # Closing rounds and losing: go for power finishes
        if losing and rounds_left <= 1:
            return random.choice(["power_hunting", "aggressive_striking"])

        # If losing mid-fight: adapt based on IQ
        if losing:
            if iq_factor > 0.6:
                # Smart fighters try to read opponent's weakness
                return random.choice([
                    default_strategy_id,
                    "counter_striker" if stamina_factor > 0.5 else "defensive_striking",
                    "pressure_fighting"
                ])
            return random.choices(
                [default_strategy_id, "aggressive_striking", "pressure_fighting"],
                weights=[0.3, 0.4, 0.3])[0]

        # Winning: manage fight smartly
        if winning:
            # Low stamina: switch to defensive
            if stamina_factor < 0.35 and iq_factor > 0.4:
                return random.choice(["defensive_striking", default_strategy_id])

            # High stamina and winning: press advantage
            if stamina_factor > 0.7 and iq_factor > 0.3:
                return random.choice(["pressure_fighting", default_strategy_id])

            # High IQ: recognize opponent adjustments and counter
            if iq_factor > 0.65 and opponent_fighter:
                opp_arch = opponent_fighter.archetype
                # If opponent is a wrestler and we're standing, stay away
                if opp_arch in ["wrestler", "submission_artist"] and stamina_factor > 0.5:
                    if random.random() < iq_factor * 0.4:
                        return "counter_striker"

                # If opponent is aggressive, try to counter
                if opp_arch in ["brawler", "aggressive_striker"]:
                    if random.random() < iq_factor * 0.3:
                        return "defensive_striking"

        # Fatigue factor: if both fighters are tired, clinch game
        if stamina_factor < 0.3 and opponent_fighter:
            opp_stam = opponent_fighter.get_effective_attribute("cardio", 0) / 100
            if opp_stam < 0.4 and random.random() < 0.3:
                return random.choice(["clinch_dominance", "body_shot_focus"])
