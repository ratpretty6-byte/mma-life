from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

import utils
from fighter import Fighter


class Position(Enum):
    DISTANCE = "Distance"
    POCKET = "Pocket"
    CLINCH = "Clinch"
    GROUND_GUARD = "Ground (Guard)"
    GROUND_HALF_GUARD = "Ground (Half Guard)"
    GROUND_SIDE = "Ground (Side Control)"
    GROUND_NORTH_SOUTH = "Ground (North-South)"
    GROUND_MOUNT = "Ground (Mount)"
    GROUND_BACK = "Ground (Back Mount)"
    GROUND_TURTLE = "Ground (Turtle)"
    GROUND_CRUCIFIX = "Ground (Crucifix)"
    GROUND_SCARF_HOLD = "Ground (Scarf Hold)"

    @staticmethod
    def is_standing(pos: "Position") -> bool:
        return pos in (Position.DISTANCE, Position.POCKET, Position.CLINCH)

    @staticmethod
    def is_ground(pos: "Position") -> bool:
        return pos in (Position.GROUND_GUARD, Position.GROUND_HALF_GUARD, Position.GROUND_SIDE,
                       Position.GROUND_NORTH_SOUTH, Position.GROUND_MOUNT, Position.GROUND_BACK,
                       Position.GROUND_TURTLE, Position.GROUND_CRUCIFIX, Position.GROUND_SCARF_HOLD)

    @staticmethod
    def ground_advancement() -> Dict["Position", "Position"]:
        return {
            Position.GROUND_GUARD: Position.GROUND_HALF_GUARD,
            Position.GROUND_HALF_GUARD: Position.GROUND_SIDE,
            Position.GROUND_SIDE: Position.GROUND_NORTH_SOUTH,
            Position.GROUND_NORTH_SOUTH: Position.GROUND_MOUNT,
            Position.GROUND_MOUNT: Position.GROUND_BACK,
        }

    @staticmethod
    def ground_hierarchy_rank(pos: "Position") -> int:
        return {
            Position.GROUND_GUARD: 0,
            Position.GROUND_HALF_GUARD: 1,
            Position.GROUND_SIDE: 2,
            Position.GROUND_NORTH_SOUTH: 3,
            Position.GROUND_MOUNT: 4,
            Position.GROUND_BACK: 5,
            Position.GROUND_TURTLE: -1,
            Position.GROUND_CRUCIFIX: 6,
            Position.GROUND_SCARF_HOLD: 5,
        }.get(pos, -1)


GROUND_POSITIONS = [Position.GROUND_GUARD, Position.GROUND_HALF_GUARD, Position.GROUND_SIDE,
                    Position.GROUND_NORTH_SOUTH, Position.GROUND_MOUNT, Position.GROUND_BACK,
                    Position.GROUND_TURTLE, Position.GROUND_CRUCIFIX, Position.GROUND_SCARF_HOLD]


