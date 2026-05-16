from typing import Dict, List, Optional
from fighter import Fighter
import random
from datetime import datetime
import utils

class TrainingDrill:
    def __init__(self, name: str, drill_type: str, affected_attrs: List[str],
                 duration_days: int, base_gain: float, fatigue_rate: float, injury_risk: float):
        self.name = name
        self.drill_type = drill_type
        self.affected_attrs = affected_attrs
        self.duration_days = duration_days
        self.base_gain = base_gain
        self.fatigue_rate = fatigue_rate
        self.injury_risk = injury_risk

DRILLS = [
    TrainingDrill("Hand Speed Drills", "striking", ["hand_speed", "striking_accuracy", "kick_speed"], 7, 0.5, 0.05, 0.01),
    TrainingDrill("Footwork & Movement", "striking", ["athleticism", "adaptability", "composure"], 7, 0.4, 0.04, 0.005),
    TrainingDrill("Combination Work", "striking", ["striking_power", "hand_speed", "fight_iq"], 10, 0.6, 0.07, 0.02),
    TrainingDrill("Takedown Chains", "grappling", ["takedown_power", "takedown_accuracy", "athleticism"], 10, 0.7, 0.08, 0.03),
    TrainingDrill("Wrestling & Sprawl", "grappling", ["wrestling_defense", "clinch_escapes", "cardio", "durability"], 7, 0.5, 0.06, 0.02),
    TrainingDrill("Clinch Control", "clinch", ["clinch_control", "clinch_strikes", "clinch_escapes"], 7, 0.6, 0.07, 0.02),
    TrainingDrill("Clinch Throws", "clinch", ["clinch_throws", "clinch_strikes", "takedown_power"], 7, 0.5, 0.08, 0.03),
    TrainingDrill("Ground and Pound", "grappling", ["top_control", "striking_power", "submission_offense"], 10, 0.7, 0.09, 0.03),
    TrainingDrill("Submission Defense", "grappling", ["submission_defense", "submission_offense", "bottom_control", "mental_toughness"], 10, 0.6, 0.07, 0.02),
    TrainingDrill("Sparring (Striking)", "sparring", ["striking_power", "striking_accuracy", "hand_speed", "composure", "kick_power", "aggression", "charisma"], 5, 1.0, 0.15, 0.05),
    TrainingDrill("Sparring (Grappling)", "sparring", ["takedown_accuracy", "submission_offense", "top_control", "bottom_control", "adaptability", "submission_defense"], 5, 1.0, 0.15, 0.05),
    TrainingDrill("Kick Conditioning", "kick", ["kick_power", "kick_accuracy", "kick_speed", "athleticism"], 7, 0.6, 0.06, 0.02),
    TrainingDrill("Fight Conditioning", "conditioning", ["cardio", "durability", "mental_toughness", "heart"], 7, 0.5, 0.04, 0.01),
    TrainingDrill("Mental Training", "mental", ["fight_iq", "discipline", "charisma", "composure", "adaptability", "aggression"], 7, 0.5, 0.03, 0.005),
    TrainingDrill("Head Movement Drills", "defense", ["head_movement", "footwork_defense", "counter_timing"], 7, 0.5, 0.05, 0.01),
    TrainingDrill("Defensive Fundamentals", "defense", ["blocking", "parrying", "danger_recognition"], 7, 0.5, 0.04, 0.01),
    TrainingDrill("Reactive Counters", "sparring", ["counter_timing", "head_movement", "fight_iq"], 5, 1.0, 0.15, 0.05),
    TrainingDrill("Sprawl & Scramble", "grappling", ["sprawl_technique", "scrambling", "explosiveness"], 7, 0.6, 0.07, 0.02),
    TrainingDrill("Chain Wrestling", "grappling", ["chain_wrestling", "takedown_power", "takedown_accuracy"], 10, 0.7, 0.08, 0.03),
    TrainingDrill("Guard Retention", "grappling", ["guard_retention", "flexibility", "bottom_control"], 7, 0.5, 0.06, 0.02),
    TrainingDrill("Ground Defense", "grappling", ["ground_striking_defense", "submission_awareness", "durability"], 10, 0.6, 0.07, 0.02),
    TrainingDrill("Pace & Distance", "mental", ["pace_management", "cardio", "danger_recognition"], 7, 0.4, 0.03, 0.005),
]

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class TrainingSystem:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.current_drill: Optional[TrainingDrill] = None
        self.intensity = "moderate"
        self.days_trained = 0
        self.total_days_elapsed = 0
        self.fatigue = 0.0
        self.in_training = False
        self.weekly_schedule: Dict[int, Optional[str]] = {}
        self.current_week_day = 0
        self.week_started = False
        self.fight_camp_active = False
        self.recovery_active = False
        self.recovery_type = None
        self.film_study_sessions = 0

    def start_film_study(self) -> bool:
        if self.film_study_sessions >= 2:
            return False
        self.film_study_sessions += 1
        for attr in ["fight_iq", "adaptability", "danger_recognition", "pace_management"]:
            old_val = self.fighter.attributes.get(attr, 50)
            new_val = utils.clamp(old_val + 0.08, utils.ATTR_MIN, utils.ATTR_MAX)
            self.fighter.attributes[attr] = new_val
        return True

    def start_recovery(self, recovery_type: str) -> bool:
        if self.recovery_active:
            return False
        self.recovery_active = True
        self.recovery_type = recovery_type
        return True

    def process_recovery(self) -> Optional[str]:
        if not self.recovery_active:
            return None
        result = None
        if self.recovery_type == "ice_bath":
            old_fatigue = self.fatigue
            self.fatigue = max(0.0, self.fatigue - 0.25)
            result = f"Ice bath reduced fatigue from {old_fatigue:.0%} to {self.fatigue:.0%}"
        elif self.recovery_type == "sports_massage":
            for attr in self.fighter.PHYSICAL_ATTRS:
                if random.random() < 0.3:
                    val = self.fighter.attributes.get(attr, 50)
                    self.fighter.attributes[attr] = utils.clamp(val + 0.02, utils.ATTR_MIN, utils.ATTR_MAX)
            result = "Sports massage helped muscle recovery"
        elif self.recovery_type == "nutrition_plan":
            self.fatigue = max(0.0, self.fatigue - 0.1)
            result = "Nutrition plan boosts recovery rate"
        elif self.recovery_type == "meditation":
            comp = self.fighter.attributes.get("composure", 50)
            self.fighter.attributes["composure"] = utils.clamp(comp + 0.1, utils.ATTR_MIN, utils.ATTR_MAX)
            result = "Meditation improved mental composure"
        self.recovery_active = False
        self.recovery_type = None
        return result

    def auto_fill_schedule(self, drill: TrainingDrill):
        for d in range(5):
            self.weekly_schedule[d] = drill.name
        for d in range(5, 7):
            self.weekly_schedule[d] = None
        self.current_week_day = 0
        self.week_started = True

    def set_day_drill(self, day_idx: int, drill_name: Optional[str]):
        if 0 <= day_idx <= 6:
            self.weekly_schedule[day_idx] = drill_name

    def get_today_drill(self) -> Optional[TrainingDrill]:
        name = self.weekly_schedule.get(self.current_week_day)
        if name is None:
            return None
        for d in DRILLS:
            if d.name == name:
                return d
        return None

    def start_training(self, drill: TrainingDrill, intensity: str = "moderate") -> bool:
        if self.in_training:
            return False
        self.current_drill = drill
        self.intensity = intensity
        self.days_trained = 0
        self.total_days_elapsed = 0
        self.in_training = True
        self.auto_fill_schedule(drill)
        return True

    def _find_gym(self, gym_name: str) -> Optional[Dict]:
        for g in utils.GYMS:
            if g["name"] == gym_name:
                return g
        return None

    def advance_day(self, game_date: Optional[datetime] = None) -> Dict:
        drill = self.get_today_drill()
        is_rest = drill is None

        recovery_result = self.process_recovery() if self.recovery_active else None

        result = {"day": DAYS_OF_WEEK[self.current_week_day], "is_rest": is_rest,
                  "gains": {}, "fatigue": self.fatigue, "injury": None,
                  "drill_over": False, "recovery": recovery_result}

        if not self.in_training:
            result["status"] = "idle"
            self._advance_week_day()
            return result

        if is_rest:
            self.fatigue = max(0.0, self.fatigue - 0.35)
            result["status"] = "rest"
            result["fatigue"] = self.fatigue
            for attr in self.fighter.PHYSICAL_ATTRS + self.fighter.MENTAL_ATTRS:
                old_val = self.fighter.attributes[attr]
                # Small upkeep gain on rest days
                new_val = utils.clamp(old_val + 0.05, utils.ATTR_MIN, utils.ATTR_MAX)
                self.fighter.attributes[attr] = new_val
                if new_val - old_val > 0:
                    result["gains"][attr] = new_val - old_val
            self._advance_week_day()
            return result

        self.current_drill = drill
        self.days_trained += 1
        intensity_mult = {"light": 0.6, "moderate": 1.0, "intense": 1.4}.get(self.intensity, 1.0)

        gym_bonus = 0.0
        if self.fighter.gym:
            gym = self._find_gym(self.fighter.gym)
            if gym:
                if drill.drill_type in gym["specialties"]:
                    gym_bonus = gym["coach_bonus"] * 0.75
                else:
                    gym_bonus = gym["coach_bonus"] * 0.25

        gain_mult = 1.0 + gym_bonus
        overtraining_mult = max(0.3, 1.0 - max(0, self.fatigue - 0.7) * 2.0)

        gains = {}
        for attr in drill.affected_attrs:
            gain = drill.base_gain * intensity_mult * gain_mult * overtraining_mult * 1.5
            old_val = self.fighter.attributes[attr]
            new_val = utils.clamp(old_val + gain, utils.ATTR_MIN, utils.ATTR_MAX)
            self.fighter.attributes[attr] = new_val
            gains[attr] = new_val - old_val
            if game_date:
                self.fighter.last_training_dates[attr] = game_date

        self.fighter.record_training_type(drill.drill_type, intensity_mult)
        self.fatigue = utils.clamp(self.fatigue + (drill.fatigue_rate * intensity_mult), 0.0, 1.0)

        if self.fatigue > 0.8 and random.random() < 0.05:
            injury = self._generate_injury()
            self.fighter.add_injury(injury["type"], injury["severity"], injury["affected_attrs"], injury["recovery_days"], game_date)
            result["injury"] = injury

        result["status"] = "training"
        result["gains"] = gains
        result["fatigue"] = self.fatigue
        result["overtraining_risk"] = self.fatigue > 0.7

        self._advance_week_day()
        return result

    def _advance_week_day(self):
        prev = self.current_week_day
        self.current_week_day = (self.current_week_day + 1) % 7
        if prev == 6 and self.current_week_day == 0:
            self.film_study_sessions = 0

    def _generate_injury(self) -> Dict:
        injuries = [
            {"type": "cut", "severity": 0.3, "affected_attrs": ["striking_accuracy"], "recovery_days": 7},
            {"type": "bruise", "severity": 0.2, "affected_attrs": ["durability"], "recovery_days": 5},
            {"type": "strain", "severity": 0.4, "affected_attrs": ["athleticism"], "recovery_days": 10},
        ]
        return random.choice(injuries)

    def stop_training(self):
        self.current_drill = None
        self.days_trained = 0
        self.in_training = False
        self.fatigue = max(0.0, self.fatigue - 0.3)
        self.weekly_schedule = {}
        self.week_started = False
        self.current_week_day = 0
        self.fight_camp_active = False

    def get_gym_bonus_for_drill(self, drill_name: str) -> float:
        if not self.fighter.gym:
            return 0.0
        gym = self._find_gym(self.fighter.gym)
        if not gym:
            return 0.0
        drill = None
        for d in DRILLS:
            if d.name == drill_name:
                drill = d
                break
        if not drill:
            return 0.0
        if drill.drill_type in gym["specialties"]:
            return gym["coach_bonus"] * 0.75
        return gym["coach_bonus"] * 0.25

    def get_schedule_state(self) -> Dict:
        sched = {}
        for d in range(7):
            name = self.weekly_schedule.get(d)
            sched[DAYS_OF_WEEK[d]] = name if name else "Rest"
        return {
            "schedule": sched,
            "current_day": DAYS_OF_WEEK[self.current_week_day],
            "week_started": self.week_started,
            "overtraining_risk": self.fatigue > 0.7,
        }

    def get_fight_readiness(self) -> Dict:
        readiness = {
            "overall": 0.0,
            "stamina_pct": max(0, 100 - self.fatigue * 100),
            "overtraining": self.fatigue > 0.7,
            "notes": [],
        }
        if readiness["overtraining"]:
            readiness["notes"].append("Overtraining detected — reduced fight performance expected")
            readiness["overall"] = 0.6
        elif self.fatigue > 0.5:
            readiness["notes"].append("Moderate fatigue — some performance reduction")
            readiness["overall"] = 0.8
        else:
            readiness["notes"].append("Fighter is well-rested and ready")
            readiness["overall"] = 1.0
        return readiness
