from typing import Dict, List, Optional
from datetime import datetime, timedelta
import random
import utils

class Fighter:
    PHYSICAL_ATTRS = [
        "striking_power", "striking_accuracy", "hand_speed",
        "kick_power", "kick_accuracy", "kick_speed",
        "takedown_power", "takedown_accuracy", "wrestling_defense",
        "clinch_control", "clinch_escapes", "clinch_strikes", "clinch_throws",
        "top_control", "bottom_control", "submission_offense", "submission_defense",
        "cardio", "durability", "athleticism"
    ]

    MENTAL_ATTRS = [
        "mental_toughness", "fight_iq", "heart", "discipline",
        "charisma", "aggression", "composure", "adaptability"
    ]

    def __init__(self, name: str, age: int, weight_lbs: float, background: str = "mma", archetype: str = "balanced",
                 nationality: str = "American", home_region: str = "California", trait_id: str = None, personality_id: str = "humble",
                 game_date: datetime = None):
        self.name = name
        self.age = age
        self.base_weight_lbs = weight_lbs
        self.current_weight_lbs = weight_lbs
        self.natural_weight_lbs = weight_lbs
        self.background = background
        self.weight_class = utils.get_weight_class(weight_lbs)
        self.natural_weight_class = self.weight_class
        self.archetype = archetype
        self.nationality = nationality
        self.home_region = home_region
        self.trait_id = trait_id
        self.personality_id = personality_id

        self.height = random.randint(64, 80)
        self.reach = random.randint(64, 84)

        self.attributes = {}
        self._init_attributes()

        self.wins = 0
        self.losses = 0
        self.draws = 0
        self.knockouts = 0
        self.submissions = 0

        self.win_streak = 0
        self.loss_streak = 0
        self.confidence = 50.0

        self.rank = 1000
        self.peak_rank = 1000

        self.injuries = []
        self.medical_suspension_end = None
        self.months_inactive = 0
        self.last_fight_date = None
        now = game_date or datetime.now()
        self.last_training_dates = {
            attr: now
            for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS
        }

        self.net_worth = 0.0
        self.current_contract = None
        self.gym = None
        self.agent = None
        self.agent_name = None

        self.weight_cut_lbs = 0.0
        self.weigh_in_pass = True

        self.retired = False
        self.retirement_date = None

    def _init_attributes(self):
        base = 50
        bg_bonuses = {
            "wrestling": {"takedown_power": 15, "takedown_accuracy": 15, "wrestling_defense": 15, "top_control": 10, "clinch_control": 10},
            "bjj": {"submission_offense": 20, "submission_defense": 15, "bottom_control": 15, "clinch_escapes": 10},
            "muay_thai": {"kick_power": 15, "kick_accuracy": 10, "clinch_control": 15, "clinch_strikes": 15, "clinch_throws": 10},
            "boxing": {"striking_power": 15, "striking_accuracy": 10, "hand_speed": 15, "composure": 5},
            "judo": {"clinch_throws": 20, "clinch_control": 15, "top_control": 10, "wrestling_defense": 5},
            "taekwondo": {"kick_power": 10, "kick_accuracy": 15, "kick_speed": 10, "athleticism": 10},
            "karate": {"striking_accuracy": 15, "hand_speed": 10, "composure": 10, "adaptability": 5, "fight_iq": 5},
            "sambo": {"takedown_power": 10, "takedown_accuracy": 10, "submission_offense": 10, "top_control": 10, "wrestling_defense": 5},
            "kickboxing": {"striking_power": 10, "kick_power": 10, "cardio": 10, "aggression": 5, "hand_speed": 5},
            "capoeira": {"athleticism": 15, "kick_accuracy": 10, "striking_accuracy": 10, "adaptability": 10, "composure": 5},
            "mma": {attr: 5 for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS}
        }
        bonuses = bg_bonuses.get(self.background, bg_bonuses["mma"])
        for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS:
            val = base + bonuses.get(attr, 0)
            self.attributes[attr] = utils.clamp(val, utils.ATTR_MIN, utils.ATTR_MAX)

        if self.trait_id:
            for t in utils.TRAITS:
                if t["id"] == self.trait_id:
                    for attr, bonus in t["effects"].items():
                        if attr in self.attributes:
                            self.attributes[attr] = utils.clamp(self.attributes[attr] + bonus, utils.ATTR_MIN, utils.ATTR_MAX)

        if self.personality_id:
            for p in utils.PERSONALITIES:
                if p["id"] == self.personality_id:
                    for attr, bonus in p["effects"].items():
                        if attr in self.attributes:
                            self.attributes[attr] = utils.clamp(self.attributes[attr] + bonus, utils.ATTR_MIN, utils.ATTR_MAX)

    def get_effective_attribute(self, attr: str, fatigue: float = 0.0) -> int:
        base = self.attributes.get(attr, 50)
        age_mod = utils.get_age_modifier(self.age)

        injury_penalty = 0.0
        for injury in self.injuries:
            if attr in injury.get("affected_attrs", []):
                injury_penalty += injury["severity"] * 0.1

        cut_penalties = utils.weight_cut_penalty(self.weight_cut_lbs)
        if attr == "cardio":
            injury_penalty += cut_penalties["cardio_penalty"]
        elif attr == "durability":
            injury_penalty += cut_penalties["durability_penalty"]

        ring_rust = self.get_ring_rust_penalty()
        confidence_mod = self.get_confidence_modifier()

        effective = base * age_mod * (1.0 - ring_rust) * confidence_mod
        return utils.calculate_effective_attribute(effective, fatigue, injury_penalty)

    def get_ring_rust_penalty(self) -> float:
        if self.months_inactive <= 6:
            return 0.0
        return min(0.25, (self.months_inactive - 6) * 0.03)

    def get_confidence_modifier(self) -> float:
        bonus = self.win_streak * 0.02
        penalty = self.loss_streak * 0.05
        return utils.clamp(1.0 + bonus - penalty, 0.75, 1.15)

    def update_streaks(self, won: bool):
        if won:
            self.win_streak += 1
            self.loss_streak = 0
        else:
            self.loss_streak += 1
            self.win_streak = 0
        self.confidence = 50 + self.win_streak * 5 - self.loss_streak * 8
        self.confidence = utils.clamp(self.confidence, 10, 100)

    def apply_skill_decay(self, game_date: datetime = None):
        now = game_date or datetime.now()
        if not hasattr(self, 'last_training_dates') or not self.last_training_dates:
            return
        for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS:
            last_used = self.last_training_dates.get(attr)
            if last_used is None:
                continue
            months_unused = (now - last_used).days / 30
            if months_unused >= 2:
                excess_months = months_unused - 1
                decay = 0.02 * excess_months
                self.attributes[attr] = utils.clamp(
                    self.attributes[attr] * (1 - decay),
                    utils.ATTR_MIN,
                    utils.ATTR_MAX
                )

    def monthly_aging(self, game_date: datetime = None):
        self.months_inactive += 1
        self.apply_skill_decay(game_date)

    def cut_weight(self, target_weight_lbs: float) -> bool:
        self.weight_cut_lbs = max(0, self.base_weight_lbs - target_weight_lbs)
        if self.weight_cut_lbs > 10 and utils.random_roll(1, 100) <= 10:
            self.weigh_in_pass = False
            return False
        self.current_weight_lbs = target_weight_lbs
        self.weigh_in_pass = True
        return True

    def adjust_weight(self, new_weight_lbs: float):
        self.base_weight_lbs = new_weight_lbs
        self.current_weight_lbs = new_weight_lbs
        self.weight_class = utils.get_weight_class(new_weight_lbs)

    def add_injury(self, injury_type: str, severity: float, affected_attrs: List[str], recovery_days: int, game_date: datetime = None):
        now = game_date or datetime.now()
        self.injuries.append({
            "type": injury_type,
            "severity": severity,
            "affected_attrs": affected_attrs,
            "recovery_end": now + timedelta(days=recovery_days)
        })

    def recover_injuries(self, game_date: datetime = None):
        now = game_date or datetime.now()
        self.injuries = [i for i in self.injuries if i["recovery_end"] > now]

    def update_rank(self, new_rank: int):
        self.rank = new_rank
        if new_rank < self.peak_rank:
            self.peak_rank = new_rank

    def get_overall_rating(self) -> float:
        return utils.calculate_rating_from_attrs(self.attributes, self.PHYSICAL_ATTRS, self.MENTAL_ATTRS)

    def has_medical_suspension(self, game_date: datetime = None) -> bool:
        if not self.medical_suspension_end:
            return False
        now = game_date or datetime.now()
        return now < self.medical_suspension_end

    def is_available(self, game_date: datetime = None) -> bool:
        return (not self.retired
                and not self.injuries
                and not self.has_medical_suspension(game_date))

    def shake_ring_rust(self):
        self.months_inactive = 0

    def get_record_string(self) -> str:
        return f"{self.wins}-{self.losses}-{self.draws}"
