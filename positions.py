from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Tuple
import utils
from fighter import Fighter

class Position(Enum):
    DISTANCE = "Distance"
    POCKET = "Pocket"
    CLINCH = "Clinch"
    GROUND_GUARD = "Ground (Guard)"
    GROUND_SIDE = "Ground (Side Control)"
    GROUND_MOUNT = "Ground (Mount)"
    GROUND_BACK = "Ground (Back Mount)"

    @staticmethod
    def is_standing(pos: "Position") -> bool:
        return pos in (Position.DISTANCE, Position.POCKET)

    @staticmethod
    def is_ground(pos: "Position") -> bool:
        return pos in (Position.GROUND_GUARD, Position.GROUND_SIDE, Position.GROUND_MOUNT, Position.GROUND_BACK)

    @staticmethod
    def ground_advancement() -> Dict["Position", "Position"]:
        return {
            Position.GROUND_GUARD: Position.GROUND_SIDE,
            Position.GROUND_SIDE: Position.GROUND_MOUNT,
            Position.GROUND_MOUNT: Position.GROUND_BACK,
        }

    @staticmethod
    def ground_hierarchy_rank(pos: "Position") -> int:
        return {
            Position.GROUND_GUARD: 0,
            Position.GROUND_SIDE: 1,
            Position.GROUND_MOUNT: 2,
            Position.GROUND_BACK: 3,
        }.get(pos, -1)


GROUND_POSITIONS = [Position.GROUND_GUARD, Position.GROUND_SIDE, Position.GROUND_MOUNT, Position.GROUND_BACK]


