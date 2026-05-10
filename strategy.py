from typing import Dict, List, Optional
from fighter import Fighter
import utils

STRATEGIES = [
    {
        "id": "aggressive_striking",
        "name": "Aggressive Striking",
        "description": "High-output stand-up exchanges",
        "modifiers": {"striking_power": 1.1, "hand_speed": 1.1, "striking_accuracy": 0.95, "wrestling_defense": 0.9, "cardio_drain": 1.15},
        "counters": ["defensive_striking", "clinch_dominance"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.85, "takedown": 0.05, "clinch": 0.10},
    },
    {
        "id": "defensive_striking",
        "name": "Defensive Striking",
        "description": "Counter-punching and distance management",
        "modifiers": {"striking_accuracy": 1.15, "wrestling_defense": 1.1, "hand_speed": 0.9, "striking_power": 0.9, "cardio_drain": 0.9},
        "counters": ["aggressive_striking", "volume_striking"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.75, "takedown": 0.10, "clinch": 0.15},
    },
    {
        "id": "wrestling_focus",
        "name": "Wrestling Focus",
        "description": "Takedown attempts and ground control",
        "modifiers": {"takedown_power": 1.2, "takedown_accuracy": 1.15, "top_control": 1.1, "striking_power": 0.85, "striking_accuracy": 0.85},
        "counters": ["submission_hunting", "clinch_dominance"],
        "preferred_position": "ground_top",
        "action_weights": {"strike": 0.30, "takedown": 0.50, "clinch": 0.20},
    },
    {
        "id": "grappling_focus",
        "name": "Grappling Focus",
        "description": "Submission attempts and ground control",
        "modifiers": {"submission_offense": 1.2, "submission_defense": 1.1, "bottom_control": 1.1, "top_control": 1.05, "striking_power": 0.8},
        "counters": ["ground_and_pound", "wrestling_focus"],
        "preferred_position": "ground",
        "action_weights": {"strike": 0.20, "takedown": 0.30, "clinch": 0.10},
    },
    {
        "id": "clinch_dominance",
        "name": "Clinch Dominance",
        "description": "Close-quarters control with strikes/throws",
        "modifiers": {"clinch_control": 1.2, "clinch_strikes": 1.15, "clinch_throws": 1.15, "striking_accuracy": 0.9, "takedown_accuracy": 0.9},
        "counters": ["wrestling_focus", "aggressive_striking"],
        "preferred_position": "clinch",
        "action_weights": {"strike": 0.25, "takedown": 0.15, "clinch": 0.60},
    },
    {
        "id": "pressure_fighting",
        "name": "Pressure Fighting",
        "description": "Constant forward movement and aggression",
        "modifiers": {"aggression": 1.2, "cardio_drain": 1.2, "striking_power": 1.05, "composure": 0.9, "fight_iq": 0.95},
        "counters": ["defensive_striking", "leg_kick_focus"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.80, "takedown": 0.10, "clinch": 0.10},
    },
    {
        "id": "volume_striking",
        "name": "Volume Striking",
        "description": "High output, low-damage strikes",
        "modifiers": {"hand_speed": 1.2, "striking_accuracy": 1.1, "striking_power": 0.8, "cardio_drain": 1.1},
        "counters": ["power_hunting", "defensive_striking"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.90, "takedown": 0.05, "clinch": 0.05},
    },
    {
        "id": "power_hunting",
        "name": "Power Hunting",
        "description": "Wait for big shots and explosive combinations",
        "modifiers": {"striking_power": 1.2, "hand_speed": 0.85, "striking_accuracy": 0.9, "cardio_drain": 0.95},
        "counters": ["volume_striking", "pressure_fighting"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.85, "takedown": 0.10, "clinch": 0.05},
    },
    {
        "id": "leg_kick_focus",
        "name": "Leg Kick Focus",
        "description": "Target legs to slow opponent down",
        "modifiers": {"kick_power": 1.2, "kick_accuracy": 1.1, "kick_speed": 1.05, "cardio_drain": 1.1, "striking_power": 0.9},
        "counters": ["kickboxing_focus", "clinch_dominance"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.85, "takedown": 0.10, "clinch": 0.05},
    },
    {
        "id": "body_shot_focus",
        "name": "Body Shot Focus",
        "description": "Target midsection to sap energy",
        "modifiers": {"striking_power": 1.15, "striking_accuracy": 1.1, "cardio_drain": 1.15, "kick_power": 0.9},
        "counters": ["leg_kick_focus", "pressure_fighting"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.90, "takedown": 0.05, "clinch": 0.05},
    },
    {
        "id": "ground_and_pound",
        "name": "Ground and Pound",
        "description": "Takedowns and strikes from top position",
        "modifiers": {"top_control": 1.2, "striking_power": 1.1, "takedown_accuracy": 1.1, "submission_offense": 0.8},
        "counters": ["submission_hunting", "grappling_focus"],
        "preferred_position": "ground_top",
        "action_weights": {"strike": 0.40, "takedown": 0.40, "clinch": 0.20},
    },
    {
        "id": "submission_hunting",
        "name": "Submission Hunting",
        "description": "Prioritize submissions over strikes",
        "modifiers": {"submission_offense": 1.25, "bottom_control": 1.1, "top_control": 1.05, "striking_power": 0.75},
        "counters": ["ground_and_pound", "wrestling_focus"],
        "preferred_position": "ground",
        "action_weights": {"strike": 0.15, "takedown": 0.35, "clinch": 0.10},
    },
    {
        "id": "boxing_focus",
        "name": "Boxing Focus",
        "description": "Emphasize punches, avoid kicks/grappling",
        "modifiers": {"striking_power": 1.15, "hand_speed": 1.1, "striking_accuracy": 1.1, "kick_power": 0.7, "kick_accuracy": 0.7, "clinch_control": 0.8},
        "counters": ["kickboxing_focus", "leg_kick_focus"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.90, "takedown": 0.05, "clinch": 0.05},
    },
    {
        "id": "kickboxing_focus",
        "name": "Kickboxing Focus",
        "description": "Full striking arsenal (punches and kicks)",
        "modifiers": {"striking_power": 1.1, "kick_power": 1.1, "hand_speed": 1.05, "clinch_control": 0.85, "takedown_accuracy": 0.85},
        "counters": ["boxing_focus", "clinch_dominance"],
        "preferred_position": "standing",
        "action_weights": {"strike": 0.85, "takedown": 0.10, "clinch": 0.05},
    },
    {
        "id": "muay_thai_focus",
        "name": "Muay Thai Focus",
        "description": "Clinch work, knees, and elbows",
        "modifiers": {"clinch_control": 1.2, "clinch_strikes": 1.2, "kick_power": 1.1, "wrestling_defense": 0.85, "takedown_accuracy": 0.85},
        "counters": ["kickboxing_focus", "wrestling_focus"],
        "preferred_position": "clinch",
        "action_weights": {"strike": 0.40, "takedown": 0.10, "clinch": 0.50},
    },
]

