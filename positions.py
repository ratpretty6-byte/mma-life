from __future__ import annotations
from enum import Enum
from typing import Optional, Dict
import utils
from fighter import Fighter

class Position(Enum):
    STANDING = "Standing"
    CLINCH = "Clinch"
    GROUND_TOP = "Ground (Top)"
    GROUND_BOTTOM = "Ground (Bottom)"

class PositionSystem:
    def __init__(self, fighter1: Fighter, fighter2: Fighter):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.current_position = Position.STANDING
        self.top_fighter: Optional[Fighter] = None
        self.bottom_fighter: Optional[Fighter] = None
        self.clinch_initiator: Optional[Fighter] = None
        self.position_time = 0
    
    def attempt_takedown(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
        takedown_power = attacker.get_effective_attribute("takedown_power", fatigue)
        takedown_accuracy = attacker.get_effective_attribute("takedown_accuracy", fatigue)
        wrestling_defense = defender.get_effective_attribute("wrestling_defense", fatigue)
        
        success_chance = (takedown_power * 0.4 + takedown_accuracy * 0.6) - (wrestling_defense * 0.5)
        success_chance = max(5, min(95, success_chance))
        
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_TOP
            self.top_fighter = attacker
            self.bottom_fighter = defender
            self.position_time = 0
            return True
        return False
    
    def attempt_clinch(self, attacker: Fighter, defender: Fighter, fatigue: float = 0.0) -> bool:
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
            self.current_position = Position.STANDING
            self.clinch_initiator = None
            self.position_time = 0
            return True
        return False
    
    def sweep_from_bottom(self, bottom_fighter: Fighter, top_fighter: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_BOTTOM:
            return False
        
        bottom_control = bottom_fighter.get_effective_attribute("bottom_control", fatigue)
        top_control = top_fighter.get_effective_attribute("top_control", fatigue)
        
        success_chance = bottom_control * 0.6 - top_control * 0.4
        success_chance = max(10, min(80, success_chance))
        
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.GROUND_TOP
            self.top_fighter = bottom_fighter
            self.bottom_fighter = top_fighter
            self.position_time = 0
            return True
        return False
    
    def stand_up_from_bottom(self, bottom_fighter: Fighter, top_fighter: Fighter, fatigue: float = 0.0) -> bool:
        if self.current_position != Position.GROUND_BOTTOM:
            return False
        
        bottom_control = bottom_fighter.get_effective_attribute("bottom_control", fatigue)
        top_control = top_fighter.get_effective_attribute("top_control", fatigue)
        athleticism = bottom_fighter.get_effective_attribute("athleticism", fatigue)
        
        success_chance = (bottom_control * 0.4 + athleticism * 0.6) - top_control * 0.5
        success_chance = max(5, min(75, success_chance))
        
        if utils.random_roll(1, 100) <= success_chance:
            self.current_position = Position.STANDING
            self.top_fighter = None
            self.bottom_fighter = None
            self.position_time = 0
            return True
        return False
    
    def get_position_description(self) -> str:
        if self.current_position == Position.STANDING:
            return "Fighters are trading strikes at range."
        elif self.current_position == Position.CLINCH:
            initiator = self.clinch_initiator.name if self.clinch_initiator else "Unknown"
            return f"{initiator} has secured the clinch."
        elif self.current_position == Position.GROUND_TOP:
            return f"{self.top_fighter.name} is controlling {self.bottom_fighter.name} on the ground."
        elif self.current_position == Position.GROUND_BOTTOM:
            return f"{self.bottom_fighter.name} is on the bottom, trying to escape {self.top_fighter.name}'s control."
        return "Unknown position"