class PositionSystem:
    def __init__(self, fighter1: Fighter, fighter2: Fighter):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.current_position = Position.DISTANCE
        self.top_fighter: Optional[Fighter] = None
        self.bottom_fighter: Optional[Fighter] = None
        self.clinch_initiator: Optional[Fighter] = None
        self.position_time = 0

    def _is_top(self, fighter: Fighter) -> bool:
        return self.top_fighter is fighter

    def _is_bottom(self, fighter: Fighter) -> bool:
        return self.bottom_fighter is fighter

    def _set_ground(self, top: Fighter, bottom: Fighter, pos: Position):
        self.current_position = pos
        self.top_fighter = top
        self.bottom_fighter = bottom
        self.clinch_initiator = None
        self.position_time = 0

    def close_distance(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.DISTANCE:
            return False
        speed_attr = attacker.get_effective_attribute("hand_speed", fatigue)
        athleticism = attacker.get_effective_attribute("athleticism", fatigue)
        defender_ath = defender.get_effective_attribute("athleticism", fatigue)
        success_chance = (speed_attr * 0.5 + athleticism * 0.5) - defender_ath * 0.3
        success_chance = max(40, min(95, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.POCKET
            self.position_time = 0
            return True
        return False

    def retreat_to_distance(self, fighter: Fighter, opponent: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.POCKET:
            return False
        athleticism = fighter.get_effective_attribute("athleticism", fatigue)
        opponent_aggression = opponent.get_effective_attribute("aggression", 1.0)
        success_chance = athleticism * 0.6 - opponent_aggression * 0.3
        success_chance = max(10, min(70, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.DISTANCE
            self.position_time = 0
            return True
        return False

    def attempt_takedown(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
        takedown_power = attacker.get_effective_attribute("takedown_power", fatigue)
        takedown_accuracy = attacker.get_effective_attribute("takedown_accuracy", fatigue)
        wrestling_defense = defender.get_effective_attribute("wrestling_defense", fatigue)
        range_penalty = 0.7 if self.current_position == Position.DISTANCE else 1.0
        success_chance = ((takedown_power * 0.4 + takedown_accuracy * 0.6) - (wrestling_defense * 0.5)) * range_penalty
        success_chance = max(5, min(95, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self._set_ground(attacker, defender, Position.GROUND_GUARD)
            return True
        return False

    def attempt_clinch(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position not in (Position.POCKET, Position.DISTANCE):
            return False
        if self.current_position == Position.DISTANCE:
            if not self.close_distance(attacker, defender, fatigue):
                return False
        clinch_control = attacker.get_effective_attribute("clinch_control", fatigue)
        clinch_escapes = defender.get_effective_attribute("clinch_escapes", fatigue)
        success_chance = clinch_control * 0.7 - clinch_escapes * 0.5
        success_chance = max(10, min(90, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.CLINCH
            self.clinch_initiator = attacker
            self.position_time = 0
            return True
        return False

    def break_clinch(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.CLINCH:
            return False
        clinch_escapes = attacker.get_effective_attribute("clinch_escapes", fatigue)
        clinch_control = defender.get_effective_attribute("clinch_control", fatigue)
        success_chance = clinch_escapes * 0.6 - clinch_control * 0.4
        success_chance = max(15, min(85, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.POCKET
            self.clinch_initiator = None
            self.position_time = 0
            return True
        return False

    def takedown_from_clinch(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.CLINCH:
            return False
        td_power = attacker.get_effective_attribute("takedown_power", fatigue) * 1.15
        wd = defender.get_effective_attribute("wrestling_defense", fatigue)
        success_chance = td_power * 0.5 - wd * 0.4
        success_chance = max(10, min(90, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            initiator_is_attacker = (self.clinch_initiator == attacker)
            if initiator_is_attacker:
                self._set_ground(attacker, defender, Position.GROUND_GUARD)
            else:
                self._set_ground(defender, attacker, Position.GROUND_GUARD)
            return True
        return False

    def pass_guard(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_GUARD:
            return False
        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        success_chance = top_control * 0.6 - bottom_control * 0.4
        success_chance = max(10, min(80, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_SIDE
            self.position_time = 0
            return True
        return False

    def advance_to_mount(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_SIDE:
            return False
        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        success_chance = top_control * 0.5 - bottom_control * 0.3
        success_chance = max(5, min(70, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_MOUNT
            self.position_time = 0
            return True
        return False

    def take_back(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position not in (Position.GROUND_GUARD, Position.GROUND_SIDE):
            return False
        top_control = top.get_effective_attribute("top_control", fatigue) * 0.8
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        success_chance = top_control * 0.4 - bottom_control * 0.3
        success_chance = max(3, min(50, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_BACK
            self.position_time = 0
            return True
        return False

    def sweep_from_bottom(self, bottom_fighter: Fighter, top_fighter: Fighter, fatigue: float = 0.0) -> bool:
        if not Position.is_ground(self.current_position):
            return False
        pos_factor = 1.0 if self.current_position == Position.GROUND_GUARD else (0.7 if self.current_position == Position.GROUND_SIDE else (0.4 if self.current_position == Position.GROUND_MOUNT else 0.2))
        bottom_control = bottom_fighter.get_effective_attribute("bottom_control", fatigue)
        top_control = top_fighter.get_effective_attribute("top_control", fatigue)
        success_chance = (bottom_control * 0.6 - top_control * 0.4) * pos_factor
        success_chance = max(5, min(70, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self._set_ground(bottom_fighter, top_fighter, Position.GROUND_GUARD)
            return True
        return False

    def stand_up_from_bottom(self, bottom_fighter: Fighter, top_fighter: Fighter, fatigue: float = 0.0) -> bool:
        if not Position.is_ground(self.current_position):
            return False
        pos_factor = 1.2 if self.current_position == Position.GROUND_GUARD else (1.0 if self.current_position == Position.GROUND_SIDE else (0.6 if self.current_position == Position.GROUND_MOUNT else 0.4))
        bottom_control = bottom_fighter.get_effective_attribute("bottom_control", fatigue)
        top_control = top_fighter.get_effective_attribute("top_control", fatigue)
        athleticism = bottom_fighter.get_effective_attribute("athleticism", fatigue)
        success_chance = (bottom_control * 0.3 + athleticism * 0.5 - top_control * 0.4) * pos_factor
        success_chance = max(5, min(75, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.DISTANCE
            self.top_fighter = None
            self.bottom_fighter = None
            self.position_time = 0
            return True
        return False

    def get_position_description(self) -> str:
        p = self.current_position
        if p == Position.DISTANCE:
            return "Fighters are at kicking range, measuring each other."
        elif p == Position.POCKET:
            return "Fighters are in the pocket, trading strikes."
        elif p == Position.CLINCH:
            initiator = self.clinch_initiator.name if self.clinch_initiator else "Unknown"
            return f"{initiator} has secured the clinch."
        elif p == Position.GROUND_GUARD:
            return f"{self.top_fighter.name} is in {self.bottom_fighter.name}'s guard."
        elif p == Position.GROUND_SIDE:
            return f"{self.top_fighter.name} has passed guard and is in side control."
        elif p == Position.GROUND_MOUNT:
            return f"{self.top_fighter.name} has mounted {self.bottom_fighter.name}!"
        elif p == Position.GROUND_BACK:
            return f"{self.top_fighter.name} has {self.bottom_fighter.name}'s back!"
        return "Unknown position"