ARCHETYPE_STRATEGY_MAP = {
    "brawler": "aggressive_striking",
    "counter_striker": "defensive_striking",
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

    def set_pre_fight_strategy(self, strategy_id: str) -> bool:
        for strategy in STRATEGIES:
            if strategy["id"] == strategy_id:
                self.pre_fight_strategy = strategy
                self.current_strategy = strategy
                self.switch_penalty = 0.0
                return True
        return False

    def adjust_strategy(self, new_strategy_id: str) -> bool:
        for strategy in STRATEGIES:
            if strategy["id"] == new_strategy_id:
                self.current_strategy = strategy
                self.switch_penalty = 0.1
                return True
        return False

    def get_modifiers(self) -> Dict[str, float]:
        if not self.current_strategy:
            return {}
        modifiers = self.current_strategy["modifiers"].copy()
        if self.switch_penalty > 0:
            for key in modifiers:
                if modifiers[key] > 1:
                    modifiers[key] *= (1 - self.switch_penalty)
        return modifiers

    def get_modifier_for_attr(self, attr: str) -> float:
        mods = self.get_modifiers()
        return mods.get(attr, 1.0)

    def get_action_weights(self) -> Dict[str, float]:
        if not self.current_strategy:
            return {"strike": 0.7, "takedown": 0.15, "clinch": 0.15}
        weights = self.current_strategy.get("action_weights", {}).copy()
        if self.switch_penalty > 0:
            for key in weights:
                weights[key] *= (1 - self.switch_penalty * 0.5)
        total = sum(weights.values())
        if total > 0:
            for key in weights:
                weights[key] /= total
        return weights

    def calculate_effectiveness(self, opponent_strategy: Optional[Dict]) -> float:
        if not self.current_strategy or not opponent_strategy:
            return 0.5
        if self.current_strategy["id"] in opponent_strategy.get("counters", []):
            return 0.3
        if opponent_strategy["id"] in self.current_strategy.get("counters", []):
            return 0.7
        return 0.5

    def get_preferred_position(self) -> str:
        if not self.current_strategy:
            return "standing"
        return self.current_strategy.get("preferred_position", "standing")

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
    def pick_ai_strategy(fighter: Fighter, opponent_fighter: Fighter, round_scores: List[int],
                         round_num: int, total_rounds: int, current_strategy: Optional[Dict] = None) -> str:
        archetype = fighter.archetype
        default_strategy_id = ARCHETYPE_STRATEGY_MAP.get(archetype)

        if not default_strategy_id:
            default_strategy_id = random.choice([s["id"] for s in STRATEGIES])

        if round_num <= 1:
            return default_strategy_id

        total_score = sum(round_scores)
        losing = total_score < 0
        badly_losing = total_score <= -15
        winning = total_score > 0

        if badly_losing:
            return "aggressive_striking"
        if losing and round_num >= total_rounds - 1:
            return "power_hunting"
        if losing:
            return random.choices(
                [default_strategy_id, "aggressive_striking", "pressure_fighting"],
                weights=[0.3, 0.4, 0.3]
            )[0]

        stamina_left = fighter.attributes.get("cardio", 50)
        if stamina_left < 30 and winning:
            return "defensive_striking"
        if stamina_left > 70 and winning:
            return "pressure_fighting"

        return default_strategy_id

import random