class PositionSystem:
    def __init__(self, fighter1: Fighter, fighter2: Fighter):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.current_position = Position.DISTANCE
        self.top_fighter: Optional[Fighter] = None
        self.bottom_fighter: Optional[Fighter] = None
        self.clinch_initiator: Optional[Fighter] = None
        self.position_time = 0
        self.cage_position: Optional[Fighter] = None  # Which fighter has their back to the cage

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

        reach_diff = attacker.reach - defender.reach
        reach_mod = 1.0 - max(0, reach_diff) * 0.004 if reach_diff > 0 else 1.0 + min(0.1, abs(reach_diff) * 0.003)

        speed_attr = attacker.get_effective_attribute("hand_speed", fatigue)
        athleticism = attacker.get_effective_attribute("athleticism", fatigue)
        explode = attacker.get_effective_attribute("explosiveness", fatigue)
        defender_footwork = defender.get_effective_attribute("footwork_defense", fatigue)
        defender_ath = defender.get_effective_attribute("athleticism", fatigue)

        success_chance = (speed_attr * 0.30 + athleticism * 0.25 + explode * 0.25) - (defender_footwork * 0.30 + defender_ath * 0.20)
        success_chance *= reach_mod
        success_chance *= max(0.4, 1.0 - fatigue * 0.3)
        success_chance = max(15, min(92, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            if self.cage_position == defender:
                pass
            self.current_position = Position.POCKET
            self.position_time = 0
            return True
        return False

    def retreat_to_distance(self, fighter: Fighter, opponent: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position not in (Position.POCKET, Position.CLINCH):
            return False

        athleticism = fighter.get_effective_attribute("athleticism", fatigue)
        opponent_aggression = opponent.get_effective_attribute("aggression", 1.0)

        # Against cage, retreat is harder
        escape_mod = 0.6 if self.cage_position == fighter else 1.0

        success_chance = (athleticism * 0.6 - opponent_aggression * 0.3) * escape_mod
        success_chance *= max(0.4, 1.0 - fatigue * 0.4)
        success_chance = max(10, min(65, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.DISTANCE
            self.cage_position = None
            self.position_time = 0
            return True
        return False

    def attempt_takedown(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0,
                          td_mod: float = 1.0, tda_mod: float = 1.0, wd_mod: float = 1.0,
                          weight_advantage: float = 0.0, att_leg_mod: float = 1.0, def_leg_mod: float = 1.0) -> bool:
        takedown_power = attacker.get_effective_attribute("takedown_power", fatigue) * td_mod
        takedown_accuracy = attacker.get_effective_attribute("takedown_accuracy", fatigue) * tda_mod
        wrestling_defense = defender.get_effective_attribute("wrestling_defense", fatigue) * wd_mod

        range_penalty = 1.0 if self.current_position == Position.DISTANCE else 1.0

        # Height/weight advantage
        height_diff = attacker.height - defender.height
        height_mod = 1.0 - max(0, height_diff) * 0.003 if height_diff > 0 else 1.0 + min(0.15, abs(height_diff) * 0.002)

        success_chance = ((takedown_power * 0.5 + takedown_accuracy * 0.5) - (wrestling_defense * 0.4))
        success_chance *= range_penalty * height_mod
        if weight_advantage != 0.0:
            success_chance *= (1.0 + weight_advantage)
        success_chance *= att_leg_mod
        success_chance *= (2.0 - def_leg_mod)
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(5, min(92, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self._set_ground(attacker, defender, Position.GROUND_GUARD)
            if self.cage_position == defender:
                pass
            return True
        return False

    def attempt_clinch(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0,
                       cc_mod: float = 1.0) -> bool:
        if self.current_position not in (Position.POCKET, Position.DISTANCE):
            return False

        if self.current_position == Position.DISTANCE:
            if not self.close_distance(attacker, defender, fatigue):
                return False

        clinch_control = attacker.get_effective_attribute("clinch_control", fatigue) * cc_mod
        clinch_escapes = defender.get_effective_attribute("clinch_escapes", fatigue)
        reach_diff = attacker.reach - defender.reach
        reach_mod = 1.0 - max(0, reach_diff) * 0.004 if reach_diff > 0 else 1.0 + min(0.1, abs(reach_diff) * 0.003)

        success_chance = (clinch_control * 0.7 - clinch_escapes * 0.5) * reach_mod
        success_chance *= max(0.4, 1.0 - fatigue * 0.3)
        success_chance = max(10, min(88, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.CLINCH
            self.clinch_initiator = attacker
            self.position_time = 0
            return True
        return False

    def takedown_from_clinch(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0,
                              td_mod: float = 1.0, tda_mod: float = 1.0, wd_mod: float = 1.0,
                              weight_advantage: float = 0.0, att_leg_mod: float = 1.0, def_leg_mod: float = 1.0) -> bool:
        if self.current_position != Position.CLINCH:
            return False

        td_power = attacker.get_effective_attribute("takedown_power", fatigue) * td_mod * 1.15
        wd = defender.get_effective_attribute("wrestling_defense", fatigue) * wd_mod
        height_diff = attacker.height - defender.height
        height_mod = 1.0 - max(0, height_diff) * 0.003 if height_diff > 0 else 1.0 + abs(height_diff) * 0.002

        # Weight advantage helps in clinch takedowns
        weight_mod = 1.0 + weight_advantage

        success_chance = (td_power - wd * 0.3) * height_mod * weight_mod
        success_chance *= att_leg_mod
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(8, min(88, success_chance))

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
        chain = top.get_effective_attribute("chain_wrestling", fatigue)
        guard_ret = bottom.get_effective_attribute("guard_retention", fatigue)
        scramble = bottom.get_effective_attribute("scrambling", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)

        weight_diff = top.base_weight_lbs - bottom.base_weight_lbs
        weight_mod = 1.0 + min(0.15, max(-0.1, weight_diff / 150))

        # Attacker: top_control + chain_wrestling vs Defender: guard_retention + scrambling + bottom_control
        success_chance = (top_control * 0.40 + chain * 0.35) - (guard_ret * 0.35 + scramble * 0.20 + bottom_control * 0.15)
        success_chance *= weight_mod
        success_chance *= max(0.4, 1.0 - fatigue * 0.3)
        success_chance = max(8, min(80, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_HALF_GUARD
            self.position_time = 0
            return True
        return False

    def pass_half_guard(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_HALF_GUARD:
            return False

        top_control = top.get_effective_attribute("top_control", fatigue)
        chain = top.get_effective_attribute("chain_wrestling", fatigue)
        guard_ret = bottom.get_effective_attribute("guard_retention", fatigue)
        scramble = bottom.get_effective_attribute("scrambling", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        weight_diff = top.base_weight_lbs - bottom.base_weight_lbs
        weight_mod = 1.0 + min(0.15, max(-0.1, weight_diff / 150))

        success_chance = (top_control * 0.35 + chain * 0.30) - (guard_ret * 0.30 + scramble * 0.20 + bottom_control * 0.15)
        success_chance *= weight_mod
        success_chance *= max(0.4, 1.0 - fatigue * 0.3)
        success_chance = max(6, min(75, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_SIDE
            self.position_time = 0
            return True
        return False

    def side_to_north_south(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_SIDE:
            return False

        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        weight_mod = 1.0 + min(0.1, max(-0.1, (top.base_weight_lbs - bottom.base_weight_lbs) / 1000))

        success_chance = top_control * 0.5 - bottom_control * 0.35
        success_chance *= weight_mod
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(4, min(65, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_NORTH_SOUTH
            self.position_time = 0
            return True
        return False

    def north_south_to_mount(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_NORTH_SOUTH:
            return False

        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        weight_mod = 1.0 + min(0.1, max(-0.1, (top.base_weight_lbs - bottom.base_weight_lbs) / 1000))

        success_chance = top_control * 0.45 - bottom_control * 0.25
        success_chance *= weight_mod
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(3, min(60, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_MOUNT
            self.position_time = 0
            return True
        return False

    def take_back_from_turtle(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_TURTLE:
            return False

        top_control = top.get_effective_attribute("top_control", fatigue) * 1.1
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)

        success_chance = top_control * 0.5 - bottom_control * 0.3
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(4, min(65, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_BACK
            self.position_time = 0
            return True
        return False

    def crucifix_from_side(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_SIDE:
            return False

        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)

        success_chance = top_control * 0.4 - bottom_control * 0.2
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(2, min(45, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_CRUCIFIX
            self.position_time = 0
            return True
        return False

    def scarf_hold_from_north_south(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_NORTH_SOUTH:
            return False

        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)

        success_chance = top_control * 0.35 - bottom_control * 0.15
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(2, min(40, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_SCARF_HOLD
            self.position_time = 0
            return True
        return False

    def turtle_roll_to_guard(self, bottom: Fighter, top: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_TURTLE:
            return False

        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        top_control = top.get_effective_attribute("top_control", fatigue)

        success_chance = bottom_control * 0.5 - top_control * 0.3
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(4, min(55, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self._set_ground(bottom, top, Position.GROUND_GUARD)
            return True
        return False

    def granby_roll_to_guard(self, bottom: Fighter, top: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_NORTH_SOUTH:
            return False

        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        top_control = top.get_effective_attribute("top_control", fatigue)

        success_chance = bottom_control * 0.4 - top_control * 0.3
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(3, min(40, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self._set_ground(bottom, top, Position.GROUND_GUARD)
            return True
        return False

    def advance_to_mount(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_NORTH_SOUTH:
            return False
        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        weight_mod = 1.0 + min(0.1, max(-0.1, (top.base_weight_lbs - bottom.base_weight_lbs) / 1000))
        success_chance = top_control * 0.5 - bottom_control * 0.3
        success_chance *= weight_mod
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(4, min(70, success_chance))
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_MOUNT
            self.position_time = 0
            return True
        return False

    def take_back(self, top: Fighter, bottom: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position not in (Position.GROUND_GUARD, Position.GROUND_SIDE, Position.GROUND_HALF_GUARD):
            return False

        top_control = top.get_effective_attribute("top_control", fatigue) * 0.8
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)

        success_chance = top_control * 0.4 - bottom_control * 0.3
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(2, min(50, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_BACK
            self.position_time = 0
            return True
        return False

    def sweep_from_bottom(self, bottom_fighter: Fighter, top_fighter: Fighter, fatigue: float = 0.0) -> bool:
        if not Position.is_ground(self.current_position):
            return False

        pos_factor = {
            Position.GROUND_GUARD: 1.0,
            Position.GROUND_HALF_GUARD: 0.85,
            Position.GROUND_SIDE: 0.7,
            Position.GROUND_NORTH_SOUTH: 0.6,
            Position.GROUND_MOUNT: 0.4,
            Position.GROUND_BACK: 0.2,
            Position.GROUND_TURTLE: 0.5,
            Position.GROUND_CRUCIFIX: 0.15,
            Position.GROUND_SCARF_HOLD: 0.25,
        }.get(self.current_position, 0.5)

        bottom_control = bottom_fighter.get_effective_attribute("bottom_control", fatigue)
        top_control = top_fighter.get_effective_attribute("top_control", fatigue)
        scramble = bottom_fighter.get_effective_attribute("scrambling", fatigue)
        top_scramble = top_fighter.get_effective_attribute("scrambling", fatigue)

        # Weight advantage for the bottom fighter helps sweeps
        weight_mod = 1.0 + min(0.15, max(-0.1, (bottom_fighter.base_weight_lbs - top_fighter.base_weight_lbs) / 800))

        success_chance = (bottom_control * 0.40 + scramble * 0.30 - top_control * 0.30 - top_scramble * 0.10) * pos_factor * weight_mod
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(4, min(70, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self._set_ground(bottom_fighter, top_fighter, Position.GROUND_GUARD)
            return True
        return False

    def stand_up_from_bottom(self, bottom_fighter: Fighter, top_fighter: Fighter, fatigue: float = 0.0) -> bool:
        if not Position.is_ground(self.current_position):
            return False

        pos_factor = {
            Position.GROUND_GUARD: 1.0,
            Position.GROUND_HALF_GUARD: 0.8,
            Position.GROUND_SIDE: 0.8,
            Position.GROUND_NORTH_SOUTH: 0.6,
            Position.GROUND_MOUNT: 0.5,
            Position.GROUND_BACK: 0.3,
            Position.GROUND_TURTLE: 0.7,
            Position.GROUND_CRUCIFIX: 0.3,
            Position.GROUND_SCARF_HOLD: 0.4,
        }.get(self.current_position, 0.5)

        bottom_control = bottom_fighter.get_effective_attribute("bottom_control", fatigue)
        top_control = top_fighter.get_effective_attribute("top_control", fatigue)
        athleticism = bottom_fighter.get_effective_attribute("athleticism", fatigue)
        scramble = bottom_fighter.get_effective_attribute("scrambling", fatigue)

        success_chance = (bottom_control * 0.20 + athleticism * 0.30 + scramble * 0.30 - top_control * 0.35) * pos_factor
        success_chance *= max(0.3, 1.0 - fatigue * 0.4)
        success_chance = max(4, min(75, success_chance))

        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.DISTANCE
            self.top_fighter = None
            self.bottom_fighter = None
            self.position_time = 0
            return True
        return False

    def get_reach_advantage(self, attacker: Fighter, defender: Fighter) -> float:
        """
        Returns a multiplier for strike accuracy based on reach advantage.
        Longer reach = easier to land, shorter reach = must get closer (riskier).
        """
        diff = attacker.reach - defender.reach
        # 1 inch advantage ≈ 0.3% accuracy bonus, 3 inch disadvantage ≈ -0.6%
        return 1.0 + diff * 0.003

    def get_cage_penalty(self, fighter: Fighter) -> float:
        """
        Fighter with back to cage gets movement/defense penalty.
        """
        if self.cage_position == fighter:
            return 0.85  # 15% penalty to evasion/defense
        return 1.0

    def set_cage_position(self, fighter: Fighter):
        """Mark a fighter as being against the cage."""
        self.cage_position = fighter

    def clear_cage_position(self):
        self.cage_position = None

    def get_position_description(self) -> str:
        p = self.current_position
        if p == Position.DISTANCE:
            return "Fighters are at kicking range, measuring each other."
        elif p == Position.POCKET:
            return "Fighters are in the pocket, trading strikes."
        elif p == Position.CLINCH:
            return f"{self.clinch_initiator.name if self.clinch_initiator else 'Unknown'} has secured the clinch."
        elif p == Position.GROUND_GUARD:
            return f"{self.top_fighter.name} is in {self.bottom_fighter.name}'s guard."
        elif p == Position.GROUND_HALF_GUARD:
            return f"{self.top_fighter.name} is in {self.bottom_fighter.name}'s half guard."
        elif p == Position.GROUND_SIDE:
            return f"{self.top_fighter.name} has passed guard and is in side control."
        elif p == Position.GROUND_NORTH_SOUTH:
            return f"{self.top_fighter.name} is in north-south position over {self.bottom_fighter.name}!"
        elif p == Position.GROUND_MOUNT:
            return f"{self.top_fighter.name} has mounted {self.bottom_fighter.name}!"
        elif p == Position.GROUND_BACK:
            return f"{self.top_fighter.name} has {self.bottom_fighter.name}'s back!"
        elif p == Position.GROUND_TURTLE:
            return f"{self.bottom_fighter.name} is turtled up with {self.top_fighter.name} on top."
        elif p == Position.GROUND_CRUCIFIX:
            return f"{self.top_fighter.name} has {self.bottom_fighter.name}'s trapped in a crucifix!"
        elif p == Position.GROUND_SCARF_HOLD:
            return f"{self.top_fighter.name} has {self.bottom_fighter.name} locked in scarf hold."
        elif self.cage_position is not None:
            return f"{self.cage_position.name} is backed against the cage!"
        return "Unknown position"

    @property
    def is_against_cage(self) -> bool:
        return self.cage_position is not None
