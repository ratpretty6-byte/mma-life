import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import utils


class Fighter:
    PHYSICAL_ATTRS = [
        "striking_power", "striking_accuracy", "hand_speed",
        "kick_power", "kick_accuracy", "kick_speed",
        "takedown_power", "takedown_accuracy", "wrestling_defense",
        "clinch_control", "clinch_escapes", "clinch_strikes", "clinch_throws",
        "top_control", "bottom_control", "submission_offense", "submission_defense",
        "cardio", "durability", "athleticism",
        # Defensive striking
        "head_movement", "footwork_defense", "blocking", "parrying", "counter_timing",
        # Takedown / grappling defense
        "sprawl_technique", "chain_wrestling", "guard_retention", "scrambling",
        "ground_striking_defense", "submission_awareness",
        # Physical differentiation
        "explosiveness", "flexibility",
    ]

    MENTAL_ATTRS = [
        "mental_toughness", "fight_iq", "heart", "discipline",
        "charisma", "aggression", "composure", "adaptability",
        "danger_recognition", "pace_management",
    ]

    # Prime age range: 24-33 is peak performance
    PRIME_START = 24
    PRIME_END = 33
    DECLINE_START = 34
    STEEP_DECLINE = 39

    # 11 body zones — more granular than old head/body/legs model
    BODY_ZONES = [
        "left_eye", "right_eye", "jaw", "temple", "nose",
        "chest", "solar_plexus", "liver", "ribs",
        "lead_leg", "rear_leg"
    ]

    # Zone damage multipliers — how much a hit to this zone hurts
    ZONE_KO_MULTIPLIER = {
        "jaw": 1.4, "temple": 1.8, "nose": 1.0,
        "left_eye": 0.7, "right_eye": 0.7,
        "solar_plexus": 1.3, "liver": 1.5, "ribs": 0.9,
        "chest": 0.6,
        "lead_leg": 0.5, "rear_leg": 0.6
    }

    # Zone group mapping for scoring/display
    ZONE_GROUPS = {
        "left_eye": "head", "right_eye": "head", "jaw": "head",
        "temple": "head", "nose": "head",
        "chest": "body", "solar_plexus": "body", "liver": "body", "ribs": "body",
        "lead_leg": "legs", "rear_leg": "legs"
    }

    def __init__(self, name: str, age: int, weight_lbs: float, background: str = "mma", archetype: str = "balanced",
                 nationality: str = "American", home_region: str = "California", trait_id: str = None, personality_id: str = "humble",
                 stance: str = None, game_date: datetime = None, height: int = None, reach: int = None):
        self.is_player = False
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
        self.stance = stance or utils.get_stance_for_background(background)

        # Height and reach based on weight class, with explicit parameter override
        if height is not None and reach is not None:
            self.height = height
            self.reach = reach
        else:
            hr_range = utils.get_height_reach_range(self.weight_class)
            self.height = utils.gaussian_random(
                (hr_range["height_min"] + hr_range["height_max"]) // 2, 3,
                hr_range["height_min"], hr_range["height_max"]
            )
            self.reach = utils.gaussian_random(
                (hr_range["reach_min"] + hr_range["reach_max"]) // 2, 3,
                hr_range["reach_min"], hr_range["reach_max"]
            )

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
        self.hydration_level = 80.0  # 0-100, affects recovery post-weigh-in
        self.cut_history = []  # list of dicts: {cut_lbs: float, success: bool, fight_date: datetime}

        self.retired = False
        self.retirement_date = None

        # Cumulative trauma tracking (career damage)
        self.career_damage_taken = 0.0
        self.career_ko_losses = 0
        self.career_total_fights = 0
        self.concussion_count = 0

        # Signature move tracking
        self.signature_strikes = {}
        self.nickname = None

        # Scouting data
        self.times_scouted = 0
        self.preferred_strategies = []

        # Weight migration state
        self.migrating_weight_class = None
        self.migration_camps_remaining = 0
        self._style_evolution_tracker: Dict[str, int] = {}

    def __eq__(self, other):
        if not isinstance(other, Fighter):
            return NotImplemented
        db_id = getattr(self, '_db_id', None)
        other_id = getattr(other, '_db_id', None)
        if db_id is not None and other_id is not None:
            return db_id == other_id
        return self.name == other.name and self.age == other.age

    def __hash__(self):
        db_id = getattr(self, '_db_id', None)
        if db_id is not None:
            return hash(db_id)
        name = getattr(self, 'name', None)
        if name is not None:
            return hash((name, getattr(self, 'age', 0)))
        return hash(id(self))

    def _init_attributes(self):
        base = 50
        bg_bonuses = {
            "wrestling": {
                "takedown_power": 12, "takedown_accuracy": 12, "wrestling_defense": 12,
                "top_control": 10, "clinch_control": 8, "chain_wrestling": 10,
                "sprawl_technique": 8, "explosiveness": 8,
                "ground_striking_defense": 5, "scrambling": 5,
            },
            "bjj": {
                "submission_offense": 15, "submission_defense": 12, "bottom_control": 12,
                "guard_retention": 12, "submission_awareness": 10, "flexibility": 10,
                "scrambling": 8, "clinch_escapes": 8,
            },
            "muay_thai": {
                "kick_power": 12, "kick_accuracy": 8, "clinch_control": 12,
                "clinch_strikes": 12, "clinch_throws": 8, "blocking": 8,
                "parrying": 5, "flexibility": 5,
            },
            "boxing": {
                "striking_power": 10, "striking_accuracy": 8, "hand_speed": 12,
                "head_movement": 12, "blocking": 8, "parrying": 8,
                "counter_timing": 10, "footwork_defense": 8, "composure": 5,
            },
            "judo": {
                "clinch_throws": 15, "clinch_control": 12, "top_control": 8,
                "wrestling_defense": 5, "scrambling": 8, "explosiveness": 8,
                "flexibility": 8, "guard_retention": 5,
            },
            "taekwondo": {
                "kick_power": 10, "kick_accuracy": 12, "kick_speed": 10,
                "flexibility": 10, "athleticism": 8, "footwork_defense": 8,
            },
            "karate": {
                "striking_accuracy": 12, "hand_speed": 8, "head_movement": 10,
                "counter_timing": 8, "composure": 10, "adaptability": 5,
                "fight_iq": 5, "parrying": 5,
            },
            "sambo": {
                "takedown_power": 8, "takedown_accuracy": 8, "submission_offense": 10,
                "top_control": 8, "chain_wrestling": 10, "sprawl_technique": 8,
                "wrestling_defense": 5, "explosiveness": 8,
            },
            "kickboxing": {
                "striking_power": 8, "kick_power": 8, "cardio": 8,
                "blocking": 8, "footwork_defense": 8, "hand_speed": 5,
                "aggression": 5,
            },
            "capoeira": {
                "athleticism": 12, "kick_accuracy": 8, "striking_accuracy": 8,
                "adaptability": 8, "flexibility": 10, "footwork_defense": 8,
                "composure": 5,
            },
            "mma": {attr: 4 for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS}
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

    def reset_fight_data(self):
        self._zone_health = {}
        self._zone_max_health = {}
        self._blood_level = 0.0

    def init_fight_health(self):
        """Initialize 9-zone health model for a fight. Based on durability + age."""
        self.reset_fight_data()
        durability = self.attributes.get("durability", 50)
        age_mod = utils.get_age_modifier(self.age)
        base_health = durability * age_mod

        # Some zones naturally have lower health
        zone_base = {
            "left_eye": 0.75, "right_eye": 0.75,
            "jaw": 0.70,
            "temple": 0.65,
            "nose": 0.85,
            "chest": 0.95,
            "solar_plexus": 0.85,
            "liver": 0.80,
            "ribs": 0.85,
            "lead_leg": 0.90,
            "rear_leg": 0.90,
        }

        self._zone_health = {}
        self._zone_max_health = {}
        for zone in self.BODY_ZONES:
            max_h = base_health * zone_base.get(zone, 1.0)
            # Random variance: ±8% with a floor to prevent ZeroDivisionError
            max_h = max(5.0, max_h * (1.0 + random.uniform(-0.08, 0.08)))
            self._zone_max_health[zone] = max_h
            self._zone_health[zone] = max_h

        # Blood tracking
        self._blood_level = 0.0  # 0-100, blood in eyes/vision

    def get_zone_health(self, zone: str) -> float:
        return max(0, self._zone_health.get(zone, 50))

    def get_zone_health_pct(self, zone: str) -> float:
        max_h = self._zone_max_health.get(zone, 50)
        return max(0, self._zone_health.get(zone, 50) / max_h * 100)

    def get_group_health(self, group: str) -> float:
        """Get average health percentage for a body group (head/body/legs)."""
        zones = [z for z, g in self.ZONE_GROUPS.items() if g == group]
        if not zones:
            return 100
        return sum(self.get_zone_health_pct(z) for z in zones) / len(zones)

    def get_overall_health_pct(self) -> float:
        return sum(self.get_group_health(g) for g in ["head", "body", "legs"]) / 3.0

    def apply_damage_to_zone(self, zone: str, raw_damage: float, fight) -> float:
        """Apply damage to a specific body zone. Returns actual damage dealt."""
        # Map group-level targets ("head", "body", "legs") to random specific zones
        target_zone = zone
        if zone == "head":
            target_zone = random.choice(["left_eye", "right_eye", "jaw", "temple", "nose"])
        elif zone == "body":
            target_zone = random.choice(["chest", "solar_plexus", "liver", "ribs"])
        elif zone == "legs":
            target_zone = random.choice(["lead_leg", "rear_leg"])

        zone_mult = self.ZONE_KO_MULTIPLIER.get(target_zone, 1.0)
        effective_damage = raw_damage * zone_mult

        current = self._zone_health.get(target_zone, 50)
        new_health = max(0, current - effective_damage)
        actual_damage = current - new_health
        self._zone_health[target_zone] = new_health

        # Damage to eyes causes vision impairment (blood)
        if target_zone in ("left_eye", "right_eye"):
            fight._add_blood(self, effective_damage)

        # Damage to jaw/temple contributes to head KO tracker
        if target_zone in ("jaw", "temple", "left_eye", "right_eye", "nose"):
            fight._track_head_damage(self, effective_damage)
            fight._track_ko_accumulation(self, effective_damage, zone_mult)

        return actual_damage

    def get_chin_resistance(self) -> float:
        """
        Chin resistance — higher = harder to KO.
        Based on mental toughness, durability, composure, heart, and fighting spirit.
        Returns threshold: KO happens when accumulated head damage exceeds this.
        """
        base = (
            self.attributes.get("durability", 50) * 0.30 +
            self.attributes.get("mental_toughness", 50) * 0.25 +
            self.attributes.get("composure", 50) * 0.20 +
            self.attributes.get("heart", 50) * 0.15 +
            self.attributes.get("aggression", 50) * 0.10
        )
        # Age factor: older fighters have lower chin resistance
        age_mod = 1.0 - max(0, (self.age - 30)) * 0.005
        return base * age_mod * 2.0

    def get_effective_attribute(self, attr: str, fatigue: float = 0.0, in_fight: bool = False) -> int:
        base = self.attributes.get(attr, 50)
        age_mod = self.get_prime_age_modifier()

        injury_penalty = 0.0
        for injury in self.injuries:
            if attr in injury.get("affected_attrs", []):
                injury_penalty += injury["severity"] * 0.1

        cut_penalties = utils.weight_cut_penalty(self.weight_cut_lbs, self.hydration_level)
        if attr == "cardio":
            injury_penalty += cut_penalties["cardio_penalty"]
        elif attr == "durability":
            injury_penalty += cut_penalties["durability_penalty"]
        elif attr in ("striking_power", "kick_power"):
            injury_penalty += cut_penalties["strength_penalty"]
        elif attr in ("hand_speed", "kick_speed"):
            injury_penalty += cut_penalties["speed_penalty"]
        elif attr in ("chin_resistance", "mental_toughness"):
            injury_penalty += cut_penalties["chin_penalty"]

        ring_rust = self.get_ring_rust_penalty(in_fight=in_fight)
        confidence_mod = self.get_confidence_modifier()

        effective = base * age_mod * (1.0 - ring_rust) * confidence_mod
        return utils.calculate_effective_attribute(effective, fatigue, injury_penalty)

    def get_prime_age_modifier(self) -> float:
        if self.age < self.PRIME_START:
            return 0.85 + (self.age - 18) * 0.025
        elif self.age <= self.PRIME_END:
            return 1.0
        elif self.age < self.STEEP_DECLINE:
            return max(0.85, 1.0 - (self.age - self.PRIME_END) * 0.02)
        else:
            return max(0.70, 1.0 - (self.age - self.STEEP_DECLINE) * 0.04)

    def get_ring_rust_penalty(self, in_fight: bool = False) -> float:
        if self.months_inactive <= 4:
            return 0.0
        base = min(0.25, (self.months_inactive - 4) * 0.03)
        if in_fight:
            return base * 1.5
        return base

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
        all_untrained_months = 999
        for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS:
            last_used = self.last_training_dates.get(attr)
            if last_used is None:
                continue
            months_unused = (now - last_used).days / 30
            all_untrained_months = min(all_untrained_months, months_unused)
        if all_untrained_months < 4:
            return
        for attr in self.PHYSICAL_ATTRS + self.MENTAL_ATTRS:
            if self.attributes.get(attr, 50) <= 30:
                continue
            self.attributes[attr] = max(30, self.attributes[attr] - 0.5)

    def monthly_aging(self, game_date: datetime = None):
        self.months_inactive += 1
        self.apply_skill_decay(game_date)
        self.apply_career_trauma_effects()

    def apply_career_trauma_effects(self):
        cumul = self.career_damage_taken
        if cumul >= 700 and random.random() < 0.05:
            self.retired = True
        trauma_reduction = 0
        if cumul >= 500:
            trauma_reduction = 5
        elif cumul >= 300:
            trauma_reduction = 3
        elif cumul >= 100:
            trauma_reduction = 1
        if trauma_reduction > 0:
            for attr in self.PHYSICAL_ATTRS:
                self.attributes[attr] = max(utils.ATTR_MIN, self.attributes[attr] - trauma_reduction * 0.02)

    def record_fight_damage(self, damage_taken: float, was_ko: bool = False):
        self.career_damage_taken += damage_taken
        self.career_total_fights += 1
        if was_ko:
            self.career_ko_losses += 1

    def record_training_type(self, drill_type: str, count: int = 1):
        self._style_evolution_tracker[drill_type] = self._style_evolution_tracker.get(drill_type, 0) + count

    def check_style_evolution(self) -> Optional[str]:
        if not self._style_evolution_tracker:
            return None
        total = sum(self._style_evolution_tracker.values())
        if total < 12:
            return None
        dominant = max(self._style_evolution_tracker, key=self._style_evolution_tracker.get)
        dominant_count = self._style_evolution_tracker[dominant]
        ratio = dominant_count / total

        if ratio < 0.4:
            return None
        if self.age > 33 and random.random() < 0.3:
            if self.archetype in ["brawler", "boxer", "kickboxer"]:
                return "counter_striker"
        if self.age < 25 and dominant in ("striking", "clinch", "grappling") and random.random() < 0.15:
            arch_map = {"striking": "boxer", "clinch": "muay_thai", "grappling": "submission_artist",
                        "sparring": "balanced", "conditioning": "balanced", "mental": "counter_striker"}
            new_arch = arch_map.get(dominant)
            if new_arch and new_arch != self.archetype and random.random() < 0.1:
                return new_arch
        return None

    def record_signature_strike(self, strike_type: str):
        self.signature_strikes[strike_type] = self.signature_strikes.get(strike_type, 0) + 1

    def get_signature_strike(self) -> Optional[str]:
        if not self.signature_strikes:
            return None
        best = max(self.signature_strikes, key=self.signature_strikes.get)
        if self.signature_strikes[best] >= 20:
            return best
        return None

    def cut_weight(self, target_weight_lbs: float, is_title_fight: bool = False, intensity: str = "standard") -> bool:
        """
        Full weight cutting system.
        Factors: cut size, discipline, cardio, age, cumulative damage from past cuts.
        intensity: safe (+10% success), standard, aggressive (-10% success, worse hydration)
        Returns True if weigh-in passed.
        """
        self.weight_cut_lbs = max(0, self.base_weight_lbs - target_weight_lbs)

        if self.weight_cut_lbs <= 0:
            self.current_weight_lbs = target_weight_lbs
            self.weigh_in_pass = True
            self.hydration_level = 90.0
            return True

        cut_ratio = self.weight_cut_lbs / max(1, self.base_weight_lbs)
        discipline = self.attributes.get("discipline", 50)
        cardio = self.attributes.get("cardio", 50)
        age = self.age

        # Base success chance with modifiers
        success_chance = 0.92
        success_chance -= cut_ratio * 0.50
        success_chance += (discipline - 50) * 0.003
        success_chance += (cardio - 50) * 0.002
        success_chance -= max(0, (age - 30)) * 0.008
        success_chance -= len(self.cut_history) * 0.02

        # Intensity modifier
        intensity_mult = {"safe": 0.10, "standard": 0.0, "aggressive": -0.10}
        success_chance += intensity_mult.get(intensity, 0.0)

        # Cumulative cut damage
        avg_cut = 0.0
        if self.cut_history:
            avg_cut = sum(h["cut_lbs"] for h in self.cut_history) / len(self.cut_history)
            if avg_cut > 12:
                success_chance -= 0.05
            if avg_cut > 18:
                success_chance -= 0.10

        if is_title_fight:
            success_chance -= 0.05

        success_chance = utils.clamp(success_chance, 0.05, 0.98)

        self.weigh_in_pass = random.random() < success_chance
        self.current_weight_lbs = target_weight_lbs

        # Record cut history
        self.cut_history.append({
            "cut_lbs": self.weight_cut_lbs,
            "success": self.weigh_in_pass,
            "fight_date": datetime.now()
        })

        # Rehydration — intensity affects hydration recovery
        if self.weigh_in_pass:
            base_hydration = 60.0
            base_hydration += (discipline - 50) * 0.3
            base_hydration += (cardio - 50) * 0.2
            base_hydration -= self.weight_cut_lbs * 1.5
            hyd_mult = {"safe": 1.2, "standard": 1.0, "aggressive": 0.7}
            base_hydration *= hyd_mult.get(intensity, 1.0)
            self.hydration_level = utils.clamp(base_hydration, 10.0, 100.0)
        else:
            hyd_penalty = {"safe": 10, "standard": 20, "aggressive": 30}
            self.hydration_level = utils.clamp(self.hydration_level - hyd_penalty.get(intensity, 20), 5.0, 100.0)

        return self.weigh_in_pass

    def migrate_weight_class_up(self, target_weight: float) -> bool:
        if self.migration_camps_remaining > 0:
            return False
        target_wc = utils.get_weight_class(target_weight)
        current_idx = utils.get_weight_class_index(self.weight_class)
        target_idx = utils.get_weight_class_index(target_wc)
        if target_idx <= current_idx:
            return False
        self.migrating_weight_class = target_wc
        self.migration_camps_remaining = 2
        return True

    def migrate_weight_class_down(self, target_weight: float) -> bool:
        if self.migration_camps_remaining > 0:
            return False
        target_wc = utils.get_weight_class(target_weight)
        current_idx = utils.get_weight_class_index(self.weight_class)
        target_idx = utils.get_weight_class_index(target_wc)
        if target_idx >= current_idx:
            return False
        self.migrating_weight_class = target_wc
        self.migration_camps_remaining = 2
        return True

    def advance_migration(self):
        if self.migration_camps_remaining <= 0:
            return False
        self.migration_camps_remaining -= 1
        if self.migration_camps_remaining <= 0 and self.migrating_weight_class:
            current_idx = utils.get_weight_class_index(self.weight_class)
            target_idx = utils.get_weight_class_index(self.migrating_weight_class)
            is_up = target_idx > current_idx
            for wc in utils.WEIGHT_CLASSES:
                if wc["name"] == self.migrating_weight_class:
                    new_weight = random.randint(wc["min"], wc["max"])
                    self.adjust_weight(new_weight)
                    if is_up:
                        for attr in ["hand_speed", "kick_speed", "athleticism", "cardio"]:
                            self.attributes[attr] = utils.clamp(
                                self.attributes.get(attr, 50) - 4, utils.ATTR_MIN, utils.ATTR_MAX)
                        for attr in ["striking_power", "durability"]:
                            self.attributes[attr] = utils.clamp(
                                self.attributes.get(attr, 50) + 3, utils.ATTR_MIN, utils.ATTR_MAX)
                    else:
                        for attr in ["hand_speed", "kick_speed", "athleticism", "cardio"]:
                            self.attributes[attr] = utils.clamp(
                                self.attributes.get(attr, 50) + 4, utils.ATTR_MIN, utils.ATTR_MAX)
                        for attr in ["striking_power", "durability"]:
                            self.attributes[attr] = utils.clamp(
                                self.attributes.get(attr, 50) - 3, utils.ATTR_MIN, utils.ATTR_MAX)
                    break
            self.migrating_weight_class = None
            return True
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
