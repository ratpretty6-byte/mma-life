import random
import math
import numpy as np
from typing import Dict, Optional, List, Generator
from fighter import Fighter
from positions import PositionSystem, Position
from strategy import StrategySystem, STRATEGIES
from commentary import CommentaryEngine
import utils
from utils import get_combos_for_position, calculate_feint_chance, calculate_feint_recognition
from utils import get_breathing_level, get_breathing_recovery_modifier, BREATHING_THRESHOLDS, BREATHING_RECOVERY_BETWEEN_ROUNDS
from utils import get_stance_modifiers

# ============================================================
# CONSTANTS
# ============================================================

ROUND_DURATION = 300  # 5 minutes, MMA standard
TITLE_ROUND_DURATION = 300  # 5 min for title fights (5 rounds)
CHAMPIONSHIP_ROUNDS = 5
REGULAR_ROUNDS = 3

STRIKE_PROFILES = {
    "jab":       {"base_damage": 5,  "speed": 1.4, "stamina_cost": 1,  "range": "pocket",  "targets": ["head", "body", "jaw"]},
    "cross":     {"base_damage": 8,  "speed": 1.0, "stamina_cost": 2,  "range": "pocket",  "targets": ["head", "body", "jaw"]},
    "hook":      {"base_damage": 11, "speed": 0.7, "stamina_cost": 3,  "range": "pocket",  "targets": ["head", "body", "jaw"]},
    "uppercut":  {"base_damage": 9,  "speed": 0.8, "stamina_cost": 3,  "range": "pocket",  "targets": ["head", "body", "jaw"]},
    "kick":      {"base_damage": 13, "speed": 0.5, "stamina_cost": 5,  "range": "distance", "targets": ["head", "body", "legs"]},
    "knee":      {"base_damage": 10, "speed": 0.7, "stamina_cost": 4,  "range": "clinch",   "targets": ["head", "body"]},
    "elbow":     {"base_damage": 11, "speed": 0.9, "stamina_cost": 3,  "range": "clinch",   "targets": ["head", "body", "jaw"]},
    "hammerfist":{"base_damage": 7,  "speed": 0.9, "stamina_cost": 2,  "range": "ground",   "targets": ["head", "body"]},
    "punch":     {"base_damage": 6,  "speed": 1.0, "stamina_cost": 2,  "range": "ground",   "targets": ["head", "body"]},
    "superman_punch": {"base_damage": 10, "speed": 0.6, "stamina_cost": 4, "range": "pocket", "targets": ["head", "body"]},
}

# Import from utils for enhanced combo system
from utils import COMBOS as NEW_COMBOS

STAMINA_COST = {
    "jab": 1, "cross": 2, "hook": 3, "uppercut": 3,
    "kick": 5, "knee": 4, "elbow": 3,
    "hammerfist": 2, "punch": 2, "superman_punch": 4,
    "takedown_attempt": 6, "clinch_attempt": 3,
    "ground_strike": 2, "submission_attempt": 4,
    "stand_up": 5, "sweep": 4, "pass_guard": 3,
    "advance_mount": 3, "take_back": 4,
}

COMBINATIONS = {c["id"]: c for c in utils.COMBOS}
COMBOS_BY_POSITION = {}  # populated lazily


# ============================================================
# MMA REFEREE
# ============================================================

class Referee:
    """MMA referee — no 8-count. Manages cage-side stoppages and standups."""

    def __init__(self, fighter1=None, fighter2=None, style="protective"):
        self.standup_pending = False
        self.target_fighter = None
        self.warning_issued = False
        self.consecutive_damage_count = 0
        self.fighter_ref = fighter1
        self.fighter2_ref = fighter2
        self.f1_unanswered_strikes = 0
        self.f2_unanswered_strikes = 0
        self.last_standup_round = 0
        self.style = style
        # Style modifiers
        if style == "protective":
            self.tko_threshold = 0.85
            self.standup_speed = 1.0
            self.foul_detection = 0.85
        elif style == "let_them_fight":
            self.tko_threshold = 1.15
            self.standup_speed = 0.7
            self.foul_detection = 0.55
        elif style == "strict":
            self.tko_threshold = 1.0
            self.standup_speed = 1.0
            self.foul_detection = 0.95
        # Foul tracking
        self.f1_fouls = []
        self.f2_fouls = []
        self.f1_warnings = 0
        self.f2_warnings = 0
        self.f1_dq = False
        self.f2_dq = False
        self.foul_timeout_active = False
        self.foul_timeout_actions = 0

    def should_stand_up(self, fight, round_num) -> bool:
        """
        MMA referee standup: if one fighter is against the cage taking
        unanswered punishment, ref stands them up.
        """
        # Only in clinch or cage-against situations
        pos = fight.position_system.current_position
        if pos not in (Position.CLINCH,):
            return False

        # Don't stand up too frequently
        if round_num - self.last_standup_round < 2:
            return False

        # If one fighter has been controlling for too long without damage
        ctrl_time = fight.position_system.position_time
        if ctrl_time >= 6:  # 6 actions in clinch without progression
            # Check if bottom fighter is absorbing damage
            bottom = fight.position_system.bottom_fighter
            top = fight.position_system.top_fighter
            if bottom and top:
                # Bottom fighter health significantly worse
                bottom_health = bottom.get_overall_health_pct()
                top_health = top.get_overall_health_pct()
                if bottom_health < top_health - 10:
                    return True
        return False

    def stop_for_standing_tko(self, fighter, state_name: str) -> bool:
        unanswered = self.get_unanswered(fighter)
        threshold = int(5 * self.tko_threshold)
        if unanswered >= threshold:
            defense = utils.calculate_defense_score(
                fighter.attributes.get("durability", 50),
                fighter.attributes.get("composure", 50),
                fighter.attributes.get("fight_iq", 50),
                state_name == "HURT",
                state_name == "STUNNED"
            )
            if defense < 45:
                return True
        return False

    def check_doctor_stoppage(self, fighter, state, fight) -> Optional[str]:
        """
        Doctor intervenes for severe injuries — MMA style.
        """
        # Eye injuries
        for eye in ["left_eye", "right_eye"]:
            eye_health = fighter.get_zone_health_pct(eye)
            if eye_health < 3:
                return f"Doctor stoppage: {fighter.name}'s {eye.replace('_', ' ')} is too damaged"

        # Jaw injuries
        jaw_health = fighter.get_zone_health_pct("jaw")
        if jaw_health < 2:
            return f"Doctor stoppage: {fighter.name}'s jaw is broken"

        if state.get("swelling", 0) > 97:
            return f"Doctor stoppage: Severe swelling on {fighter.name}"

        # Leg damage doctor check — can barely stand
        lead_dmg = state.get("lead_leg_damage", 0)
        rear_dmg = state.get("rear_leg_damage", 0)
        if lead_dmg > 90 and rear_dmg > 90:
            return f"Doctor stoppage: {fighter.name} can barely stand on damaged legs"
        if (lead_dmg + rear_dmg) / 2 > 85 and random.random() < 0.15:
            return f"Doctor stoppage: {fighter.name}'s legs are too damaged to continue"

        return None

    def check_foul(self, attacker, defender, fighter_num) -> Optional[str]:
        """
        Full foul system: determines if a foul occurs and returns the foul type or None.
        Foul rate based on fighter discipline, aggression, mental toughness, and dirty trait.
        """
        discipline = attacker.get_effective_attribute("discipline", 0)
        aggression = attacker.get_effective_attribute("aggression", 0)
        mental_toughness = attacker.get_effective_attribute("mental_toughness", 0)

        # Base foul chance per action
        base_chance = 0.008  # 0.8%

        # Aggressive fighters commit more fouls
        if aggression > 70:
            base_chance += 0.005
        if aggression > 85:
            base_chance += 0.008

        # Disciplined fighters commit fewer fouls
        if discipline < 40:
            base_chance += 0.010
        if discipline < 25:
            base_chance += 0.015

        # Low mental toughness => more desperation fouls
        if mental_toughness < 35:
            base_chance += 0.005

        # Dirty fighter trait
        if getattr(attacker, 'trait_id', None) == 'dirty_fighter':
            base_chance += 0.020

        if random.random() >= base_chance:
            return None

        # Determine foul type based on position
        from positions import Position
        pos = self.f1_fouls if fighter_num == 1 else self.f2_fouls  # just to access position_ref
        # Choose foul type
        fouls = []
        if random.random() < 0.25:
            fouls.append("eye poke")
        elif random.random() < 0.35:
            fouls.append("low blow")
        elif random.random() < 0.50:
            fouls.append("fence grab")
        elif random.random() < 0.60:
            fouls.append("12-6 elbow")
        elif random.random() < 0.75:
            fouls.append("glove grab")
        else:
            fouls.append("back of the head")

        foul_type = random.choice(fouls) if fouls else "eye poke"

        # Detection chance
        detect_chance = self.foul_detection
        visible_fouls = ["eye poke", "low blow", "12-6 elbow"]
        subtle_fouls = ["fence grab", "glove grab"]
        if foul_type in visible_fouls:
            detect_chance += 0.15
        if foul_type in subtle_fouls:
            detect_chance -= 0.20

        if random.random() >= detect_chance:
            return None  # Foul not detected

        return foul_type

    def record_foul(self, fighter_num: int, foul_type: str) -> str:
        """Record a detected foul and return the consequence."""
        fouls = self.f1_fouls if fighter_num == 1 else self.f2_fouls
        warnings = self.f1_warnings if fighter_num == 1 else self.f2_warnings
        dq = self.f1_dq if fighter_num == 1 else self.f2_dq

        fouls.append(foul_type)

        # Count fouls for this fighter
        total_fouls = len(fouls)
        undetected = max(0, total_fouls - warnings - (1 if self.f1_dq or self.f2_dq else 0))

        if undetected == 1:
            return f"verbal"
        elif undetected == 2:
            self.f1_warnings += 1 if fighter_num == 1 else 0
            self.f2_warnings += 1 if fighter_num == 2 else 0
            return f"official warning"
        elif undetected == 3:
            self.f1_warnings += 1 if fighter_num == 1 else 0
            self.f2_warnings += 1 if fighter_num == 2 else 0
            return f"point deduction"
        else:
            if fighter_num == 1:
                self.f1_dq = True
            else:
                self.f2_dq = True
            return f"disqualification"

    def is_dq(self, fighter_num: int) -> bool:
        if fighter_num == 1:
            return self.f1_dq
        return self.f2_dq

    def reset_consecutive_damage(self):
        self.consecutive_damage_count = 0
        self.f1_unanswered_strikes = 0
        self.f2_unanswered_strikes = 0

    def record_damage_taken(self, fighter, is_on_feet, attacker=None):
        if not is_on_feet:
            self.f1_unanswered_strikes = 0
            self.f2_unanswered_strikes = 0
            return

        # Track unanswered strikes per fighter
        if fighter == self.fighter_ref:
            other_unanswered = self.f2_unanswered_strikes
        else:
            other_unanswered = self.f1_unanswered_strikes

        # When a fighter lands, reset the attacker's unanswered count
        # and increment the defender's
        if attacker:
            if attacker == self.fighter_ref:
                self.f1_unanswered_strikes = 0
                self.f2_unanswered_strikes += 1
            else:
                self.f2_unanswered_strikes = 0
                self.f1_unanswered_strikes += 1

        # Global count = max of both fighters' unanswered
        self.consecutive_damage_count = max(self.f1_unanswered_strikes, self.f2_unanswered_strikes)

    def get_unanswered(self, fighter) -> int:
        if fighter == self.fighter_ref:
            return self.f1_unanswered_strikes
        return self.f2_unanswered_strikes


# ============================================================
# FIGHTER STATE MACHINE
# ============================================================

class FighterState:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.state = "NORMAL"
        self.hurt_timer = 0
        self.stunned_timer = 0
        self.rocked_timer = 0
        self.recovery_rate = 0.3  # per action

    def transition(self, head_health_pct: float, is_struck: bool, strike_severity: str):
        prev = self.state

        if self.state == "NORMAL":
            if head_health_pct < 55:
                self.state = "HURT"
                self.hurt_timer = 0
            elif is_struck and strike_severity in ("Flush", "Devastating"):
                self.state = "ROCKED"
                self.rocked_timer = 2

        elif self.state == "HURT":
            self.hurt_timer += 1
            if head_health_pct < 30:
                self.state = "STUNNED"
                self.stunned_timer = 3
            elif self.hurt_timer > 4 and head_health_pct > 55:
                self.state = "NORMAL"
            elif is_struck and strike_severity == "Devastating":
                self.state = "STUNNED"
                self.stunned_timer = 3

        elif self.state == "ROCKED":
            self.rocked_timer -= 1
            if self.rocked_timer <= 0:
                if head_health_pct < 30:
                    self.state = "STUNNED"
                    self.stunned_timer = 3
                else:
                    self.state = "HURT"
            elif is_struck and strike_severity in ("Solid", "Flush", "Devastating"):
                self.state = "STUNNED"
                self.stunned_timer = 3

        elif self.state == "STUNNED":
            self.stunned_timer -= 2
            if self.stunned_timer <= 0:
                if head_health_pct < 12:
                    self.state = "DOWN"
                elif head_health_pct < 40:
                    self.state = "ROCKED"
                    self.rocked_timer = 2
                else:
                    self.state = "HURT"
            elif is_struck:
                self.stunned_timer += 1

    def get_state(self) -> str:
        return self.state

    def get_stat_modifier(self) -> dict:
        """Stat modifiers based on current state."""
        if self.state == "NORMAL":
            return {"accuracy": 1.0, "power": 1.0, "movement": 1.0, "defense": 1.0}
        elif self.state == "HURT":
            return {"accuracy": 0.90, "power": 0.95, "movement": 0.95, "defense": 0.85}
        elif self.state == "ROCKED":
            return {"accuracy": 0.70, "power": 0.85, "movement": 0.80, "defense": 0.65}
        elif self.state == "STUNNED":
            return {"accuracy": 0.50, "power": 0.70, "movement": 0.55, "defense": 0.40}
        elif self.state == "DOWN":
            return {"accuracy": 0.0, "power": 0.0, "movement": 0.0, "defense": 0.0}
        return {"accuracy": 1.0, "power": 1.0, "movement": 1.0, "defense": 1.0}


# ============================================================
# FIGHT CLASS
# ============================================================

class JudgeProfile:
    def __init__(self, name: str, aggression_weight: float = 0.15, grappling_weight: float = 0.35,
                 damage_weight: float = 0.40, generalship_weight: float = 0.10,
                 bias_noise: float = 0.0, bias: float = 0.0):
        self.name = name
        self.weights = {
            "striking": 1.0,
            "grappling": 1.0,
            "aggression": 1.0,
            "octagon_control": 1.0,
        }
        self.aggression_weight = aggression_weight
        self.grappling_weight = grappling_weight
        self.damage_weight = damage_weight
        self.generalship_weight = generalship_weight
        self.bias_noise = bias_noise
        self.bias = bias


class Judge:
    def __init__(self, name: str, profile: JudgeProfile = None, bias: float = 0.0):
        self.name = name
        self.profile = profile or JudgeProfile(name, bias=bias)
        self.scores: List[List[int]] = []
        self.round_details: List[dict] = []

    def score_round(self, rd: dict) -> tuple:
        pw = self.profile.weights
        kd_diff = rd["knockdowns_f1"] - rd["knockdowns_f2"]

        # Each criterion weighted by judge preference
        strike_diff = rd["effective_striking_f1"] - rd["effective_striking_f2"]
        strike_score = self.normalize(strike_diff) * self.profile.damage_weight * pw["striking"]

        grapple_diff = rd["effective_grappling_f1"] - rd["effective_grappling_f2"]
        grapple_score = self.normalize(grapple_diff) * self.profile.grappling_weight * pw["grappling"]

        agg_diff = rd["aggression_f1"] - rd["aggression_f2"]
        agg_score = self.normalize(agg_diff) * self.profile.aggression_weight * pw["aggression"]

        cage_diff = rd["octagon_control_f1"] - rd["octagon_control_f2"]
        cage_score = self.normalize(cage_diff) * self.profile.generalship_weight * pw["octagon_control"]

        # Per-judge noise
        noise = random.gauss(0, self.profile.bias_noise)

        f1_raw = strike_score + grapple_score + agg_score + cage_score + noise
        f2_raw = -(strike_score + grapple_score + agg_score + cage_score) - noise

        if kd_diff != 0:
            kd_bonus = 1.0 + max(0, kd_diff - 1) * 1.0
            f1_raw += kd_bonus
            f2_raw -= kd_bonus

        f1_round, f2_round = 10, 10
        diff = f1_raw - f2_raw

        if abs(diff) < 0.15:
            f1_round, f2_round = 10, 10
        elif diff > 0:
            f1_round = 10
            f2_round = max(7, 10 - self._score_diff_to_points(diff))
        else:
            f2_round = 10
            f1_round = max(7, 10 - self._score_diff_to_points(abs(diff)))

        # 10-8 gate: rarely score 10-8 unless multiple knockdowns or massive domination
        if (10 - min(f1_round, f2_round)) >= 2:
            sig_f1 = rd.get("f1_sig_strikes", 0)
            sig_f2 = rd.get("f2_sig_strikes", 0)
            total_sig = max(sig_f1, sig_f2, 1)
            min_ratio = min(sig_f1, sig_f2) / total_sig
            if abs(kd_diff) < 2 and min_ratio > 0.25:
                loser_score = max(f1_round, f2_round)
                if loser_score == 8:
                    f1_round = 10 if f1_round > f2_round else 9
                    f2_round = 9 if f1_round > f2_round else 10

        self.scores.append([f1_round, f2_round])
        self.round_details.append(rd)
        return (f1_round, f2_round)

    @staticmethod
    def normalize(value: float) -> float:
        return utils.clamp(value * 0.01, -1.0, 1.0)

    @staticmethod
    def _score_diff_to_points(diff: float) -> int:
        if diff < 0.5:
            return 1
        elif diff < 2.5:
            return 2
        elif diff < 4.5:
            return 3
        else:
            return 4


class Fight:
    def __init__(self, fighter1: Fighter, fighter2: Fighter, rounds: int = 3, is_title_fight: bool = False, context: Optional[Dict] = None):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.rounds = rounds
        self.is_title_fight = is_title_fight
        self.context = context or {}

        self.position_system = PositionSystem(fighter1, fighter2)
        self.commentary = CommentaryEngine()
        self.strategy1 = StrategySystem(fighter1)
        self.strategy2 = StrategySystem(fighter2)
        self.strategy1.set_opponent_strategy(self.strategy2.current_strategy)
        self.strategy2.set_opponent_strategy(self.strategy1.current_strategy)

        # Initialize 9-zone health models
        fighter1.init_fight_health()
        fighter2.init_fight_health()

        # Per-fighter state tracking
        self.f1_state = self._init_fighter_state()
        self.f2_state = self._init_fighter_state()
        self.f1_state["fighter_obj"] = fighter1
        self.f2_state["fighter_obj"] = fighter2

        # Fighter state machine wrappers
        self.f1_machine = FighterState(fighter1)
        self.f2_machine = FighterState(fighter2)

        # Referee with personality
        ref_styles = ["protective", "let_them_fight", "strict"]
        ref_style = random.choice(ref_styles)
        self.referee = Referee(fighter1, fighter2, style=ref_style)
        self.referee_style = ref_style

        # Stance system
        self.fighter1_stance = getattr(fighter1, 'stance', 'orthodox')
        self.fighter2_stance = getattr(fighter2, 'stance', 'orthodox')

        # Judges with profiles
        judge_profiles = [
            JudgeProfile("Judge A", aggression_weight=0.15, grappling_weight=0.35,
                         damage_weight=0.40, generalship_weight=0.10, bias_noise=0.5, bias=0.3),
            JudgeProfile("Judge B", aggression_weight=0.12, grappling_weight=0.40,
                         damage_weight=0.38, generalship_weight=0.10, bias_noise=0.8, bias=0.0),
            JudgeProfile("Judge C", aggression_weight=0.20, grappling_weight=0.30,
                         damage_weight=0.42, generalship_weight=0.08, bias_noise=0.6, bias=-0.3),
        ]
        self.judges = [Judge(p.name, p) for p in judge_profiles]

        # Momentum tracker (-50 to +50 per fighter)
        self.f1_momentum = 0
        self.f2_momentum = 0

        # Crowd excitement (0-100)
        self.crowd_excitement = 40
        if context and context.get("rivalry_info"):
            self.crowd_excitement = 70
        if is_title_fight:
            self.crowd_excitement = 85

        # KO tracking
        self.f1_head_damage = 0.0  # Accumulated head damage for KO threshold
        self.f2_head_damage = 0.0
        self.f1_knockdowns_this_round = 0
        self.f2_knockdowns_this_round = 0

        # Corner advice for next round
        self.corner_advice_mods = {}

        # Action tracking
        self.current_round = 1
        self.action_count = 0
        self.round_start_time = 0
        self.time_elapsed = 0  # In seconds, across all rounds
        self.round_time_elapsed = 0  # Time in current round

        self.fight_log = []
        self.winner = None
        self.loser = None
        self.win_method = None
        self.win_round = None

        self.f1_round_scores = []
        self.f2_round_scores = []
        self.f1_control_time = 0
        self.f2_control_time = 0
        self.f1_actions_landed = 0
        self.f2_actions_landed = 0

        self._web_gen = None
        self.f1_round_snap_sig = 0
        self.f2_round_snap_sig = 0
        self.f1_round_snap_td = 0
        self.f2_round_snap_td = 0
        self.f1_round_snap_td_att = 0
        self.f2_round_snap_td_att = 0
        self.f1_round_snap_grapple = 0.0
        self.f2_round_snap_grapple = 0.0
        self.f1_round_snap_sub = 0
        self.f2_round_snap_sub = 0
        self.f1_round_snap_dmg = 0
        self.f2_round_snap_dmg = 0
        self.f1_round_attempts = 0
        self.f2_round_attempts = 0
        self.f1_start_attempts = 0
        self.f2_start_attempts = 0
        self._last_severity = "Clean"
        self._last_landed = True
        self._last_subtype = "strike"

    def _init_fighter_state(self) -> Dict:
        return {
            "health": {"head": 100, "body": 100, "legs": 100},
            "stamina": 100,
            "cuts": [],
            "swelling": 0,
            "leg_damage": 0,
            "lead_leg_damage": 0,
            "rear_leg_damage": 0,
            "liver_damage": 0,
            "rib_damage": 0,
            "rib_injury_active": False,
            "knockdown": False,
            "knockdown_count": 0,
            "recovering": False,
            "accumulated_damage": 0,
            "rounds_stamina_burn": [],
            "rounds_damage_dealt": [],
            "fatigue_level": 0.0,
            "state": "NORMAL",
            "hurt": False,
            "stunned": False,
            "stunned_timer": 0,
            "rocked": False,
            "combo_count": 0,
            "submission_threat": {},
            "body_fatigue": 0,
            "vision_impairment": 0,
            "significant_strikes_landed": 0,
            "strikes_thrown": 0,
            "takedowns_landed": 0,
            "takedowns_attempted": 0,
            "guard_passes": 0,
            "submissions_attempted": 0,
            "unanswered_ground_strikes": 0,
            "forward_pressure_points": 0,
            "effective_grappling_points": 0.0,
            "damage_taken_log": [],
            "breathing_capacity": 100,
            "feint_count": 0,
            "feinted_last_action": False,
            "opponent_action_history": [],
            "ko_stage": 0,
            "cardio_zone": "aerobic",
            "consecutive_retreats": 0,
            "pattern_read": False,
            "pattern_read_bonus": 1.0,
            "second_wind_used": False,
            "involuntary_rest_timer": 0,
            "stunned_since_action": 0,
        }

    # ============================================================
    # ADRENALINE SYSTEM
    # ============================================================

    def get_adrenaline(self, fighter_num: int) -> float:
        """
        Adrenaline multiplier: boosts power and aggression when hurt or losing.
        """
        base = 1.0
        f_state = self.f1_state if fighter_num == 1 else self.f2_state
        f_obj = self.fighter1 if fighter_num == 1 else self.fighter2

        # Being hurt increases adrenaline
        if f_state["hurt"]:
            base += 0.2
        if f_state.get("state") == "HURT":
            base += 0.15
        elif f_state.get("state") == "ROCKED":
            base += 0.3
        elif f_state.get("state") == "STUNNED":
            base += 0.4

        # Losing on cards increases adrenaline
        score_deficit = self._get_score_deficit(fighter_num)
        if score_deficit > 15:
            base += 0.4
        elif score_deficit > 5:
            base += 0.2

        return min(base, 2.0)

    def _get_score_deficit(self, fighter_num: int) -> int:
        """How much a fighter is losing by on the scorecards (cumulative across all rounds)."""
        if not self.judges[0].scores:
            return 0
        total1 = sum(sum(s[0] for s in j.scores) for j in self.judges)
        total2 = sum(sum(s[1] for s in j.scores) for j in self.judges)
        if fighter_num == 1:
            return max(0, total2 - total1)
        return max(0, total1 - total2)

    # ============================================================
    # MOMENTUM SYSTEM
    # ============================================================

    def _update_momentum(self, for_fighter: int, delta: int):
        if for_fighter == 1:
            self.f1_momentum = utils.clamp(self.f1_momentum + delta, -50, 50)
        else:
            self.f2_momentum = utils.clamp(self.f2_momentum + delta, -50, 50)

    def get_momentum_modifier(self, fighter_num: int) -> float:
        m = self.f1_momentum if fighter_num == 1 else self.f2_momentum
        if m > 20:
            return 1.05
        elif m < -20:
            return 0.95
        return 1.0

    # ============================================================
    # CROWD EXCITEMENT SYSTEM
    # ============================================================

    def _update_crowd_excitement(self, delta: int):
        self.crowd_excitement = utils.clamp(self.crowd_excitement + delta, 0, 100)

    def get_crowd_modifier(self, fighter_num: int) -> float:
        if self.crowd_excitement < 40:
            return 0.98
        elif self.crowd_excitement > 70:
            return 1.02
        return 1.0

    # ============================================================
    # BLOOD SYSTEM
    # ============================================================

    def _add_blood(self, fighter: Fighter, damage: float):
        """Tracking blood — high damage to face causes bleeding that affects vision."""
        severity = damage / 50.0
        fighter._blood_level = min(100, fighter._blood_level + severity)

        if fighter._blood_level > 30 and random.random() < 0.3:
            self.fight_log.append(f"Blood is streaming from {fighter.name}'s face!")

    def _get_blood_penalty(self, fighter: Fighter) -> float:
        """Blood in eyes reduces accuracy."""
        if fighter._blood_level > 40:
            return max(0.7, 1.0 - (fighter._blood_level - 40) / 200)
        return 1.0

    # ============================================================
    # KO ACCUMULATION
    # ============================================================

    def _track_head_damage(self, fighter: Fighter, damage: float):
        divisor = 2.0
        if fighter == self.fighter1:
            self.f1_head_damage += damage / divisor
            self.f1_state["damage_taken_log"].append({"type": "head", "damage": damage, "round": self.current_round})
            self._update_ko_stage(self.fighter1, self.f1_state, self.f1_head_damage)
        else:
            self.f2_head_damage += damage / divisor
            self.f2_state["damage_taken_log"].append({"type": "head", "damage": damage, "round": self.current_round})
            self._update_ko_stage(self.fighter2, self.f2_state, self.f2_head_damage)

    def _update_ko_stage(self, fighter: Fighter, state: dict, head_damage: float):
        """Progressive KO staging system. Updates visible stage without ending fight."""
        if self.current_round < 2:
            return
        chin_resistance = fighter.get_chin_resistance()
        pct = head_damage / max(1, chin_resistance)

        new_stage = 0
        if pct >= 1.0:
            new_stage = 4  # Finish
        elif pct >= 0.80:
            new_stage = 3  # On the verge
        elif pct >= 0.60:
            new_stage = 2  # Wobbled
        elif pct >= 0.40:
            new_stage = 1  # Dazed

        old_stage = state.get("ko_stage", 0)
        state["ko_stage"] = new_stage

        # Stage-specific effects
        if new_stage == 1 and old_stage < 1:
            self.fight_log.append(f"{fighter.name} looks glassy-eyed!")
        elif new_stage == 2 and old_stage < 2:
            self.fight_log.append(f"{fighter.name} is wobbled, legs looking unsteady!")
        elif new_stage == 3 and old_stage < 3:
            self.fight_log.append(f"{fighter.name} is on the verge of being finished!")
        elif new_stage == 4:
            pass  # Handled by _check_ko_or_tko

    def _check_ko_or_tko(self, fighter: Fighter, damage: float, zone_mult: float) -> bool:
        """Check if current damage warrants a KO/TKO. Returns True if fight is over."""
        if self.current_round < 2 and random.random() < 0.90:
            return False
        is_f1 = fighter == self.fighter1
        head_damage = self.f1_head_damage if is_f1 else self.f2_head_damage
        state = self.f1_state if is_f1 else self.f2_state
        chin_resistance = fighter.get_chin_resistance()
        opponent = self.fighter2 if is_f1 else self.fighter1

        pct = head_damage / max(1, chin_resistance)

        # Immediate KO: Devastating + zone_mult > 2.0 (single devastating blow)
        if pct >= 1.0 and damage * zone_mult > 0.4 * chin_resistance:
            self.winner = opponent
            self.loser = fighter
            self.win_method = "KO"
            self.win_round = self.current_round
            return True

        # KO from accumulation: pct >= 1.0 but gradual
        if pct >= 1.0:
            # Check if recent damage is burst vs accumulated
            recent = sum(
                d["damage"] for d in state["damage_taken_log"]
                if self.current_round - d["round"] <= 1 and d.get("round", self.current_round) == self.current_round
            )
            if recent > chin_resistance * 0.5:
                self.win_method = "KO"
            else:
                self.win_method = "TKO (Strikes)"
            self.winner = opponent
            self.loser = fighter
            self.win_round = self.current_round
            return True

        if pct >= 0.80 and self._last_severity in ("Flush", "Devastating"):
            if random.random() < 0.25:
                self.winner = opponent
                self.loser = fighter
                self.win_method = "TKO (Strikes)"
                self.win_round = self.current_round
                return True

        return False

    def _track_ko_accumulation(self, fighter: Fighter, damage: float, zone_mult: float):
        if self.current_round < 2 and random.random() < 0.90:
            return
        if self._check_ko_or_tko(fighter, damage, zone_mult):
            loser = self.loser
            if loser == self.fighter1:
                log_text = f"\n*** {self.fighter2.name} stops {self.fighter1.name}! {self.win_method} in round {self.current_round}! ***"
            else:
                log_text = f"\n*** {self.fighter1.name} stops {self.fighter2.name}! {self.win_method} in round {self.current_round}! ***"
            self.fight_log.append(log_text)

    # ============================================================
    # MAIN SIMULATION GENERATOR
    # ============================================================

    def simulate_fight_gen(self, speed: float = 1.0) -> Generator:
        buildup_parts = self.commentary.generate_pre_fight_buildup(self.fighter1, self.fighter2, self.context)
        for part in buildup_parts:
            yield {"type": "pre_fight", "text": part}

        yield {"type": "walkout", "text": self.commentary.generate_walkout(self.fighter1, self.is_title_fight)}
        yield {"type": "walkout", "text": self.commentary.generate_walkout(self.fighter2, False)}

        for round_num in range(1, self.rounds + 1):
            self.current_round = round_num
            self.round_time_elapsed = 0
            self.f1_knockdowns_this_round = 0
            self.f2_knockdowns_this_round = 0
            self.f1_control_time = 0
            self.f2_control_time = 0
            self.f1_actions_landed = 0
            self.f2_actions_landed = 0
            self.action_count = 0
            self.referee.reset_consecutive_damage()
            self.position_system.current_position = Position.DISTANCE
            self.position_system.top_fighter = None
            self.position_system.bottom_fighter = None
            self.position_system.clinch_initiator = None
            self.position_system.position_time = 0
            self.position_system.cage_position = None
            self.f1_round_snap_sig = self.f1_state.get("significant_strikes_landed", 0)
            self.f2_round_snap_sig = self.f2_state.get("significant_strikes_landed", 0)
            self.f1_round_snap_td = self.f1_state.get("takedowns_landed", 0)
            self.f2_round_snap_td = self.f2_state.get("takedowns_landed", 0)
            self.f1_round_snap_td_att = self.f1_state.get("takedowns_attempted", 0)
            self.f2_round_snap_td_att = self.f2_state.get("takedowns_attempted", 0)
            self.f1_round_snap_grapple = self.f1_state.get("effective_grappling_points", 0.0)
            self.f2_round_snap_grapple = self.f2_state.get("effective_grappling_points", 0.0)
            self.f1_round_snap_sub = self.f1_state.get("submissions_attempted", 0)
            self.f2_round_snap_sub = self.f2_state.get("submissions_attempted", 0)
            self.f1_round_snap_dmg = len(self.f1_state.get("rounds_damage_dealt", []))
            self.f2_round_snap_dmg = len(self.f2_state.get("rounds_damage_dealt", []))
            self.f1_start_attempts = self.f1_round_attempts
            self.f2_start_attempts = self.f2_round_attempts

            # Determine number of actions this round (~based on pace)
            total_actions = self._determine_actions_this_round(round_num)

            # Carryover context from previous round damage
            if round_num > 1:
                for f_obj, f_state in [(self.fighter1, self.f1_state), (self.fighter2, self.f2_state)]:
                    if f_state.get("stunned", False):
                        yield {"type": "between_round", "text": f"{f_obj.name} is still recovering from that punishment in Round {round_num - 1}!"}

            yield {"type": "round_start", "round": round_num,
                   "text": self.commentary.generate_round_start(round_num, self.fighter1, self.fighter2)}

            for action_idx in range(total_actions):
                if self.winner:
                    break

                self.action_count += 1
                self.round_time_elapsed += random.randint(6, 15)  # Each action takes 6-15 seconds
                self.time_elapsed += random.randint(6, 15)

                # Check for end-of-round based on time
                if self.round_time_elapsed >= ROUND_DURATION:
                    break

                phase_progress = action_idx / max(1, total_actions)
                phase = self._get_round_phase(action_idx, total_actions)

                # Check referee standup (MMA-specific)
                if self.referee.should_stand_up(self, round_num):
                    standup_text = "The referee stands them up!"
                    yield {"type": "action", "text": standup_text, "round": round_num, "time": self._get_time_str()}
                    self.position_system.current_position = Position.DISTANCE
                    self.position_system.position_time = 0
                    self.referee.last_standup_round = round_num
                    continue

                if action_idx % 4 == 0 and not self.winner and random.random() < 0.6:
                    pace_text = self.commentary.generate_pacing_commentary(self.fighter1, self.fighter2, phase)
                    if pace_text:
                        self.fight_log.append(pace_text)

                # Periodic leg damage commentary (every 10 actions)
                if action_idx % 10 == 0 and not self.winner:
                    self._apply_leg_damage_effects(self.f1_state, 1)
                    self._apply_leg_damage_effects(self.f2_state, 2)

                # Ring generalship check (every 6 actions)
                if action_idx % 6 == 0 and not self.winner:
                    self._check_ring_generalship()

                # Pattern recognition check (every 8 actions)
                if action_idx % 8 == 0 and not self.winner:
                    self._check_pattern_recognition()

                # Rib injury effect: reduced striking power
                if self.f1_state.get("rib_injury_active") and action_idx % 3 == 0:
                    if random.random() < 0.3:
                        self.fight_log.append(f"{self.fighter1.name} is hampered by rib damage!")
                if self.f2_state.get("rib_injury_active") and action_idx % 3 == 0:
                    if random.random() < 0.3:
                        self.fight_log.append(f"{self.fighter2.name} is hampered by rib damage!")

                self._simulate_action(phase=phase)

                if not self.winner and round_num >= 3 and action_idx > 0 and action_idx % 20 == 0 and random.random() < 0.12:
                    for fighter, state in [(self.fighter1, self.f1_state), (self.fighter2, self.f2_state)]:
                        stop_reason = self.referee.check_doctor_stoppage(fighter, state, self)
                        if stop_reason:
                            self.winner = self.fighter2 if fighter == self.fighter1 else self.fighter1
                            self.loser = fighter
                            self.win_method = "TKO (Doctor Stoppage)"
                            self.win_round = self.current_round
                            yield {"type": "action", "text": stop_reason, "round": round_num,
                                   "time": self._get_time_str(),
                                   "f1_health": self._get_display_health(self.fighter1),
                                   "f2_health": self._get_display_health(self.fighter2)}
                            yield {"type": "knockout",
                                   "text": f"Doctor stoppage! {self.winner.name} wins by {self.win_method}!",
                                   "winner": self.winner.name, "method": self.win_method, "round": self.current_round,
                                   "time": self._get_time_str()}
                            d = self._get_fight_details()
                            yield {"type": "complete", "winner": self.winner.name,
                                   "method": self.win_method, "round": self.win_round,
                                   "f1_health": self._get_display_health(self.fighter1),
                                   "f2_health": self._get_display_health(self.fighter2),
                                   "total_scores": self._get_total_scores(),
                                   "f1_details": d["f1"], "f2_details": d["f2"]}
                            return

                # Yield action result with time stamp
                if self.fight_log:
                    last = self.fight_log[-1]
                    # Determine crowd reaction and sound cue based on event
                    reaction = None
                    sound = None
                    sev_lower = (self._last_severity or "").lower()
                    if "devastating" in sev_lower or "critical" in sev_lower:
                        reaction = "eruption"
                    elif "flush" in sev_lower:
                        reaction = "cheer"
                    elif "solid" in sev_lower:
                        reaction = "gasp"
                    if "CRITICAL" in (self._last_severity or "") or "Devastating" in (self._last_severity or ""):
                        sound = "impact"
                    if self.crowd_excitement > 80:
                        reaction = reaction or "cheer"
                    elif self.crowd_excitement < 25:
                        reaction = reaction or "silence"

                    event = {"type": "action", "text": last, "round": round_num,
                             "f1_health": self._get_display_health(self.fighter1),
                             "f2_health": self._get_display_health(self.fighter2),
                             "f1_state": self.f1_machine.get_state(),
                             "f2_state": self.f2_machine.get_state(),
                             "f1_total_score": self._get_total_score_for(1),
                             "f2_total_score": self._get_total_score_for(2),
                             "time": self._get_time_str(),
                             "severity": self._last_severity,
                             "landed": self._last_landed,
                             "subtype": self._last_subtype,
                             "f1_momentum": self.f1_momentum,
                             "f2_momentum": self.f2_momentum,
                             "crowd_excitement": self.crowd_excitement,
                             "crowd_reaction": reaction,
                             "sound_cue": sound}
                    yield event

                # Mid-round AI adaptation (every 6 actions)
                if action_idx % 6 == 5 and round_num > 1 and not self.winner:
                    self._check_ai_mid_round()

            if self.winner:
                # Knockout/Submission finish
                if self.win_method == "KO":
                    yield {"type": "knockout", "text": self.commentary.generate_knockout_commentary(self.loser),
                           "winner": self.winner.name, "method": self.win_method, "round": self.current_round,
                           "time": self._get_time_str(),
                           "f1_health": self._get_display_health(self.fighter1),
                           "f2_health": self._get_display_health(self.fighter2),
                           "f1_state": self.f1_machine.get_state(),
                           "f2_state": self.f2_machine.get_state(),
                           "f1_total_score": self._get_total_score_for(1),
                           "f2_total_score": self._get_total_score_for(2),
                           "total_scores": self._get_total_scores(),
                           "crowd_reaction": "eruption",
                           "sound_cue": "ko_bell"}
                elif "TKO" in self.win_method:
                    yield {"type": "knockout", "text": self.commentary.generate_tko_commentary(self.winner, self.loser, self.win_method),
                           "winner": self.winner.name, "method": self.win_method, "round": self.current_round,
                           "time": self._get_time_str(),
                           "f1_health": self._get_display_health(self.fighter1),
                           "f2_health": self._get_display_health(self.fighter2),
                           "f1_state": self.f1_machine.get_state(),
                           "f2_state": self.f2_machine.get_state(),
                           "f1_total_score": self._get_total_score_for(1),
                           "f2_total_score": self._get_total_score_for(2),
                           "total_scores": self._get_total_scores()}
                elif "Submission" in self.win_method:
                    sub_name = self.win_method.replace("Submission (", "").replace(")", "")
                    sub_text = f"{self.winner.name} sinks in the {sub_name}!"
                    yield {"type": "submission", "text": sub_text,
                           "winner": self.winner.name, "method": self.win_method, "round": self.current_round,
                           "time": self._get_time_str(),
                           "f1_health": self._get_display_health(self.fighter1),
                           "f2_health": self._get_display_health(self.fighter2),
                           "f1_state": self.f1_machine.get_state(),
                           "f2_state": self.f2_machine.get_state(),
                           "f1_total_score": self._get_total_score_for(1),
                           "f2_total_score": self._get_total_score_for(2),
                           "total_scores": self._get_total_scores(),
                           "crowd_reaction": "cheer",
                           "sound_cue": "bell"}
                yield {"type": "post_fight",
                       "text": self.commentary.generate_post_fight(self.winner, self.win_method, self.current_round, False, self.loser)}
                if self.winner and self.loser:
                    win_reaction = self.commentary.generate_post_fight_reaction(self.winner, self.loser)
                    if win_reaction:
                        yield {"type": "post_fight_reaction", "text": win_reaction}
                    loss_reaction = self.commentary.generate_post_fight_loss(self.loser, self.winner)
                    if loss_reaction:
                        yield {"type": "post_fight_reaction", "text": loss_reaction}
                details = self._get_fight_details()
                yield {"type": "complete", "winner": self.winner.name if self.winner else "Draw",
                       "method": self.win_method, "round": self.win_round,
                       "f1_health": self._get_display_health(self.fighter1),
                       "f2_health": self._get_display_health(self.fighter2),
                       "total_scores": self._get_total_scores(),
                       "f1_details": details["f1"],
                       "f2_details": details["f2"]}
                return

            if round_num >= 2:
                for fighter, machine, opponent in [
                    (self.fighter1, self.f1_machine, self.fighter2),
                    (self.fighter2, self.f2_machine, self.fighter1)
                ]:
                    if self.referee.stop_for_standing_tko(fighter, machine.get_state()):
                        self.winner = opponent
                        self.loser = fighter
                        self.win_method = "TKO (Referee Stoppage)"
                        self.win_round = self.current_round
                        yield {"type": "action", "text": "The referee jumps in and stops the fight!", "round": round_num, "time": self._get_time_str()}
                        yield {"type": "knockout",
                               "text": f"TKO (Referee Stoppage)! {self.winner.name} wins!",
                               "winner": self.winner.name, "method": self.win_method, "round": self.current_round,
                               "time": self._get_time_str(),
                               "f1_health": self._get_display_health(self.fighter1),
                               "f2_health": self._get_display_health(self.fighter2),
                               "f1_state": self.f1_machine.get_state(),
                               "f2_state": self.f2_machine.get_state(),
                               "f1_total_score": self._get_total_score_for(1),
                               "f2_total_score": self._get_total_score_for(2),
                               "total_scores": self._get_total_scores()}
                        d = self._get_fight_details()
                        yield {"type": "complete", "winner": self.winner.name,
                               "method": self.win_method, "round": self.win_round,
                               "f1_health": self._get_display_health(self.fighter1),
                               "f2_health": self._get_display_health(self.fighter2),
                               "total_scores": self._get_total_scores(),
                               "f1_details": d["f1"], "f2_details": d["f2"]}
                        return

            # Round ending
            round_desc = self._describe_round(round_num)
            round_summary = self.commentary.generate_round_summary(self.fighter1, self.fighter2)
            yield {"type": "round_end", "round": round_num,
                   "text": self.commentary.generate_round_end(round_num, self.fighter1, self.fighter2, round_desc),
                   "f1_health": self._get_display_health(self.fighter1),
                   "f2_health": self._get_display_health(self.fighter2)}
            if round_summary:
                yield {"type": "round_summary", "text": round_summary, "round": round_num}

            self._score_round(round_num)
            self._round_end_effects(round_num)

            # Emit score update after scoring
            f1_avg = sum(j.scores[-1][0] for j in self.judges) / 3.0
            f2_avg = sum(j.scores[-1][1] for j in self.judges) / 3.0
            yield {"type": "score_update", "round": round_num,
                   "score": f"{int(f1_avg)}-{int(f2_avg)}",
                   "f1_total_score": self._get_total_score_for(1),
                   "f2_total_score": self._get_total_score_for(2),
                   "scores": [[j.scores[r][0] for j in self.judges] for r in range(len(self.judges[0].scores))]}

            if round_num < self.rounds and not self.winner:
                f1_sig = self.f1_state.get("significant_strikes_landed", 0) - self.f1_round_snap_sig
                f2_sig = self.f2_state.get("significant_strikes_landed", 0) - self.f2_round_snap_sig
                f1_td = self.f1_state.get("takedowns_landed", 0) - self.f1_round_snap_td
                f2_td = self.f2_state.get("takedowns_landed", 0) - self.f2_round_snap_td
                f1_gp = self.f1_state.get("effective_grappling_points", 0.0) - self.f1_round_snap_grapple
                f2_gp = self.f2_state.get("effective_grappling_points", 0.0) - self.f2_round_snap_grapple
                f1_fat = self.f1_state.get("fatigue_level", 0) * 100
                f2_fat = self.f2_state.get("fatigue_level", 0) * 100
                f1_sub = self.f1_state.get("submissions_attempted", 0) - self.f1_round_snap_sub
                f2_sub = self.f2_state.get("submissions_attempted", 0) - self.f2_round_snap_sub
                f1_att = self.f1_round_attempts - self.f1_start_attempts
                f2_att = self.f2_round_attempts - self.f2_start_attempts
                f1_td_att = self.f1_state.get("takedowns_attempted", 0) - self.f1_round_snap_td_att
                f2_td_att = self.f2_state.get("takedowns_attempted", 0) - self.f2_round_snap_td_att
                f1_strikes_thrown = self.f1_state.get("strikes_thrown", 0) - self.f1_round_snap_sig
                f2_strikes_thrown = self.f2_state.get("strikes_thrown", 0) - self.f2_round_snap_sig
                yield {"type": "strategy_prompt", "round": round_num,
                       "f1_stats": {"sig_strikes": f1_sig, "strikes_thrown": max(f1_sig, f1_strikes_thrown), "strikes_attempted": f1_att, "takedowns": f1_td, "takedowns_attempted": max(f1_td, f1_td_att), "fatigue": round(f1_fat), "sub_attempts": f1_sub, "grapple_points": round(f1_gp, 1)},
                       "f2_stats": {"sig_strikes": f2_sig, "strikes_thrown": max(f2_sig, f2_strikes_thrown), "strikes_attempted": f2_att, "takedowns": f2_td, "takedowns_attempted": max(f2_td, f2_td_att), "fatigue": round(f2_fat), "sub_attempts": f2_sub, "grapple_points": round(f2_gp, 1)},
                       "f1_total_score": self._get_total_score_for(1),
                       "f2_total_score": self._get_total_score_for(2),
                       "f1_health": self._get_display_health(self.fighter1),
                       "f2_health": self._get_display_health(self.fighter2),
                       "f1Name": self.fighter1.name,
                       "f2Name": self.fighter2.name,
                       "score_detail": f"{int(f1_avg)}-{int(f2_avg)}"}

            if round_num >= 3 and round_num < self.rounds and not self.winner:
                for fighter, state in [(self.fighter1, self.f1_state), (self.fighter2, self.f2_state)]:
                    stop_reason = self.referee.check_doctor_stoppage(fighter, state, self)
                    if stop_reason and random.random() < (0.10 if self.is_title_fight else 0.12):
                        self.winner = self.fighter2 if fighter == self.fighter1 else self.fighter1
                        self.loser = fighter
                        self.win_method = "TKO (Doctor Stoppage)"
                        self.win_round = self.current_round
                        yield {"type": "action", "text": stop_reason, "round": round_num,
                               "time": self._get_time_str(),
                               "f1_health": self._get_display_health(self.fighter1),
                               "f2_health": self._get_display_health(self.fighter2)}
                        yield {"type": "knockout",
                               "text": f"Doctor stoppage! {self.winner.name} wins by {self.win_method}!",
                               "winner": self.winner.name, "method": self.win_method, "round": self.current_round,
                               "time": self._get_time_str()}
                        d = self._get_fight_details()
                        yield {"type": "complete", "winner": self.winner.name,
                               "method": self.win_method, "round": self.win_round,
                               "f1_health": self._get_display_health(self.fighter1),
                               "f2_health": self._get_display_health(self.fighter2),
                               "total_scores": self._get_total_scores(),
                               "f1_details": d["f1"], "f2_details": d["f2"]}
                        return

            if round_num < self.rounds and not self.winner:
                self._check_ai_adaptation(round_num)

        if not self.winner:
            self._determine_decision()
            yield {"type": "decision",
                   "text": self.commentary.generate_post_fight(self.winner, self.win_method, None, True),
                   "winner": self.winner.name if self.winner else "Draw",
                   "method": self.win_method, "details": self._get_decision_details(),
                   "scores": [[j.scores[r][0] for j in self.judges] for r in range(len(self.judges[0].scores))],
                   "total_scores": self._get_total_scores(),
                   "f1_health": self._get_display_health(self.fighter1),
                   "f2_health": self._get_display_health(self.fighter2)}

        details = self._get_fight_details()
        yield {"type": "complete", "winner": self.winner.name if self.winner else "Draw",
               "method": self.win_method, "round": self.win_round,
               "f1_health": self._get_display_health(self.fighter1),
               "f2_health": self._get_display_health(self.fighter2),
               "total_scores": self._get_total_scores(),
               "f1_details": details["f1"],
               "f2_details": details["f2"]}

    # ============================================================
    # TIMING
    # ============================================================

    def _get_time_str(self) -> str:
        remaining = max(0, ROUND_DURATION - self.round_time_elapsed)
        mins = remaining // 60
        secs = remaining % 60
        return f"R{self.current_round} {mins}:{secs:02d}"

    # ============================================================
    # ROUND DETERMINATION
    # ============================================================

    def _determine_actions_this_round(self, round_num: int) -> int:
        """
        Fewer, more meaningful actions per round.
        R1: 1.0x, R2: 1.0x, R3: 1.5x, R4: 1.8x, R5: 2.2x
        Returns count of major beats (each beat may group multiple strikes).
        """
        base_actions = random.randint(20, 30)
        avg_fatigue = (self.f1_state["fatigue_level"] + self.f2_state["fatigue_level"]) / 2
        fatigue_mult = {1: 1.0, 2: 1.0, 3: 1.5, 4: 1.8, 5: 2.2}.get(round_num, 1.5)
        reduction = avg_fatigue * fatigue_mult * 2
        base_actions = max(12, int(base_actions - reduction))
        return base_actions

    def set_corner_advice(self, advice_type: Optional[str]):
        """Apply corner advice modifiers for the next round."""
        self.corner_advice_mods = {}
        if not advice_type:
            return
        advice_map = {
            "aggressive": {"striking_power": 1.05, "hand_speed": 1.02, "aggression": 1.05},
            "defensive": {"composure": 1.05, "durability": 1.03, "discipline": 1.05},
            "body_work": {"body_accuracy": 1.08},
            "takedown": {"takedown_power": 1.10, "takedown_accuracy": 1.10},
            "keep_standing": {"wrestling_defense": 1.10, "athleticism": 1.03},
            "pressure": {"cardio": 1.03, "striking_power": 1.03, "aggression": 1.08},
        }
        self.corner_advice_mods = advice_map.get(advice_type, {})

    def _get_round_phase(self, action_idx: int, total_actions: int) -> str:
        """4-phase round system: feeling_out → exchanges → urgency → finish_hunt"""
        pct = action_idx / max(1, total_actions)
        if pct < 0.25:
            return "feeling_out"
        elif pct < 0.70:
            return "exchanges"
        elif pct < 0.90:
            return "urgency"
        return "finish_hunt"

    # ============================================================
    # CORE ACTION SIMULATION
    # ============================================================

    def _apply_damage_aware_behavior(self, attacker, defender, atk_state, def_state, state_mods, phase):
        """Modify fighter behavior based on accumulated damage.
        Fighters react to injuries, changing their tactics.
        """
        if not atk_state:
            return

        # === LEG DAMAGE: stop kicking ===
        leg_dmg = (atk_state.get("lead_leg_damage", 0) + atk_state.get("rear_leg_damage", 0)) / 2
        if leg_dmg > 50 and random.random() < 0.7:
            # Reduce kick power and kick accuracy significantly
            state_mods["kick_power"] = state_mods.get("kick_power", 1.0) * 0.3
            state_mods["kick_accuracy"] = state_mods.get("kick_accuracy", 1.0) * 0.3
        elif leg_dmg > 30 and random.random() < 0.4:
            state_mods["kick_power"] = state_mods.get("kick_power", 1.0) * 0.6
            state_mods["kick_accuracy"] = state_mods.get("kick_accuracy", 1.0) * 0.6

        # === HEAD/JAW DAMAGE: shell up ===
        jaw_pct = defender.get_group_health("head")
        if jaw_pct < 40 and random.random() < 0.6:
            # Fighter shells up: better defense, worse offense
            state_mods["accuracy"] = state_mods.get("accuracy", 1.0) * 0.85
            state_mods["hand_speed"] = state_mods.get("hand_speed", 1.0) * 0.90
            # Defense is handled via _get_composite_defense which reads state/head health

        # === BODY DAMAGE: reduce takedown attempts ===
        body_fatigue = atk_state.get("body_fatigue", 0)
        if body_fatigue > 60 and random.random() < 0.5:
            state_mods["takedown_power"] = state_mods.get("takedown_power", 1.0) * 0.4
            state_mods["takedown_accuracy"] = state_mods.get("takedown_accuracy", 1.0) * 0.4

        # === FATIGUE: gassed fighters throw fewer power shots ===
        if atk_state["fatigue_level"] > 0.7 and random.random() < 0.5:
            state_mods["striking_power"] = state_mods.get("striking_power", 1.0) * 0.8

    def _simulate_fighter_reaction(self, attacker, defender, atk_state, def_state, atk_strategy, phase):
        """When a fighter is hurt/stunned, they react instead of attacking normally.
        Fixed: never repeats 'frozen', adds varied reactions, and prevents
        stunned fighters from going on offense."""
        if atk_state["cardio_zone"] == "oxygen_debt" and random.random() < 0.08:
            atk_state["stamina"] = max(0, atk_state["stamina"] - 2)
            atk_state["fatigue_level"] = 1.0 - (atk_state["stamina"] / 100)
            self.fight_log.append(f"{attacker.name} is gassed, taking a moment to breathe!")
            self.referee.record_damage_taken(defender, True, attacker=attacker)
            return True

        is_stunned = atk_state.get("stunned", False)
        is_hurt = atk_state.get("hurt", False)
        if not is_stunned and not is_hurt:
            return False

        comp = attacker.get_effective_attribute("composure", atk_state["fatigue_level"])
        fiq = attacker.get_effective_attribute("fight_iq", atk_state["fatigue_level"])
        agg = attacker.get_effective_attribute("aggression", atk_state["fatigue_level"])
        dr = attacker.get_effective_attribute("danger_recognition", atk_state["fatigue_level"])

        if is_stunned:
            # Track how many actions we've been stunned for
            stunned_since = atk_state.get("stunned_since_action", 0)
            atk_state["stunned_since_action"] = atk_state.get("stunned_since_action", 0) + 1

            # Smart fighter: shells up defensively
            if fiq > 55 or comp > 60 or dr > 55:
                if stunned_since <= 1:
                    self.fight_log.append(f"{attacker.name} shells up and covers, trying to recover!")
                elif stunned_since <= 3:
                    self.fight_log.append(f"{attacker.name} clinches desperately to survive!")
                    self._simulate_clinch_attempt(attacker, defender, atk_state["fatigue_level"], atk_strategy)
                else:
                    self.fight_log.append(f"{attacker.name} retreats to the fence, covering up!")
                self._update_momentum(1 if defender == self.fighter1 else 2, 1)
                self.referee.record_damage_taken(defender, True, attacker=attacker)
                return True

            # Aggressive fighter: swings wild (bad idea when stunned)
            if agg > 70:
                if random.random() < 0.6:
                    self.fight_log.append(f"{attacker.name} swings wildly, hurt and desperate!")
                    self._update_momentum(1 if defender == self.fighter1 else 2, 2)
                    self.referee.record_damage_taken(defender, True, attacker=attacker)
                    return True
                else:
                    self.fight_log.append(f"{attacker.name} shells up despite their instincts!")
                    self._update_momentum(1 if defender == self.fighter1 else 2, 1)
                    self.referee.record_damage_taken(defender, True, attacker=attacker)
                    return True

            # Low composure: varied frozen reactions (only first time per stun)
            if comp < 40 or dr < 30:
                reactions = [
                    f"{attacker.name} is frozen! Can't mount any offense!",
                    f"{attacker.name} stumbles back, trying to clear their head!",
                    f"{attacker.name} covers up against the cage, just trying to survive!",
                    f"{attacker.name} is out on their feet, legs wobbling!",
                ]
                idx = min(stunned_since, len(reactions) - 1)
                self.fight_log.append(reactions[idx])
                self._update_momentum(1 if defender == self.fighter1 else 2, 2)
                self.referee.record_damage_taken(defender, True, attacker=attacker)
                return True

            # Default stunned behavior: shell up
            self.fight_log.append(f"{attacker.name} shells up on the cage, unable to respond!")
            self._update_momentum(1 if defender == self.fighter1 else 2, 1)
            self.referee.record_damage_taken(defender, True, attacker=attacker)
            return True

        if is_hurt and not is_stunned:
            if random.random() < 0.35:
                self.fight_log.append(f"{attacker.name} ties up in the clinch to recover!")
                self._simulate_clinch_attempt(attacker, defender, atk_state["fatigue_level"], atk_strategy)
                self.referee.record_damage_taken(defender, True, attacker=attacker)
                return True
            if random.random() < 0.25 and comp < 50:
                self.fight_log.append(f"{attacker.name} circles away, trying to clear their head!")
                self.referee.record_damage_taken(defender, True, attacker=attacker)
                return True
        return False

    def _simulate_movement(self, attacker, defender, atk_state, def_state, phase):
        """Non-strike movement/positioning actions."""
        if Position.is_ground(self.position_system.current_position):
            return False
        if self.position_system.current_position == Position.CLINCH:
            return False

        r = random.random()
        if r < 0.30:
            self.fight_log.append(f"{attacker.name} circles, finding range.")
        elif r < 0.55:
            self.fight_log.append(f"{attacker.name} steps into the pocket, cutting off the cage.")
        elif r < 0.75:
            self.fight_log.append(f"{attacker.name} feints a level change and steps back.")
        elif r < 0.90:
            self.fight_log.append(f"{attacker.name} switches stance, changing the look.")
        else:
            self.fight_log.append(f"Both fighters circle in the center, neither committing.")
        self.referee.record_damage_taken(defender, True, attacker=attacker)
        return True

    def _simulate_feint_sequence(self, attacker, defender, atk_state, def_state, atk_strategy, phase):
        """Feint → opponent reacts → real strike/combo."""
        pos = self.position_system.current_position
        fiq = attacker.get_effective_attribute("fight_iq", atk_state["fatigue_level"])
        def_iq = defender.get_effective_attribute("fight_iq", def_state["fatigue_level"])
        def_adapt = defender.get_effective_attribute("adaptability", def_state["fatigue_level"])
        feint_mods = atk_strategy.get_modifiers()
        feint_chance = calculate_feint_chance(fiq, feint_mods)
        if phase == "feeling_out":
            feint_chance = min(0.7, feint_chance * 1.8)

        if random.random() >= feint_chance:
            return False

        recognized = random.random() < calculate_feint_recognition(def_iq, def_adapt)

        if recognized:
            # Defender reads it, gains momentum
            self.fight_log.append(f"{defender.name} reads the feint from {attacker.name} and doesn't bite!")
            atk_state["feint_count"] = max(0, atk_state.get("feint_count", 0) - 1)
            def_num = 1 if defender == self.fighter1 else 2
            self._update_momentum(def_num, 1)
            self.referee.record_damage_taken(defender, True, attacker=attacker)
            return True

        # Feint works — build stack and throw real strike
        atk_state["feint_count"] = min(3, atk_state.get("feint_count", 0) + 1)
        atk_state["feinted_last_action"] = True
        atk_state["stamina"] = max(0, atk_state["stamina"] - 1)

        # Describe the feint
        feint_desc = [
            f"{attacker.name} feints high, drawing {defender.name}'s hands up — then goes to the body!",
            f"{attacker.name} sells the jab, {defender.name} flinches, and {attacker.name} capitalizes!",
            f"{attacker.name} feints a level change, {defender.name} drops his hands — shot lands!",
            f"{attacker.name} shows a kick, pulls it back, and steps in with a punch!",
            f"{attacker.name} fakes the takedown, {defender.name} sprawls, and eats a kick to the head!",
        ]
        self.fight_log.append(random.choice(feint_desc))

        # Throw a real strike after the feint
        strike_type = self._select_strike(pos, atk_strategy, phase)
        if strike_type not in ("takedown_attempt", "clinch_attempt"):
            target = self._select_target(strike_type, pos, def_state, atk_strategy)
            state_mods = self.f1_machine.get_stat_modifier() if attacker == self.fighter1 else self.f2_machine.get_stat_modifier()
            self._perform_strike(attacker, defender, atk_state, def_state, strike_type, target,
                                atk_strategy, phase, state_mods, combo_bonus=0.15)
        self.referee.record_damage_taken(defender, True, attacker=attacker)
        return True

    def _simulate_counter(self, attacker, defender, atk_state, def_state, atk_strategy, df_strategy, phase):
        """Defender slips/blocks/parries and counters with their own strike."""
        pos = self.position_system.current_position
        defense_action = self._select_defense(defender, df_strategy)
        fight_iq = defender.get_effective_attribute("fight_iq", def_state["fatigue_level"])

        if defense_action == "slip" and random.random() < 0.25 + fight_iq / 500:
            self.fight_log.append(f"{defender.name} slips the strike and fires back with a counter!")
            counter_type = self._select_specific_strike(pos, fight_iq, df_strategy)
            if counter_type not in ("takedown_attempt", "clinch_attempt"):
                c_target = self._select_target(counter_type, pos, def_state, df_strategy)
                state_mods = self.f1_machine.get_stat_modifier() if defender == self.fighter1 else self.f2_machine.get_stat_modifier()
                self._perform_strike(defender, attacker, def_state, atk_state, counter_type, c_target,
                                    df_strategy, phase, state_mods, combo_bonus=0.12)
                def_num = 1 if defender == self.fighter1 else 2
                self._update_momentum(def_num, 2)
            return True

        if defense_action == "parry" and random.random() < 0.2 + fight_iq / 600:
            self.fight_log.append(f"{defender.name} parries and creates an opening, stepping in with a strike!")
            counter_type = "cross"
            c_target = self._select_target(counter_type, pos, def_state, df_strategy)
            state_mods = self.f1_machine.get_stat_modifier() if defender == self.fighter1 else self.f2_machine.get_stat_modifier()
            self._perform_strike(defender, attacker, def_state, atk_state, counter_type, c_target,
                                df_strategy, phase, state_mods, combo_bonus=0.08)
            def_num = 1 if defender == self.fighter1 else 2
            self._update_momentum(def_num, 1)
            return True

        if defense_action == "block" and random.random() < 0.10:
            self.fight_log.append(f"{defender.name} blocks the strike and answers with a sharp cross!")
            c_target = self._select_target("cross", pos, def_state, df_strategy)
            state_mods = self.f1_machine.get_stat_modifier() if defender == self.fighter1 else self.f2_machine.get_stat_modifier()
            self._perform_strike(defender, attacker, def_state, atk_state, "cross", c_target,
                                df_strategy, phase, state_mods)
            def_num = 1 if defender == self.fighter1 else 2
            self._update_momentum(def_num, 1)
            return True

        return False

    def _simulate_exchange(self, atk1, def1, def_state1, atk2, def2, def_state2, phase):
        """Both fighters act in the same beat — one narrative exchange."""
        if Position.is_ground(self.position_system.current_position):
            return False
        if self.position_system.current_position == Position.CLINCH:
            return False

        if not (atk1.get_effective_attribute("aggression", def_state1["fatigue_level"]) > 40 and
                atk2.get_effective_attribute("aggression", def_state2["fatigue_level"]) > 40):
            return False

        pos = self.position_system.current_position
        action1 = self._select_specific_strike(pos, 50, self.strategy1)
        action2 = self._select_specific_strike(pos, 50, self.strategy2)

        roles = [
            (atk1, def1, def_state1, 1, self.strategy1, action1),
            (atk2, def2, def_state2, 2, self.strategy2, action2),
        ]
        random.shuffle(roles)

        results = []
        for i, (a, d, d_state, num, strat, act) in enumerate(roles):
            if act in ("takedown_attempt", "clinch_attempt"):
                results.append(f"{a.name} tries to change levels")
                continue
            if a is self.fighter1:
                state_mods = self.f1_machine.get_stat_modifier()
            else:
                state_mods = self.f2_machine.get_stat_modifier()
            if state_mods["accuracy"] <= 0.4:
                results.append(f"{a.name} can't get going")
                continue
            target = self._select_target(act, pos, d_state, strat)
            atk_state = self.f1_state if a == self.fighter1 else self.f2_state
            def_state = self.f2_state if a == self.fighter1 else self.f1_state
            self._perform_strike(a, d, atk_state, def_state, act, target, strat, phase, state_mods)

            # Check if the last log entry mentions this striker
            if self.fight_log:
                last = self.fight_log[-1]
                if a.name in last:
                    results.append(last)
                    self.fight_log.pop()

        if results:
            combined = f"Both fighters trade! {' — '.join(results[:2])}"
            self.fight_log.append(combined)
            self.f1_round_attempts += 1
            self.f2_round_attempts += 1
            self.referee.record_damage_taken(def1, True, attacker=atk1)
            self.referee.record_damage_taken(def2, True, attacker=atk2)
            return True
        return False

    def _simulate_action(self, phase="exchanges"):
        """Simulate one action exchange between fighters."""
        # Increment position time counter
        self.position_system.position_time += 1

        # === FOUL TIMEOUT CHECK ===
        if self.referee.foul_timeout_active:
            self.referee.foul_timeout_actions -= 1
            if self.referee.foul_timeout_actions <= 0:
                self.referee.foul_timeout_active = False
                self.fight_log.append(f"The referee restarts the action!")
            return

        atk1, def1, atk_state1, def_state1, strat1 = (
            self.fighter1, self.fighter2, self.f1_state, self.f2_state, self.strategy1)
        atk2, def2, atk_state2, def_state2, strat2 = (
            self.fighter2, self.fighter1, self.f2_state, self.f1_state, self.strategy2)

        # Determine if this beat is an exchange (both throw) or single attacker
        agg1 = atk1.get_effective_attribute("aggression", atk_state1["fatigue_level"])
        agg2 = atk2.get_effective_attribute("aggression", atk_state2["fatigue_level"])

        # Exchange beats: ~40% chance when both aggression > 40
        if phase not in ("feeling_out",) and not Position.is_ground(self.position_system.current_position):
            if random.random() < 0.40 and agg1 > 40 and agg2 > 40:
                if self._simulate_exchange(atk1, def1, def_state1, atk2, def2, def_state2, phase):
                    return

        if random.random() < agg1 / (agg1 + agg2 + 1):
            attacker, defender, atk_state, def_state, atk_strategy, df_strategy = \
                atk1, def1, atk_state1, def_state1, strat1, strat2
        else:
            attacker, defender, atk_state, def_state, atk_strategy, df_strategy = \
                atk2, def2, atk_state2, def_state2, strat2, strat1

        if attacker == self.fighter1:
            self.f1_round_attempts += 1
        else:
            self.f2_round_attempts += 1

        state_mods = self.f1_machine.get_stat_modifier() if attacker == self.fighter1 else self.f2_machine.get_stat_modifier()
        if state_mods["accuracy"] <= 0.4:
            return

        # === SECOND WIND CHECK ===
        if self._check_second_wind(atk_state, attacker):
            self.fight_log.append(f"{attacker.name} digs deep and finds a second wind!")

        # Ground game: use dedicated ground action system
        if Position.is_ground(self.position_system.current_position):
            self._simulate_ground_action(atk_state["fatigue_level"],
                                         atk_strategy.get_action_weights(), atk_strategy)
            self.referee.record_damage_taken(defender, False, attacker=attacker)
            return

        # === FIGHTER REACTION (stunned/hurt) ===
        if self._simulate_fighter_reaction(attacker, defender, atk_state, def_state, atk_strategy, phase):
            return

        # === MOVEMENT (feeling_out phase) ===
        if phase == "feeling_out" and random.random() < 0.25:
            if self._simulate_movement(attacker, defender, atk_state, def_state, phase):
                return

        # === FEINT SEQUENCE ===
        if self._simulate_feint_sequence(attacker, defender, atk_state, def_state, atk_strategy, phase):
            return

        # Track action in opponent history (for pattern recognition)
        fight_iq = attacker.get_effective_attribute("fight_iq", atk_state["fatigue_level"])
        def_state.get("opponent_action_history", []).append(
            f"{fight_iq:.0f}_{atk_strategy.current_strategy.get('id', 'unknown') if atk_strategy.current_strategy else 'unknown'}")
        hist = def_state.get("opponent_action_history", [])
        if len(hist) > 12:
            def_state["opponent_action_history"] = hist[-12:]

        # === DAMAGE-AWARE AI BEHAVIOR ===
        self._apply_damage_aware_behavior(attacker, defender, atk_state, def_state, state_mods, phase)

        # Zone-based combo chance adjustment
        cardio_zone = atk_state.get("cardio_zone", "aerobic")
        zone_combo_mod = {"aerobic": 1.0, "anaerobic": 0.5, "oxygen_debt": 0.0}.get(cardio_zone, 1.0)

        # Determine if combo or single strike
        pos_for_combo = "standing"
        if Position.is_ground(self.position_system.current_position):
            pos_for_combo = "ground"
        elif self.position_system.current_position == Position.CLINCH:
            pos_for_combo = "clinch"

        fatigue = atk_state["fatigue_level"]
        combo_type = None
        combo_chance = utils.calculate_combo_chance(fight_iq, fatigue) * zone_combo_mod
        if phase == "feeling_out":
            combo_chance *= 0.3

        if random.random() < combo_chance:
            available_combos = get_combos_for_position(pos_for_combo)
            available_combos = [c for c in available_combos if c["iq_req"] <= fight_iq]
            if available_combos:
                iq_weighted = []
                for c in available_combos:
                    weight = max(0.2, 1.0 - (c["iq_req"] - fight_iq) / 100.0)
                    iq_weighted.extend([c] * int(weight * 10))
                if iq_weighted:
                    combo_type = random.choice(iq_weighted)["id"]

        if combo_type:
            self._execute_combo(attacker, defender, atk_state, def_state, atk_strategy, combo_type, phase, state_mods)
        elif phase == "feeling_out" and random.random() < 0.35:
            if self._simulate_movement(attacker, defender, atk_state, def_state, phase):
                return
            self._execute_single_strike(attacker, defender, atk_state, def_state, atk_strategy, phase, state_mods)
        else:
            self._execute_single_strike(attacker, defender, atk_state, def_state, atk_strategy, phase, state_mods)

        # Defender answers back immediately (~35% after strikes for back-and-forth)
        if not self.winner and not Position.is_ground(self.position_system.current_position):
            if random.random() < 0.35:
                ans_mods = self.f1_machine.get_stat_modifier() if defender == self.fighter1 else self.f2_machine.get_stat_modifier()
                if ans_mods["accuracy"] > 0.4 and def_state["stamina"] >= 5:
                    ans_type = self._select_strike(self.position_system.current_position, df_strategy, phase)
                    if ans_type not in ("takedown_attempt", "clinch_attempt") and not self.winner:
                        ans_target = self._select_target(ans_type, self.position_system.current_position, atk_state, df_strategy)
                        self._perform_strike(defender, attacker, def_state, atk_state, ans_type, ans_target,
                                            df_strategy, phase, ans_mods)

        # Counter opportunity for defender
        if not self.winner and random.random() < 0.20:
            self._simulate_counter(attacker, defender, atk_state, def_state, atk_strategy, df_strategy, phase)

        # Track consecutive unanswered damage
        self.referee.record_damage_taken(defender,
            self.position_system.current_position in (Position.POCKET, Position.DISTANCE, Position.CLINCH),
            attacker=attacker)

    def _execute_single_strike(self, attacker, defender, atk_state, def_state, strategy, phase, state_mods):
        pos = self.position_system.current_position

        # Stamina cost check
        if atk_state["stamina"] < 5:
            self.fight_log.append(f"{attacker.name} is too gassed to attack effectively!")
            return

        action_type = self._select_strike(pos, strategy, phase)

        # Route non-strike actions to their handlers
        if action_type == "takedown_attempt":
            self._simulate_takedown(attacker, defender, atk_state["fatigue_level"], strategy)
            return
        elif action_type == "clinch_attempt":
            self._simulate_clinch_attempt(attacker, defender, atk_state["fatigue_level"], strategy)
            return

        strike_type = action_type
        target = self._select_target(strike_type, pos, def_state, strategy)

        self._perform_strike(attacker, defender, atk_state, def_state, strike_type, target, strategy, phase, state_mods)

    def _execute_combo(self, attacker, defender, atk_state, def_state, strategy, combo_key, phase, state_mods):
        combo_data = COMBINATIONS.get(combo_key)
        if not combo_data:
            self._execute_single_strike(attacker, defender, atk_state, def_state, strategy, phase, state_mods)
            return
        strikes = combo_data["strikes"]
        combo_name = combo_key.replace("-", " ")

        stamina_mult = combo_data.get("stamina_mult", 1.0)
        base_bonus = combo_data.get("power_bonus", 0.0)

        feint_stack = atk_state.get("feint_count", 0)
        combo_feint_bonus = 1.0 + feint_stack * 0.03
        combo_power_bonus = base_bonus * combo_feint_bonus

        # Scale stamina cost per strike in combo
        stamina_cost_mult = 1.0

        results = []
        landed = 0
        for i, strike_type in enumerate(strikes):
            if self.winner:
                break
            pos = self.position_system.current_position
            actual_strike = strike_type
            if strike_type == "kick" and pos != Position.DISTANCE:
                actual_strike = "cross"
            elif strike_type in ("knee", "elbow") and not Position.is_ground(pos) and pos != Position.CLINCH:
                actual_strike = random.choice(["hook", "uppercut"])
            target = self._select_target(actual_strike, pos, def_state, strategy)
            accuracy_penalty = 1.0 - (i * 0.07)
            mod_copy = state_mods.copy()
            mod_copy["accuracy"] *= accuracy_penalty

            group = "HEAD" if target in ("head", "jaw", "temple", "nose", "left_eye", "right_eye") else (
                    "BODY" if target in ("body", "chest", "solar_plexus", "liver", "ribs") else "LEGS")

            # Scale stamina cost: 1st strike ×1.0, 2nd ×1.15, 3rd ×1.35, 4th+ ×1.55
            strike_scale = [1.0, 1.15, 1.35, 1.55]
            scaled_stamina = stamina_mult * (strike_scale[i] if i < len(strike_scale) else 1.55)

            before_len = len(self.fight_log)
            self._perform_strike(attacker, defender, atk_state, def_state, actual_strike, target,
                                strategy, phase, mod_copy, combo_bonus=combo_power_bonus, stamina_mult=scaled_stamina)

            # Capture what _perform_strike logged and remove it for grouping
            if len(self.fight_log) > before_len:
                last_entry = self.fight_log.pop()
                if "misses with" in last_entry:
                    results.append(f"missed {actual_strike}")
                else:
                    if not last_entry.endswith("— CRITICAL HIT!"):
                        last_entry = last_entry.rsplit(" — ", 1)[0] if " — " in last_entry else last_entry
                    results.append(f"{last_entry.split(' to ')[-1] if ' to ' in last_entry else last_entry}")
                    landed += 1
            else:
                results.append(f"missed {actual_strike}")

        if i == len(strikes) - 1:
            atk_state["feint_count"] = 0

        head_pct = defender.get_zone_health_pct("jaw") * 0.5 + defender.get_zone_health_pct("temple") * 0.5
        if head_pct < 40 and random.random() < 0.3:
            results.append(f"{defender.name} staggered by the combination!")

        if def_state.get("state") == "DOWN" or self.winner:
            pass

        if results:
            detail = ", ".join([r for r in results[:4]])
            self.fight_log.append(f"{attacker.name} throws a {combo_name}! Landed {landed}/{len(strikes)}: {detail}")



    def _select_defense(self, defender, strategy) -> str:
        """Weighted defense selection based on fighter attributes and strategy."""
        dur = defender.get_effective_attribute("durability", 0)
        comp = defender.get_effective_attribute("composure", 0)
        fiq = defender.get_effective_attribute("fight_iq", 0)
        ath = defender.get_effective_attribute("athleticism", 0)

        weights = {
            "block": dur / 100 * 0.35 + 0.20,
            "slip": comp / 100 * 0.30,
            "parry": fiq / 100 * 0.25,
            "roll": ath / 100 * 0.10,
            "shell": 0.10,
        }
        return utils.weighted_random_choice(weights)

    def _select_strike(self, pos, strategy, phase) -> str:
        """Select strike type based on position, strategy, and phase."""
        weights = strategy.get_action_weights()

        # Phase adjustments
        if phase == "feeling_out":
            weights = {k: v * 0.7 for k, v in weights.items()}
            weights["strike"] = weights.get("strike", 0.7) * 1.3  # Jab-heavy early
        elif phase in ("urgency", "finish_hunt"):
            weights["takedown"] *= 0.85
            weights["clinch"] *= 0.6

        # Position adjustments
        if pos == Position.DISTANCE:
            weights["strike"] *= 1.5
            weights["takedown"] *= 1.0
        elif pos == Position.POCKET:
            weights["strike"] *= 1.2
        elif pos == Position.CLINCH:
            weights["clinch"] *= 2.0
            weights["strike"] *= 0.5
        elif Position.is_ground(pos):
            weights["takedown"] = 0
            weights["clinch"] = 0
            weights["strike"] = 1.0

        total = sum(weights.values())
        if total <= 0:
            return "cross"
        normalized = {k: v / total for k, v in weights.items()}
        choice = utils.weighted_random_choice(normalized)

        if choice == "strike":
            fight_iq = 50
            return self._select_specific_strike(pos, fight_iq, strategy)
        elif choice == "takedown":
            return "takedown_attempt"
        elif choice == "clinch":
            return "clinch_attempt"
        return "jab"

    def _select_specific_strike(self, pos, fight_iq=50, strategy=None) -> str:
        # Strategy influences strike type selection
        kick_bias = 0.0
        body_bias = 0.0
        if strategy and strategy.current_strategy:
            sid = strategy.current_strategy.get("id")
            if sid == "leg_kick_focus":
                kick_bias = 0.30
            elif sid == "kickboxing_focus":
                kick_bias = 0.15
            elif sid == "muay_thai_focus":
                kick_bias = 0.10
            elif sid == "body_shot_focus":
                body_bias = 0.20

            # Boxing focus prefers punches
            if sid in ("boxing_focus", "power_hunting"):
                kick_bias = -0.10

        if pos == Position.DISTANCE:
            # Mix of kicks and punches based on strategy
            types = ["jab", "cross", "kick"]
            if random.random() < 0.15 + fight_iq / 500:
                types.append("superman_punch")
            # Apply kick bias by adjusting probabilities
            if kick_bias > 0:
                types.extend(["kick"] * int(kick_bias * 10))
            elif kick_bias < 0:
                # Reduce kicks
                if "kick" in types:
                    types.remove("kick")
            return random.choice(types)
        elif pos == Position.POCKET:
            return random.choice(["jab", "cross", "hook", "uppercut", "knee", "elbow"])
        elif pos in (Position.CLINCH,):
            return random.choice(["knee", "elbow"])
        elif Position.is_ground(pos):
            return random.choice(["hammerfist", "elbow", "punch"])
        return "jab"

    def _select_target(self, strike_type, pos, def_state, strategy=None) -> str:
        """Aimed targeting based on strike type — different strikes favor different zones."""
        is_kick = "kick" in strike_type
        is_ground = Position.is_ground(pos)

        # Strategy-dependent target bias
        body_bias = 0.0
        leg_bias = 0.0
        head_bias = 0.0
        if strategy:
            mods = strategy.get_modifiers()
            body_bias = mods.get("body_damage_bonus", 0.0) - 1.0 if mods.get("body_damage_bonus") else 0.0
            kick_bonus = mods.get("kick_power", 1.0)

        if is_kick:
            r = random.random()
            # Leg kick focus increases leg target chance
            if strategy and strategy.current_strategy and strategy.current_strategy.get("id") == "leg_kick_focus":
                if r < 0.65:
                    return "legs"
                elif r < 0.85:
                    return "body"
                else:
                    return "head"
            if r < 0.40:
                return "legs"
            elif r < 0.75:
                return "body"
            else:
                return "head"

        if is_ground:
            return random.choice(["head", "head", "body", "body", "jaw"])

        if strike_type == "jab":
            r = random.random()
            if r < 0.40:
                return "nose"
            elif r < 0.65:
                return "jaw"
            elif r < 0.85:
                return "head"
            else:
                return "body"
        elif strike_type == "cross":
            r = random.random()
            if r < 0.35:
                return "jaw"
            elif r < 0.55:
                return "temple"
            elif r < 0.75:
                return "nose"
            elif r < 0.90:
                return "head"
            else:
                return "body"
        elif strike_type == "hook":
            r = random.random()
            if r < 0.40:
                return "temple"
            elif r < 0.70:
                return "jaw"
            elif r < 0.85:
                return "head"
            else:
                return "body"
        elif strike_type == "uppercut":
            r = random.random()
            if r < 0.50:
                return "jaw"
            elif r < 0.75:
                return "body"
            else:
                return "head"
        elif strike_type in ("knee", "elbow"):
            r = random.random()
            if r < 0.50:
                return "head"
            elif r < 0.80:
                return "body"
            else:
                return "jaw"
        elif strike_type == "body_shot":
            r = random.random()
            if r < 0.40:
                return "solar_plexus"
            elif r < 0.75:
                return "liver"
            else:
                return "ribs"
        elif strike_type == "superman_punch":
            r = random.random()
            if r < 0.35:
                return "jaw"
            elif r < 0.55:
                return "head"
            else:
                return "body"

        # Default with body/head bias from strategy
        r = random.random() * 1.0
        r -= body_bias * 0.3  # body_bias shifts probability toward body
        if r < 0.50:
            return random.choice(["head", "head", "jaw", "temple"])
        elif r < 0.75:
            return "body"
        else:
            return random.choice(["jaw", "temple", "nose"])

    def _perform_strike(self, attacker, defender, atk_state, def_state,
                        strike_type, target, strategy, phase, state_mods,
                        combo_bonus=0.0, stamina_mult=1.0):
        """Execute a strike with full damage calculation."""
        if attacker == self.fighter1:
            self.f1_state["strikes_thrown"] = self.f1_state.get("strikes_thrown", 0) + 1
        else:
            self.f2_state["strikes_thrown"] = self.f2_state.get("strikes_thrown", 0) + 1
        profile = STRIKE_PROFILES.get(strike_type, STRIKE_PROFILES["jab"])

        is_kick = "kick" in strike_type
        power_attr = "kick_power" if is_kick else "striking_power"
        accuracy_attr = "kick_accuracy" if is_kick else "striking_accuracy"
        speed_attr = "kick_speed" if is_kick else "hand_speed"

        # Base stats
        fight_iq = attacker.get_effective_attribute("fight_iq", atk_state["fatigue_level"])
        discipline = attacker.get_effective_attribute("discipline", atk_state["fatigue_level"])
        composure = attacker.get_effective_attribute("composure", atk_state["fatigue_level"])

        # Strategy modifiers
        modifiers = strategy.get_modifiers()
        sp_mod = modifiers.get("striking_power", 1.0)
        hs_mod = modifiers.get("hand_speed", 1.0)

        # Phase power scaling
        phase_power = {"feeling_out": 0.75, "exchanges": 1.0, "urgency": 1.15, "finish_hunt": 1.3}.get(phase, 1.0)

        # Reach advantage
        reach_mod = self.position_system.get_reach_advantage(attacker, defender)

        # Momentum modifier
        attacker_num = 1 if attacker == self.fighter1 else 2
        momentum_mod = self.get_momentum_modifier(attacker_num)

        # Crowd modifier
        crowd_mod = self.get_crowd_modifier(attacker_num)

        # === STANCE MODIFIERS ===
        a_stance = self.fighter1_stance if attacker == self.fighter1 else self.fighter2_stance
        d_stance = self.fighter2_stance if attacker == self.fighter1 else self.fighter1_stance
        stance_mods = get_stance_modifiers(a_stance, d_stance)
        power_stance_mod = stance_mods["power_mod"]
        speed_stance_mod = stance_mods["speed_mod"]
        acc_stance_mod = stance_mods["accuracy_mod"]

        # Power hand bonus: rear hand strikes (cross, rear hook, uppercut from rear) get +10%
        rear_hand_strikes = ["cross", "hook", "uppercut"]
        power_hand_bonus = 1.10 if strike_type in rear_hand_strikes else 1.0
        lead_hand_speed_bonus = 1.08 if strike_type == "jab" else 1.0

        # === PRECISION ROLL ===
        # Gaussian variance in how cleanly a strike lands
        precision = max(0.4, min(1.6, random.gauss(1.0, 0.15)))

        # === FEINT BONUS ===
        feint_stack = atk_state.get("feint_count", 0)
        feint_acc_bonus = 1.0 + feint_stack * 0.08
        feint_power_bonus = 1.0 + feint_stack * 0.05
        feint_crit_bonus = 1.0 + feint_stack * 0.10

        # State modifiers from fighter state machine
        # Leg damage effects: kick power reduced by rear leg damage, movement by both
        attacker_fstate = self.f1_state if attacker == self.fighter1 else self.f2_state
        if is_kick:
            kick_penalty = self._get_leg_kick_penalty(attacker_fstate)
        else:
            kick_penalty = 1.0
        move_mod = self._get_leg_damage_modifier(attacker_fstate)
        # Leg-damaged fighters move slower, affecting speed of action
        leg_speed_mod = max(0.7, move_mod)

        # Rib injury penalty: reduced striking power
        if attacker_fstate.get("rib_injury_active"):
            rib_power_penalty = 0.85
        else:
            rib_power_penalty = 1.0

        # Confidence modifier: confident fighters hit harder
        confidence = getattr(attacker, 'confidence', 50)
        conf_mod = 1.0 + (confidence - 50) / 300.0  # 0.83 at 0, 1.0 at 50, 1.17 at 100

        # Aggression boost: aggressive fighters commit more to strikes
        aggression = attacker.get_effective_attribute("aggression", atk_state["fatigue_level"])
        agg_mod = 1.0 + (aggression - 50) / 250.0  # 0.80 at 0, 1.0 at 50, 1.20 at 100

        # Momentum burst: hot streak adds power, cold streak reduces
        momentum_burst_mod = 1.0 + momentum_mod * 0.15  # ±15% at max momentum swing

        # Corner advice bonus for this round
        corner_bonus = self.corner_advice_mods.get(power_attr, 1.0)

        power = (attacker.get_effective_attribute(power_attr, atk_state["fatigue_level"])
                 * sp_mod * phase_power * momentum_mod * crowd_mod
                 * power_stance_mod * power_hand_bonus * feint_power_bonus
                 * kick_penalty * rib_power_penalty * conf_mod * agg_mod * momentum_burst_mod * corner_bonus)
        speed = (attacker.get_effective_attribute(speed_attr, atk_state["fatigue_level"])
                 * hs_mod * speed_stance_mod * lead_hand_speed_bonus * leg_speed_mod)
        raw_accuracy = attacker.get_effective_attribute(accuracy_attr, atk_state["fatigue_level"])

        # Composite accuracy calculation
        accuracy = raw_accuracy * (speed / 100) * reach_mod * (1.0 + fight_iq / 600)
        accuracy *= (0.8 if phase == "feeling_out" else (1.15 if phase in ("urgency", "finish_hunt") else 1.0))
        accuracy *= state_mods.get("accuracy", 1.0)
        accuracy *= acc_stance_mod * feint_acc_bonus * precision

        # Vision penalty from blood/swelling
        blood_penalty = self._get_blood_penalty(attacker)
        vision_penalty = atk_state.get("vision_impairment", 0)
        if vision_penalty > 0:
            accuracy *= max(0.4, 1.0 - vision_penalty / 100.0)
        accuracy *= blood_penalty

        # Stun effects
        if atk_state["stunned"]:
            accuracy *= 0.4
            power *= 0.55
        if atk_state["hurt"]:
            accuracy *= 0.75
            power *= 0.80

        # Fatigue impact on accuracy
        fatigue = atk_state["fatigue_level"]
        accuracy *= max(0.5, 1.0 - fatigue * 0.4)

        # Cardio zone accuracy penalty
        _, _, zone_acc_penalty = self._get_cardio_zone(atk_state)
        accuracy *= (1.0 - zone_acc_penalty)

        # Clamp accuracy
        accuracy = utils.clamp(accuracy, 3, 98)

        # Determine if strike lands and at what severity (target-zone-aware)
        defense_score = self._get_composite_defense(defender, def_state, atk_state, target)

        # === MISS GATE ===
        cardio = attacker.get_effective_attribute("cardio", atk_state["fatigue_level"])
        # Miss only when defense significantly exceeds accuracy
        def_ratio = defense_score / max(1, accuracy)
        miss_chance = 0.05 + max(0, (def_ratio - 1.0) * 0.12)
        miss_chance = utils.clamp(miss_chance, 0.05, 0.45)

        if random.random() < miss_chance:
            # Full stamina cost for missing — wasted energy
            self._apply_stamina_cost(atk_state, strike_type, atk_state["fatigue_level"], cardio, stamina_mult)
            self._last_landed = False
            # Log what the defender did to cause the miss
            def_action = self._select_defense(defender, strategy)
            if def_action == "block":
                self._last_subtype = "block"
                self.fight_log.append(f"{defender.name} blocks the {strike_type}!")
            elif def_action == "slip":
                self._last_subtype = "slip"
                self.fight_log.append(f"{defender.name} slips the {strike_type}!")
            elif def_action == "parry":
                self._last_subtype = "parry"
                self.fight_log.append(f"{defender.name} parries the {strike_type}!")
            elif def_action == "roll":
                self._last_subtype = "slip"
                self.fight_log.append(f"{defender.name} rolls with the {strike_type}!")
            else:
                self._last_subtype = "miss"
                self.fight_log.append(f"{attacker.name} misses with a {strike_type}!")
            return

        # Landed — full stamina cost (missing also costs same stamina as punishment)
        self._apply_stamina_cost(atk_state, strike_type, atk_state["fatigue_level"], cardio, stamina_mult)
        self._last_landed = True
        self._last_subtype = "strike"

        tier = utils.determine_severity(
            accuracy, defense_score, power, composure,
            self.get_adrenaline(1 if attacker == self.fighter1 else 2),
            attacker_stats=atk_state, defender_stats=def_state, target=target
        )

        self._last_severity = tier["name"]
        is_critical = utils.check_critical_hit(accuracy, composure,
                                                 self.get_adrenaline(1 if attacker == self.fighter1 else 2))

        # Calculate damage
        weight_mod = self._strike_weight_modifier(attacker.weight_class)

        # Build damage formula
        base_damage = profile["base_damage"]
        damage_multiplier = tier["mult"] * weight_mod * (1.0 + combo_bonus)

        # Power contribution (non-linear scaling)
        power_contribution = (power / 50.0) ** 0.85

        # Defense contribution (non-linear — diminishing returns at high defense)
        defense_factor = defense_score / 120.0
        defense_reduction = 1.0 / (1.0 + defense_factor * 2.2)

        # Calculate raw damage
        raw_damage = base_damage * power_contribution * damage_multiplier * defense_reduction

        # Critical hit doubles damage
        if is_critical:
            raw_damage *= 2.0
            tier_name = tier["name"]
            tier = {"name": f"CRITICAL {tier_name}", "mult": tier["mult"] * 2,
                    "knockdown_chance": tier["knockdown_chance"] * 2,
                    "vision_damage": tier["vision_damage"] * 2}

        # Randomization (±15% gaussian)
        raw_damage += random.gauss(0, raw_damage * 0.15)
        damage = max(1, int(raw_damage))

        # Target-specific modifiers
        if target in ("body", "ribs"):
            damage = int(damage * 0.8)
        elif target in ("solar_plexus",):
            damage = int(damage * 0.9)  # Less raw damage, more stun effect
        elif target == "liver":
            damage = int(damage * 1.1)  # More damage to liver
        elif target == "legs":
            damage = int(damage * 0.55)
        elif target in ("jaw", "temple"):
            damage = int(damage * 1.2)
        elif target == "nose":
            damage = int(damage * 0.85)

        # Apply damage to zone
        actual_damage = defender.apply_damage_to_zone(target, damage, self)

        # Momentum updates
        attacker_num = 1 if attacker == self.fighter1 else 2
        tier_name = tier["name"]
        kd_chance = tier.get("knockdown_chance", 0)
        if is_critical:
            self._update_momentum(attacker_num, 8)
            self._update_momentum(3 - attacker_num, -5)
            self._update_crowd_excitement(8)
        elif tier_name in ("Devastating", "Flush"):
            self._update_momentum(attacker_num, 5)
            self._update_momentum(3 - attacker_num, -3)
            self._update_crowd_excitement(5)
        elif tier_name in ("Solid",):
            self._update_momentum(attacker_num, 2)
            self._update_crowd_excitement(3)
        elif tier_name in ("Glancing", "Blocked"):
            self._update_momentum(3 - attacker_num, 1)

        # Update state tracking
        if attacker == self.fighter1:
            self.f1_actions_landed += 1
            self.f1_state["significant_strikes_landed"] += 1
            self.f1_state["rounds_damage_dealt"].append(actual_damage)
        else:
            self.f2_actions_landed += 1
            self.f2_state["significant_strikes_landed"] += 1
            self.f2_state["rounds_damage_dealt"].append(actual_damage)

        # Update body fatigue (now targeted by body sub-targets too)
        defender_state = def_state
        if target in ("body", "solar_plexus", "liver", "ribs", "chest"):
            defender_state["body_fatigue"] = min(100, defender_state["body_fatigue"] + actual_damage * 0.5)
            # Body damage drains attacker stamina too (body shots are tiring)
            stamina_drain = int(actual_damage * 0.3)
            atk_state["stamina"] = max(0, atk_state["stamina"] - stamina_drain)

        # === BREATHING SYSTEM ===
        if target in ("body", "solar_plexus", "liver", "ribs", "chest"):
            breathing_reduction = actual_damage * 0.6
            defender_state["breathing_capacity"] = max(0, defender_state["breathing_capacity"] - breathing_reduction)
            # Commentary at thresholds
            br = defender_state["breathing_capacity"]
            if br < 30 and random.random() < 0.4:
                self.fight_log.append(f"{defender.name} can barely breathe!")
            elif br < 50 and random.random() < 0.3:
                self.fight_log.append(f"{defender.name} is gasping for air!")

        # === LIVER SHOT SYSTEM ===
        if target == "liver":
            defender_state["liver_damage"] = min(100, defender_state["liver_damage"] + actual_damage)
            ld = defender_state["liver_damage"]
            fold_chance = 0
            if ld >= 30:
                fold_chance = (ld - 20) / 80.0
            if ld >= 50:
                fold_chance = (ld - 10) / 60.0
            if ld >= 70:
                fold_chance = 1.0
            if random.random() < fold_chance:
                defender_state["stunned"] = True
                defender_state["stunned_timer"] = random.randint(2, 4)
                self._transition_fighter_state(defender, def_state, "STUNNED")
                self.fight_log.append(f"LIVER SHOT! {defender.name} is folding!")

        # === SOLAR PLEXUS STAMINA BURST ===
        if target == "solar_plexus" and tier["name"] in ("Solid", "Flush", "Devastating"):
            # Immediate stamina drain
            stamina_burst = 8 + int(actual_damage * 0.5)
            defender_state["stamina"] = max(0, defender_state["stamina"] - stamina_burst)
            defender_state["fatigue_level"] = 1.0 - (defender_state["stamina"] / 100)
            if random.random() < 0.35:
                defender_state["stunned"] = True
                defender_state["stunned_timer"] = random.randint(1, 2)
                self._transition_fighter_state(defender, def_state, "STUNNED")
                self.fight_log.append(f"{defender.name} is winded from the solar plexus shot! {stamina_burst} stamina drained!")
            else:
                self.fight_log.append(f"{defender.name} feels that body shot — gasps!")

        # === RIBS INJURY ACCUMULATION ===
        if target == "ribs" and tier["name"] in ("Solid", "Flush", "Devastating"):
            defender_state["rib_damage"] = defender_state.get("rib_damage", 0) + actual_damage
            rib_dmg = defender_state["rib_damage"]
            if rib_dmg > 60 and random.random() < 0.15:
                self.fight_log.append(f"{defender.name} may have broken ribs from that shot! Power and cardio affected!")
                defender_state["body_fatigue"] = min(100, defender_state["body_fatigue"] + 15)
                # Also reduce striking power for the rest of the fight
                defender_state["rib_injury_active"] = True
            elif rib_dmg > 40 and random.random() < 0.10:
                self.fight_log.append(f"{defender.name} winces from the rib shot!")
                defender_state["body_fatigue"] = min(100, defender_state["body_fatigue"] + 8)
            elif rib_dmg > 20 and random.random() < 0.05:
                self.fight_log.append(f"Body shot to the ribs! {defender.name} is feeling that!")

        # Per-leg damage tracking (increased accumulation for visible impact)
        if target == "legs":
            leg_target = random.choice(["lead_leg", "rear_leg"])
            leg_accum = actual_damage * 1.2  # Increased from 0.6
            if leg_target == "lead_leg":
                defender_state["lead_leg_damage"] = min(100, defender_state["lead_leg_damage"] + leg_accum)
            else:
                defender_state["rear_leg_damage"] = min(100, defender_state["rear_leg_damage"] + leg_accum)
            defender_state["leg_damage"] = min(100, defender_state["leg_damage"] + actual_damage * 0.6)
        elif target in ("lead_leg", "rear_leg"):
            defender_state[f"{target}_damage"] = min(100, defender_state.get(f"{target}_damage", 0) + actual_damage * 1.2)

        # Head damage tracking
        if target in ("head", "jaw", "temple", "left_eye", "right_eye", "nose"):
            defender_state["swelling"] = min(100, defender_state["swelling"] + actual_damage * 0.3)

        # Check for cut (only on head/face strikes)
        cut_chance = 0.015 * (1 - defender.get_effective_attribute("durability", 0) / 150)
        if tier["name"] in ("Solid", "Flush", "Devastating", "CRITICAL Solid", "CRITICAL Flush", "CRITICAL Devastating"):
            cut_chance *= 1.5 if "CRITICAL" not in tier["name"] else 2.5

        if target in ("head", "jaw", "temple", "left_eye", "right_eye", "nose") and random.random() < cut_chance:
            cut = {"severity": random.uniform(0.1, 0.4), "location": target}
            defender_state["cuts"].append(cut)
            if actual_damage > 5:
                self.fight_log.append(f"Cut opens on {defender.name}'s {target}!")

        # Update body damage level effects
        body_damage = defender_state["body_fatigue"]
        for level in reversed(utils.BODY_DAMAGE_LEVELS):
            if body_damage >= level["threshold"] and level.get("desc"):
                self.fight_log.append(level["desc"].format(fighter=defender.name))
                break

        # Stamina drain for defender from body damage
        if target in ("body", "solar_plexus", "liver", "ribs", "chest"):
            body_damage = defender_state["body_fatigue"]
            bd_effects = utils.get_body_damage_level(body_damage)
            if bd_effects:
                stamina_drain_mod = bd_effects["stamina_drain"]
                def_state["stamina"] = max(0, def_state["stamina"] - int(stamina_drain_mod * 15))

        # Build and log the strike entry BEFORE stun/KD checks
        log_entry = self.commentary.generate_strike_commentary(attacker, defender, strike_type, target, self.position_system.current_position)
        if is_critical:
            log_entry += " — CRITICAL!"
        self.fight_log.append(log_entry)

        # === FOUL CHECK ===
        attacker_num = 1 if attacker == self.fighter1 else 2
        foul_type = self.referee.check_foul(attacker, defender, attacker_num)
        if foul_type:
            consequence = self.referee.record_foul(attacker_num, foul_type)
            if consequence == "verbal":
                self.fight_log.append(f"VERBAL WARNING: {attacker.name} fouls — {foul_type}! The referee warns them!")
            elif consequence == "official warning":
                self.fight_log.append(f"OFFICIAL WARNING: {attacker.name} commits another {foul_type}! The referee issues an official warning!")
                self._update_momentum(3 - attacker_num, 5)
            elif consequence == "point deduction":
                self.fight_log.append(f"POINT DEDUCTION: {attacker.name} is deducted a point for the {foul_type}!")
                self._update_momentum(3 - attacker_num, 10)
                # Deduct point from cumulative score
                if hasattr(self, 'judges') and self.judges and self.judges[0].scores:
                    for j in self.judges:
                        if attacker_num == 1 and j.scores:
                            j.scores[-1][0] = max(0, j.scores[-1][0] - 1)
                        elif attacker_num == 2 and j.scores:
                            j.scores[-1][1] = max(0, j.scores[-1][1] - 1)
            elif consequence == "disqualification":
                self.fight_log.append(f"DISQUALIFICATION! {attacker.name} is DQed for repeated fouls — the {foul_type}! {defender.name} wins!")
                self.winner = defender
                self.loser = attacker
                self.win_method = "DQ (Fouls)"
                self.win_round = self.current_round
                return

            # Low blow / eye poke results in brief timeout
            if foul_type in ("low blow", "eye poke") and consequence != "disqualification":
                self.referee.foul_timeout_active = True
                self.referee.foul_timeout_actions = random.randint(2, 4)
                self.fight_log.append(f"{defender.name} gets time to recover from the {foul_type}!")

        # Check for stun and state transitions
        head_pct = defender.get_group_health("head")
        body_pct = defender.get_group_health("body")

        # Mark hurt state
        if head_pct < 55 or body_pct < 45:
            defender_state["hurt"] = True
            self._transition_fighter_state(defender, def_state, "HURT")
        if head_pct < 30:
            defender_state["stunned"] = True
            defender_state["stunned_timer"] = max(defender_state["stunned_timer"], 2)
            defender_state["stunned_since_action"] = 0
            self._transition_fighter_state(defender, def_state, "STUNNED")

        # Stun check from strike severity
        stun_chance = tier.get("knockdown_chance", 0)
        if defender_state["stunned"]:
            stun_chance *= 1.5
        if defender_state["hurt"]:
            stun_chance *= 1.2
        if random.random() < stun_chance:
            defender_state["stunned"] = True
            defender_state["stunned_timer"] = random.randint(2, 4)
            defender_state["stunned_since_action"] = 0
            self._transition_fighter_state(defender, def_state, "STUNNED")

        # Check for knockdown (KO threshold) — minimum round 2 before KOs
        if self.current_round >= 2 and target in ("head", "jaw", "temple"):
            severity = tier["name"]
            head_pct = defender.get_group_health("head")
            if (severity == "Devastating" or
                (severity in ("Flush", "Solid") and head_pct <= 25)):
                self._check_knockdown(attacker, defender, atk_state, def_state, target, actual_damage,
                                       atk_state["fatigue_level"], strike_type)

        # If knockdown happened, update the strike log entry with a DROPS marker
        if def_state.get("knockdown", False):
            for i in range(len(self.fight_log) - 1, -1, -1):
                if attacker.name in self.fight_log[i] and "DROPS" not in self.fight_log[i]:
                    self.fight_log[i] += f" — DROPS {defender.name}!"
                    break

        # Update combo tracking
        atk_state["combo_count"] += 1

        # Vision impairment update
        vision_damage = tier.get("vision_damage", 0) * 100
        def_state["vision_impairment"] = min(80, def_state["vision_impairment"] + vision_damage)

    def _get_leg_damage_modifier(self, fighter_state: dict) -> float:
        """Return movement modifier based on cumulative leg damage (0.0-1.0)."""
        lead = fighter_state.get("lead_leg_damage", 0)
        rear = fighter_state.get("rear_leg_damage", 0)
        avg = (lead + rear) / 2
        if avg < 20:
            return 1.0
        elif avg < 40:
            return 0.92
        elif avg < 60:
            return 0.78
        elif avg < 80:
            return 0.55
        else:
            return 0.30

    def _get_leg_takedown_penalty(self, fighter_state: dict) -> float:
        """Return takedown defense modifier based on lead leg damage."""
        lead = fighter_state.get("lead_leg_damage", 0)
        if lead < 20:
            return 1.0
        elif lead < 40:
            return 0.92
        elif lead < 60:
            return 0.80
        elif lead < 80:
            return 0.60
        else:
            return 0.40

    def _get_leg_kick_penalty(self, fighter_state: dict) -> float:
        """Return kick power modifier based on rear leg damage."""
        rear = fighter_state.get("rear_leg_damage", 0)
        if rear < 20:
            return 1.0
        elif rear < 40:
            return 0.85
        elif rear < 60:
            return 0.60
        elif rear < 80:
            return 0.35
        else:
            return 0.15

    def _apply_leg_damage_effects(self, fighter_state: dict, fighter_num: int):
        """Apply leg damage effects to state machine and log commentary at thresholds."""
        lead = fighter_state.get("lead_leg_damage", 0)
        rear = fighter_state.get("rear_leg_damage", 0)
        # Log commentary at thresholds
        if lead > 50 and random.random() < 0.15:
            fighter = self.fighter1 if fighter_num == 1 else self.fighter2
            self.fight_log.append(f"{fighter.name}'s lead leg is chewed up!")
        if rear > 50 and random.random() < 0.15:
            fighter = self.fighter1 if fighter_num == 1 else self.fighter2
            self.fight_log.append(f"{fighter.name}'s rear leg is giving out!")

    def _get_composite_defense(self, defender, def_state, atk_state, target: str = "head") -> float:
        """
        Calculate complete defensive rating, target-zone-aware.
        Uses new per-zone stats: head_movement, blocking, footwork_defense,
        parrying for striking defense.
        """
        fatigue = def_state["fatigue_level"]

        # Per-zone defense using the new multi-stat system
        defense = utils.calculate_striking_defense(defender, fatigue, target)

        # Stance familiarity bonus
        d_stance = self.fighter2_stance if defender == self.fighter2 else self.fighter1_stance
        a_stance = self.fighter1_stance if defender == self.fighter2 else self.fighter2_stance
        if d_stance == a_stance:
            defense *= 1.03

        # State modifiers
        state_name = def_state.get("state", "NORMAL")
        if state_name == "STUNNED":
            defense *= 0.40
        elif state_name == "ROCKED":
            defense *= 0.60
        elif state_name == "HURT":
            defense *= 0.80

        # Fatigue reduces defense
        defense *= max(0.5, 1.0 - fatigue * 0.3)

        # Vision impairment
        vision = def_state.get("vision_impairment", 0)
        if vision > 20:
            defense *= max(0.6, 1.0 - (vision - 20) / 200.0)

        # Leg damage
        leg_mod = self._get_leg_damage_modifier(def_state)
        defense *= (0.6 + 0.4 * leg_mod)

        # Pattern read bonus
        if def_state.get("pattern_read"):
            defense *= def_state.get("pattern_read_bonus", 1.0)

        return utils.clamp(defense, 10, 95)

    def _get_cardio_zone(self, state: dict) -> tuple:
        """Determine cardio zone and return (zone_name, zone_penalty_modifier)."""
        fatigue = state["fatigue_level"]
        stamina = state["stamina"]
        if stamina > 45:
            return ("aerobic", 1.0, 0.0)
        elif stamina > 20:
            anaerobic_pct = (45 - stamina) / 25.0
            accuracy_penalty = anaerobic_pct * 0.15  # Up to -15% at 20 stamina
            return ("anaerobic", 1.25, accuracy_penalty)
        else:
            oxygen_debt_pct = (20 - stamina) / 20.0
            accuracy_penalty = 0.15 + oxygen_debt_pct * 0.45  # 15-60% at 0 stamina
            return ("oxygen_debt", 1.50, accuracy_penalty)

    def _check_second_wind(self, state: dict, fighter_obj) -> bool:
        """Check if fighter gets a second wind surge."""
        if state.get("second_wind_used"):
            return False
        if state["fatigue_level"] < 0.85:
            return False
        heart = fighter_obj.get_effective_attribute("heart", state["fatigue_level"])
        chance = (heart / 200.0) * (1.0 - state["fatigue_level"])
        if random.random() < chance:
            recovery = 15 + int(heart * 0.05)
            state["stamina"] = min(100, state["stamina"] + recovery)
            state["fatigue_level"] = 1.0 - (state["stamina"] / 100)
            state["second_wind_used"] = True
            return True
        return False

    def _apply_stamina_cost(self, state, action_key: str, fatigue: float, cardio: int, stamina_mult: float = 1.0):
        base_cost = STAMINA_COST.get(action_key, 2)
        cardio_eff = cardio / 100.0

        # Zone-based stamina cost scaling
        zone, zone_mult, _ = self._get_cardio_zone(state)
        state["cardio_zone"] = zone

        # Base cost with cardio efficiency
        cost = base_cost * (1.20 - cardio_eff * 0.3)
        cost *= (1.0 + fatigue * 0.2)  # Fatigue scaling (reduced from 0.3)

        # Anaerobic zone: +25% cost
        if zone == "anaerobic":
            cost *= 1.25
        elif zone == "oxygen_debt":
            cost *= 1.50

        # Combo escalation
        combo_count = state.get("combo_count", 0)
        if combo_count > 3:
            cost *= (1.0 + (combo_count - 3) * 0.15)

        # Takedown/clinch burst actions cost more in oxygen debt
        if zone == "oxygen_debt" and action_key in ("takedown_attempt", "clinch_attempt", "stand_up", "sweep"):
            cost *= 1.3

        cost *= stamina_mult
        cost *= max(0.75, 1.0 - (cardio / 150.0))

        state["stamina"] = max(0, state["stamina"] - max(1, int(cost)))
        state["fatigue_level"] = 1.0 - (state["stamina"] / 100)

    def _strike_weight_modifier(self, weight_class: str) -> float:
        heavy_classes = ["Heavyweight", "Light Heavyweight"]
        light_classes = ["Flyweight", "Bantamweight", "Featherweight"]
        if weight_class in heavy_classes:
            return 1.25
        elif weight_class in light_classes:
            return 0.85
        return 1.0

    def _transition_fighter_state(self, fighter, state, new_state):
        """Manage state machine with commentary triggers."""
        machine = self.f1_machine if fighter == self.fighter1 else self.f2_machine
        old_state = machine.get_state()

        if new_state != old_state:
            machine.state = new_state
            state["state"] = new_state

            if new_state == "HURT":
                self.fight_log.append(f"{fighter.name} is hurt!")
            elif new_state == "ROCKED":
                self.fight_log.append(f"{fighter.name} is ROCKED!")
            elif new_state == "STUNNED":
                self.fight_log.append(f"{fighter.name} is STUNNED!")

    # ============================================================
    # TAKEDOWN SYSTEM (rebuilt with sprawl_technique, chain_wrestling, explosiveness)
    # ============================================================

    def _simulate_takedown(self, attacker, defender, fatigue, strategy):
        td_mod = self._get_mod("takedown_power", strategy)
        tda_mod = self._get_mod("takedown_accuracy", strategy)
        wd_mod = self._get_mod("wrestling_defense", strategy)
        cw_mod = self._get_mod("chain_wrestling", strategy)

        # New multi-stat takedown calculation
        att_state = self._get_attacker_state(attacker)
        def_state = self._get_opponent_state(attacker)

        # Attacker: power + accuracy + chain_wrestling + explosiveness
        td_power = attacker.get_effective_attribute("takedown_power", fatigue) * td_mod
        td_acc = attacker.get_effective_attribute("takedown_accuracy", fatigue) * tda_mod
        chain = attacker.get_effective_attribute("chain_wrestling", fatigue) * cw_mod
        explode = attacker.get_effective_attribute("explosiveness", fatigue)
        att_score = td_power * 0.35 + td_acc * 0.25 + chain * 0.25 + explode * 0.15

        # Defender: sprawl_technique + wrestling_defense + footwork_defense + athleticism
        sprawl = defender.get_effective_attribute("sprawl_technique", fatigue)
        wd = defender.get_effective_attribute("wrestling_defense", fatigue) * wd_mod
        footwork = defender.get_effective_attribute("footwork_defense", fatigue)
        ath = defender.get_effective_attribute("athleticism", fatigue)
        def_score = sprawl * 0.35 + wd * 0.25 + footwork * 0.20 + ath * 0.20

        # Weight class advantage
        weight_advantage = (attacker.base_weight_lbs - defender.base_weight_lbs) / 50.0
        weight_advantage = utils.clamp(weight_advantage, -0.3, 0.3)
        att_score *= (1.0 + weight_advantage)

        # Height mod: shorter = lower CoG = harder to takedown
        height_diff = attacker.height - defender.height
        height_mod = 1.0 - max(0, height_diff) * 0.003 if height_diff > 0 else 1.0 + min(0.15, abs(height_diff) * 0.002)
        att_score *= height_mod

        # Leg damage
        att_leg_mod = self._get_leg_takedown_penalty(att_state)
        def_leg_mod = self._get_leg_takedown_penalty(def_state)
        att_score *= att_leg_mod
        def_score *= def_leg_mod

        # Fatigue
        att_score *= max(0.3, 1.0 - fatigue * 0.4)
        def_score *= max(0.3, 1.0 - fatigue * 0.3)

        success_chance = utils.clamp(att_score - def_score * 0.5 + np.random.normal(0, 8), 5, 92)

        is_clinch = self.position_system.current_position == Position.CLINCH
        if is_clinch:
            # Clinch takedowns favor chain_wrestling more
            success_chance = utils.clamp(success_chance + chain * 0.10, 5, 92)
            success = utils.random_roll(1, 100) <= success_chance
            if success:
                self.position_system._set_ground(attacker, defender, Position.GROUND_GUARD)
        else:
            success = utils.random_roll(1, 100) <= success_chance
            if success:
                self.position_system._set_ground(attacker, defender, Position.GROUND_GUARD)

        att_state["takedowns_attempted"] = att_state.get("takedowns_attempted", 0) + 1
        self._apply_stamina_cost(
            att_state,
            "takedown_attempt", fatigue,
            attacker.get_effective_attribute("cardio", fatigue)
        )

        text = self.commentary.generate_takedown_commentary(attacker, defender, success)
        self.fight_log.append(text)

        if success:
            if attacker == self.fighter1:
                self.f1_control_time += 2
                self.f1_state["takedowns_landed"] += 1
                self.f1_state["effective_grappling_points"] += 3.0
            else:
                self.f2_control_time += 2
                self.f2_state["takedowns_landed"] += 1
                self.f2_state["effective_grappling_points"] += 3.0
            def_state["unanswered_ground_strikes"] = 0
        else:
            if random.random() < 0.2 + chain * 0.002:
                self.fight_log.append(f"{defender.name} stuffs it and looks for a guillotine!")

    def _simulate_clinch_attempt(self, attacker, defender, fatigue, strategy):
        cc_mod = self._get_mod("clinch_control", strategy)
        success = self.position_system.attempt_clinch(attacker, defender, fatigue, cc_mod=cc_mod)
        if success:
            text = self.commentary.generate_clinch_commentary(attacker, defender, "enter")
            self.fight_log.append(text)

    def _simulate_clinch_strike(self, attacker, defender, atk_state, def_state, fatigue, strategy):
        strike_type = random.choice(["knee", "elbow"])
        target = random.choice(["head", "body"])
        sp_mod = self._get_mod("striking_power", strategy)
        profile = STRIKE_PROFILES.get(strike_type, STRIKE_PROFILES["knee"])
        power = attacker.get_effective_attribute("striking_power", fatigue) * sp_mod
        durability = defender.get_effective_attribute("durability", 1.0 - (def_state["stamina"] / 100))
        composure = defender.get_effective_attribute("composure", fatigue)
        raw = profile["base_damage"] * (power / 50)
        raw *= (1.0 - min(0.35, (durability + composure) / 400))
        damage = max(1, int(raw))

        actual_damage = defender.apply_damage_to_zone(target, damage, self)
        def_state["accumulated_damage"] += actual_damage

        cardio = attacker.get_effective_attribute("cardio", fatigue)
        self._apply_stamina_cost(atk_state, strike_type, fatigue, cardio)
        atk_state["combo_count"] += 1

        text = self.commentary.generate_strike_commentary(attacker, defender, strike_type, target, Position.CLINCH)
        self.fight_log.append(text)

        if attacker == self.fighter1:
            self.f1_actions_landed += 1
            self.f1_state["significant_strikes_landed"] += 1
        else:
            self.f2_actions_landed += 1
            self.f2_state["significant_strikes_landed"] += 1

        head_pct = defender.get_group_health("head")
        if head_pct <= 15:
            self._check_knockdown(attacker, defender, atk_state, def_state, target, damage, fatigue, strike_type)

    # ============================================================
    # GROUND SYSTEM
    # ============================================================

    def _simulate_ground_action(self, fatigue, action_weights, strat):
        """Ground game with position-weighted control decisions."""
        pos = self.position_system.current_position
        top = self.position_system.top_fighter
        bottom = self.position_system.bottom_fighter
        if top == self.fighter1:
            top_state, bottom_state = self.f1_state, self.f2_state
            top_strategy = self.strategy1
            bottom_strategy = self.strategy2
        else:
            top_state, bottom_state = self.f2_state, self.f1_state
            top_strategy = self.strategy2
            bottom_strategy = self.strategy1

        pt = self.position_system.position_time

        # Strategy influences ground action choices
        strats = [top_strategy, bottom_strategy]
        top_mod = top_strategy.get_modifiers()
        bottom_mod = bottom_strategy.get_modifiers()

        # Weighted decision based on position dominance
        # Higher top_control = top fighter dictates more; higher bottom_control = bottom dictates more
        top_control = top.get_effective_attribute("top_control", fatigue)
        bottom_control = bottom.get_effective_attribute("bottom_control", fatigue)
        total_control = top_control + bottom_control
        base_top_weight = top_control / max(1, total_control) if total_control > 0 else 0.5

        # Position-specific base weights
        pos_weights = {
            Position.GROUND_GUARD: 0.60,
            Position.GROUND_HALF_GUARD: 0.55,
            Position.GROUND_SIDE: 0.70,
            Position.GROUND_NORTH_SOUTH: 0.70,
            Position.GROUND_MOUNT: 0.85,
            Position.GROUND_BACK: 0.20,
            Position.GROUND_TURTLE: 0.75,
            Position.GROUND_CRUCIFIX: 0.90,
            Position.GROUND_SCARF_HOLD: 0.80,
        }
        pos_weight = pos_weights.get(pos, 0.60)

        # Blend position weight with control-based weight
        top_chance = pos_weight * 0.7 + base_top_weight * 0.3
        top_chance = max(0.15, min(0.92, top_chance))

        if random.random() < top_chance:
            self._process_ground_top_action(top, bottom, top_state, bottom_state, fatigue, top_strategy, action_weights, pos, pt)
        else:
            self._process_ground_bottom_action(top, bottom, top_state, bottom_state, fatigue, bottom_strategy, pos, pt)

    def _process_ground_top_action(self, top, bottom, top_state, bottom_state, fatigue, strategy, action_weights, pos, pt):
        top_cardio = top.get_effective_attribute("cardio", fatigue)

        # === GUARD ===
        if pos == Position.GROUND_GUARD and pt > 4:
            if random.random() < 0.45:
                if self.position_system.pass_guard(top, bottom, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "pass_guard", fighter=top.name, opponent=bottom.name))
                    top_state["guard_passes"] += 1
                    top_state["effective_grappling_points"] += 4.0
                    self._apply_stamina_cost(top_state, "pass_guard", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return
            self._simulate_ground_strike(top, bottom, top_state, bottom_state, fatigue, strategy, pos)
            return

        # === HALF GUARD ===
        elif pos == Position.GROUND_HALF_GUARD and pt > 4:
            if random.random() < 0.35:
                if self.position_system.pass_half_guard(top, bottom, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "pass_guard", fighter=top.name, opponent=bottom.name))
                    top_state["guard_passes"] += 1
                    top_state["effective_grappling_points"] += 4.0
                    self._apply_stamina_cost(top_state, "pass_guard", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return
            # Kimura attempt from half guard
            if random.random() < 0.08:
                self._simulate_submission_attempt(top, bottom, fatigue, strategy, pos)
                return
            self._simulate_ground_strike(top, bottom, top_state, bottom_state, fatigue, strategy, pos)
            return

        # === SIDE CONTROL ===
        elif pos == Position.GROUND_SIDE:
            if pt > 3:
                if random.random() < 0.30 and self.position_system.side_to_north_south(top, bottom, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "pass_guard", fighter=top.name, opponent=bottom.name))
                    top_state["effective_grappling_points"] += 5.0
                    self._apply_stamina_cost(top_state, "advance_mount", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return
                elif random.random() < 0.10 and self.position_system.crucifix_from_side(top, bottom, fatigue):
                    self.fight_log.append(f"{top.name} isolates {bottom.name}'s arm and takes crucifix!")
                    top_state["effective_grappling_points"] += 6.0
                    self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return
                elif random.random() < 0.12 and self.position_system.take_back(top, bottom, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "back_take", fighter=top.name, opponent=bottom.name))
                    top_state["effective_grappling_points"] += 6.0
                    self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return

        # === NORTH-SOUTH ===
        elif pos == Position.GROUND_NORTH_SOUTH and pt > 3:
            if random.random() < 0.25 and self.position_system.north_south_to_mount(top, bottom, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "mount", fighter=top.name, opponent=bottom.name))
                top_state["effective_grappling_points"] += 5.0
                self._apply_stamina_cost(top_state, "advance_mount", fatigue, top_cardio)
                bottom_state["unanswered_ground_strikes"] = 0
                return
            elif random.random() < 0.10 and self.position_system.scarf_hold_from_north_south(top, bottom, fatigue):
                self.fight_log.append(f"{top.name} switches to scarf hold on {bottom.name}!")
                top_state["effective_grappling_points"] += 4.0
                self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                bottom_state["unanswered_ground_strikes"] = 0
                return

        # === MOUNT ===
        elif pos == Position.GROUND_MOUNT:
            if pt > 3 and random.random() < 0.15 and self.position_system.take_back(top, bottom, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "back_take", fighter=top.name, opponent=bottom.name))
                top_state["effective_grappling_points"] += 6.0
                self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                bottom_state["unanswered_ground_strikes"] = 0
                return

        # === TURTLE ===
        elif pos == Position.GROUND_TURTLE and pt > 2:
            if random.random() < 0.30 and self.position_system.take_back_from_turtle(top, bottom, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "back_take", fighter=top.name, opponent=bottom.name))
                top_state["effective_grappling_points"] += 6.0
                self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                bottom_state["unanswered_ground_strikes"] = 0
                return

        # === CRUCIFIX ===
        elif pos == Position.GROUND_CRUCIFIX:
            if random.random() < 0.20:
                self._simulate_submission_attempt(top, bottom, fatigue, strategy, pos)
                return

        # === SCARF HOLD ===
        elif pos == Position.GROUND_SCARF_HOLD and pt > 3:
            if random.random() < 0.12:
                self._simulate_submission_attempt(top, bottom, fatigue, strategy, pos)
                return

        # Submission attempt from top (fallback for all positions)
        sub_chance = {Position.GROUND_GUARD: 0.10, Position.GROUND_HALF_GUARD: 0.10,
                      Position.GROUND_SIDE: 0.18, Position.GROUND_NORTH_SOUTH: 0.15,
                      Position.GROUND_MOUNT: 0.22, Position.GROUND_BACK: 0.30,
                      Position.GROUND_TURTLE: 0.08, Position.GROUND_CRUCIFIX: 0.35,
                      Position.GROUND_SCARF_HOLD: 0.30}.get(pos, 0.10)
        if random.random() < sub_chance:
            self._simulate_submission_attempt(top, bottom, fatigue, strategy, pos)
        else:
            self._simulate_ground_strike(top, bottom, top_state, bottom_state, fatigue, strategy, pos)

    def _process_ground_bottom_action(self, top, bottom, top_state, bottom_state, fatigue, strategy, pos, pt):
        bottom_cardio = bottom.get_effective_attribute("cardio", fatigue)

        just_kd = bottom_state.get("knockdown", False)
        kd_penalty = 0.5 if just_kd else 1.0
        head_pct = bottom.get_group_health("head")
        health_penalty = 1.0 - max(0, (55 - head_pct) / 100) * 0.5 if head_pct < 55 else 1.0
        escape_mod = kd_penalty * health_penalty

        # === GUARD: submissions, sweeps, stand-ups ===
        if pos in (Position.GROUND_GUARD, Position.GROUND_HALF_GUARD) and pt > 3:
            sub_mod = 0.14 if pos == Position.GROUND_GUARD else 0.08
            if random.random() < sub_mod * escape_mod:
                self._simulate_submission_attempt(bottom, top, fatigue, strategy, pos)
                return

        pos_bonus = {
            Position.GROUND_GUARD: 1.0, Position.GROUND_HALF_GUARD: 0.8,
            Position.GROUND_SIDE: 0.7, Position.GROUND_NORTH_SOUTH: 0.5,
            Position.GROUND_MOUNT: 0.4, Position.GROUND_BACK: 0.2,
            Position.GROUND_TURTLE: 0.6, Position.GROUND_CRUCIFIX: 0.1,
            Position.GROUND_SCARF_HOLD: 0.2,
        }.get(pos, 0.5)
        sweep_chance = 0.28 * pos_bonus * escape_mod

        # === TURTLE: roll to guard instead of sweep ===
        if pos == Position.GROUND_TURTLE and pt > 2:
            if random.random() < 0.20 * escape_mod:
                if self.position_system.turtle_roll_to_guard(bottom, top, fatigue):
                    self.fight_log.append(f"{bottom.name} rolls through and gets guard!")
                    bottom_state["effective_grappling_points"] += 4.0
                    bottom_state["unanswered_ground_strikes"] = 0
                    self._apply_stamina_cost(bottom_state, "sweep", fatigue, bottom_cardio)
                    return
            elif random.random() < 0.15 * escape_mod:
                if self.position_system.stand_up_from_bottom(bottom, top, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "stand_up", fighter=bottom.name))
                    bottom_state["effective_grappling_points"] += 2.0
                    bottom_state["unanswered_ground_strikes"] = 0
                    self._apply_stamina_cost(bottom_state, "stand_up", fatigue, bottom_cardio)
                    return
            self.fight_log.append(f"{bottom.name} stays turtled, protecting themself.")
            return

        # === NORTH-SOUTH: granby roll ===
        if pos == Position.GROUND_NORTH_SOUTH and pt > 3:
            if random.random() < 0.10 * escape_mod:
                if self.position_system.granby_roll_to_guard(bottom, top, fatigue):
                    self.fight_log.append(f"{bottom.name} granby rolls back to guard!")
                    bottom_state["effective_grappling_points"] += 4.0
                    bottom_state["unanswered_ground_strikes"] = 0
                    self._apply_stamina_cost(bottom_state, "sweep", fatigue, bottom_cardio)
                    return
            elif random.random() < 0.12 * escape_mod:
                if self.position_system.stand_up_from_bottom(bottom, top, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "stand_up", fighter=bottom.name))
                    bottom_state["effective_grappling_points"] += 2.0
                    bottom_state["unanswered_ground_strikes"] = 0
                    self._apply_stamina_cost(bottom_state, "stand_up", fatigue, bottom_cardio)
                    return

        # === CRUCIFIX: escape to turtle (only option) ===
        if pos == Position.GROUND_CRUCIFIX and pt > 3:
            if random.random() < 0.08 * escape_mod:
                top_state = self.f1_state if top == self.fighter1 else self.f2_state
                # Set ground to turtle as bottom escapes partially
                self.position_system.current_position = Position.GROUND_TURTLE
                self.fight_log.append(f"{bottom.name} fights the hands and gets to turtle position!")
                self._apply_stamina_cost(bottom_state, "sweep", fatigue, bottom_cardio)
                return
            self.fight_log.append(f"{bottom.name} is trapped in the crucifix!")
            return

        # === SCARF HOLD: bridge and roll ===
        if pos == Position.GROUND_SCARF_HOLD and pt > 3:
            if random.random() < 0.10 * escape_mod:
                if self.position_system.sweep_from_bottom(bottom, top, fatigue):
                    self.fight_log.append(f"{bottom.name} bridges and reverses into top position!")
                    bottom_state["effective_grappling_points"] += 5.0
                    bottom_state["unanswered_ground_strikes"] = 0
                    self._apply_stamina_cost(bottom_state, "sweep", fatigue, bottom_cardio)
                    return
            self.fight_log.append(f"{bottom.name} is stuck in scarf hold, trying to survive.")

        # === SWEEP ATTEMPTS (guard, half-guard, side, mount, back) ===
        if random.random() < sweep_chance:
            if self.position_system.sweep_from_bottom(bottom, top, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "sweep", bottom=bottom.name, top=top.name))
                bottom_state["effective_grappling_points"] += 5.0
                bottom_state["unanswered_ground_strikes"] = 0
                self._apply_stamina_cost(bottom_state, "sweep", fatigue, bottom_cardio)
            else:
                self.fight_log.append(f"{bottom.name} tries to sweep but {top.name} defends.")
        else:
            stand_chance = 0.22 * escape_mod * pos_bonus
            if random.random() < stand_chance:
                if self.position_system.stand_up_from_bottom(bottom, top, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "stand_up", fighter=bottom.name))
                    bottom_state["effective_grappling_points"] += 2.0
                    bottom_state["unanswered_ground_strikes"] = 0
                    self._apply_stamina_cost(bottom_state, "stand_up", fatigue, bottom_cardio)
                else:
                    self.fight_log.append(f"{bottom.name} tries to stand but {top.name} keeps them down.")
            else:
                self.fight_log.append(f"{bottom.name} covers up on the ground, trying to survive.")

    def _simulate_ground_strike(self, attacker, defender, atk_state, def_state, fatigue, strategy, pos=Position.GROUND_GUARD):
        strike_type = random.choice(["hammerfist", "elbow", "punch"])
        target = random.choice(["head", "body"])
        sp_mod = self._get_mod("striking_power", strategy)
        power = attacker.get_effective_attribute("striking_power", fatigue) * sp_mod
        gsd = defender.get_effective_attribute("ground_striking_defense", 1.0 - (def_state["stamina"] / 100))
        durability = defender.get_effective_attribute("durability", 1.0 - (def_state["stamina"] / 100))
        blocking = defender.get_effective_attribute("blocking", 1.0 - (def_state["stamina"] / 100))

        pos_power = {Position.GROUND_GUARD: 0.30, Position.GROUND_HALF_GUARD: 0.35,
                     Position.GROUND_SIDE: 0.45, Position.GROUND_NORTH_SOUTH: 0.50,
                     Position.GROUND_MOUNT: 0.60, Position.GROUND_BACK: 0.35,
                     Position.GROUND_TURTLE: 0.40, Position.GROUND_CRUCIFIX: 0.50,
                     Position.GROUND_SCARF_HOLD: 0.50}
        pos_bonus = pos_power.get(pos, 0.3)

        tc_mod = self._get_mod("top_control", strategy)
        top_bonus = 1.0 + (tc_mod - 1.0) * 0.6

        ground_strike_bonus = strategy.get_modifiers().get("ground_strike_damage", 1.0)

        raw = (power / 50) * 5 * pos_bonus * top_bonus * ground_strike_bonus
        raw *= max(0.85, 1.0 - gsd / 500.0)  # gsd provides small flat reduction
        damage = max(1, int(raw * (1 - durability / 200)))

        actual_damage = defender.apply_damage_to_zone(target, damage, self)
        def_state["accumulated_damage"] += actual_damage

        def_state["unanswered_ground_strikes"] = def_state.get("unanswered_ground_strikes", 0) + 1

        text = self.commentary.generate_strike_commentary(attacker, defender, strike_type, target, pos)
        self.fight_log.append(text)

        if attacker == self.fighter1:
            self.f1_actions_landed += 1
            self.f1_state["significant_strikes_landed"] += 1
            self.f1_state["effective_grappling_points"] += 0.5
        else:
            self.f2_actions_landed += 1
            self.f2_state["significant_strikes_landed"] += 1
            self.f2_state["effective_grappling_points"] += 0.5

        self._apply_stamina_cost(atk_state, "ground_strike", fatigue,
                                  attacker.get_effective_attribute("cardio", fatigue))

        unanswered = def_state.get("unanswered_ground_strikes", 0)
        just_kd = def_state.get("knockdown", False)

        if just_kd:
            side_tko = 14
            mount_tko = 10
            warning_map = {5: "close_mount", 8: "mount"}
        else:
            side_tko = 22
            mount_tko = 14
            warning_map = {8: "watching", 12: "mount", 15: "survival"}

        # TKO buildup warnings
        if not self.winner:
            if unanswered in warning_map:
                wtype = warning_map[unanswered]
                if wtype == "watching":
                    self.fight_log.append(f"The referee is watching {defender.name} closely — not defending intelligently!")
                elif wtype == "mount" and not just_kd:
                    self.fight_log.append(f"{defender.name} is covering up but taking heavy punishment! Ref might step in!")
                elif wtype == "survival":
                    self.fight_log.append(f"These ground strikes are adding up! {defender.name} is in survival mode!")
                elif wtype == "close_mount":
                    self.fight_log.append(f"{attacker.name} is relentless! {defender.name} needs to escape or this is over!")

        dominant_positions = (Position.GROUND_SIDE, Position.GROUND_NORTH_SOUTH,
                              Position.GROUND_MOUNT, Position.GROUND_CRUCIFIX, Position.GROUND_SCARF_HOLD)
        if unanswered >= mount_tko and pos == Position.GROUND_MOUNT:
            self.winner = attacker
            self.loser = defender
            self.win_method = "TKO (Ground Strikes)"
            self.win_round = self.current_round
            self.fight_log.append(f"The referee steps in! {defender.name} is taking too much damage from mount!")
            return
        elif unanswered >= side_tko and pos in dominant_positions:
            self.winner = attacker
            self.loser = defender
            self.win_method = "TKO (Ground Strikes)"
            self.win_round = self.current_round
            self.fight_log.append(f"The referee steps in! {defender.name} can't defend themselves!")
            return

        if defender.get_group_health("head") <= 5:
            self.winner = attacker
            self.loser = defender
            self.win_method = "TKO (Ground Strikes)"
            self.win_round = self.current_round
            self.fight_log.append(f"{defender.name} goes limp on the ground!")

    # ============================================================
    # SUBMISSION SYSTEM
    # ============================================================

    def _get_available_subs(self, pos, attacker_is_top=True) -> list:
        guard_subs_top = ["kimura", "d'arce choke", "americana", "arm triangle", "gogoplata"]
        guard_subs_bottom = ["triangle choke", "armbar", "guillotine", "omoplata", "kimura"]
        half_guard_subs_top = ["kimura", "arm triangle", "d'arce choke", "brabo choke"]
        half_guard_subs_bottom = ["kimura", "sweep to top", "guillotine", "armbar"]
        side_subs = ["kimura", "d'arce choke", "armbar", "arm triangle", "americana"]
        north_south_subs = ["north-south choke", "kimura", "arm triangle"]
        mount_subs = ["armbar", "mounted triangle", "americana", "arm triangle"]
        back_subs = ["rear naked choke", "armbar"]
        crucifix_subs = ["armbar", "triangle choke"]
        scarf_hold_subs = ["americana", "kimura"]

        if pos == Position.GROUND_GUARD:
            return guard_subs_top if attacker_is_top else guard_subs_bottom
        elif pos == Position.GROUND_HALF_GUARD:
            return half_guard_subs_top if attacker_is_top else half_guard_subs_bottom
        elif pos == Position.GROUND_SIDE:
            return side_subs
        elif pos == Position.GROUND_NORTH_SOUTH:
            return north_south_subs
        elif pos == Position.GROUND_MOUNT:
            return mount_subs
        elif pos == Position.GROUND_BACK:
            return back_subs
        elif pos == Position.GROUND_CRUCIFIX:
            return crucifix_subs
        elif pos == Position.GROUND_SCARF_HOLD:
            return scarf_hold_subs
        return ["armbar", "kimura"]

    def _simulate_submission_attempt(self, attacker, defender, fatigue, strategy, pos=Position.GROUND_GUARD):
        if self.current_round < 2 and random.random() < 0.90:
            return
        top = self.position_system.top_fighter
        attacker_is_top = (attacker == top)
        available = self._get_available_subs(pos, attacker_is_top)
        submission = random.choice(available)

        so_mod = self._get_mod("submission_offense", strategy)
        sd_mod = self._get_mod("submission_defense", strategy)

        sub_off = attacker.get_effective_attribute("submission_offense", fatigue) * so_mod
        sub_def = defender.get_effective_attribute("submission_defense", fatigue) * sd_mod
        mental = defender.get_effective_attribute("mental_toughness", fatigue)
        cardio = defender.get_effective_attribute("cardio", fatigue)
        att_flex = attacker.get_effective_attribute("flexibility", fatigue)
        def_flex = defender.get_effective_attribute("flexibility", fatigue)
        sub_aware = defender.get_effective_attribute("submission_awareness", fatigue)

        self.fight_log.append(self.commentary.generate_ground_commentary(
            "submission_attempt", attacker=attacker.name, submission=submission))

        # Positional advantage multiplier
        pos_bonus = {Position.GROUND_GUARD: 1.0, Position.GROUND_HALF_GUARD: 0.9,
                     Position.GROUND_SIDE: 1.2, Position.GROUND_NORTH_SOUTH: 1.3,
                     Position.GROUND_MOUNT: 1.4, Position.GROUND_BACK: 1.7,
                     Position.GROUND_CRUCIFIX: 1.8, Position.GROUND_SCARF_HOLD: 1.5}
        pb = pos_bonus.get(pos, 1.0)

        # Weight class modifier for submissions: heavier = less flexible = harder to sub
        weight_class = attacker.weight_class
        sub_weight_mod = 1.0
        if weight_class in ("Heavyweight",):
            sub_weight_mod = 0.85
        elif weight_class in ("Light Heavyweight",):
            sub_weight_mod = 0.92
        elif weight_class in ("Flyweight", "Bantamweight"):
            sub_weight_mod = 1.15

        # Get correct defensive state
        if attacker == self.fighter1:
            def_state = self.f2_state
        else:
            def_state = self.f1_state

        threat_key = submission
        current_threat = def_state.get("submission_threat", {}).get(threat_key, 0)

        base_threat = (sub_off * 0.120 + att_flex * 0.030 - sub_def * 0.020) * pb
        mental_resistance = mental / 250.0
        cardio_resistance = cardio / 200.0
        aware_resistance = sub_aware / 300.0
        def_flex_resistance = def_flex / 400.0
        threat_increment = base_threat * (1.0 - mental_resistance * 0.25) * (1.0 - cardio_resistance * 0.15) * (1.0 - aware_resistance * 0.20) * (1.0 - def_flex_resistance * 0.15) * sub_weight_mod
        threat_increment += random.uniform(-2, 5)

        # Previous threats decay slower (0.6x instead of 0.7x)
        new_threat = current_threat * 0.6 + max(0, threat_increment)

        if threat_key not in def_state["submission_threat"]:
            def_state["submission_threat"][threat_key] = 0
        def_state["submission_threat"][threat_key] = new_threat

        # Track submission attempts
        if attacker == self.fighter1:
            self.f1_state["submissions_attempted"] += 1
        else:
            self.f2_state["submissions_attempted"] += 1
        self.fight_log.append(f"{attacker.name} hunting for the {submission}!")

        # Defense calculation (new: includes submission_awareness and flexibility)
        mental_factor = mental / 200.0
        cardio_factor = cardio / 200.0
        sub_def_factor = sub_def / 150.0
        aware_factor = sub_aware / 200.0
        flex_factor = def_flex / 300.0
        defense_factor = 0.30 + mental_factor + cardio_factor * 0.30 + sub_def_factor * 0.20 + aware_factor * 0.15 + flex_factor * 0.10

        # Damage-based urgency: lower health = harder to defend
        defender_health = (defender.get_group_health("head") + defender.get_group_health("body")) / 200.0
        health_urgency = max(0.5, 1.0 + (1.0 - defender_health) * 0.5)

        success_chance = max(5, min(65, (new_threat * 1.9 - sub_def * defense_factor * 0.065) * pb * health_urgency))

        if random.random() * 100 <= success_chance:
            self.fight_log.append(self.commentary.generate_ground_commentary(
                "submission_tap", attacker=attacker.name, defender=defender.name, submission=submission))
            self.winner = attacker
            self.loser = defender
            self.win_method = f"Submission ({submission})"
            self.win_round = self.current_round
        else:
            self.fight_log.append(self.commentary.generate_ground_commentary(
                "submission_defend", attacker=attacker.name, defender=defender.name, submission=submission))
            if random.random() < 0.3 and not self.winner:
                def_state["submission_threat"][threat_key] = new_threat * 0.5
                self.fight_log.append(f"{defender.name} fights hands and survives!")

        # Grappling points for attempt
        grapple_pts = 1.5
        if attacker == self.fighter1:
            self.f1_state["effective_grappling_points"] += grapple_pts
        else:
            self.f2_state["effective_grappling_points"] += grapple_pts

    def _round_end_effects(self, round_num: int):
        """Apply end-of-round effects: stamina recovery, injury checks, cut progression, breathing."""
        is_title_round = round_num >= 4 and self.is_title_fight

        for idx, (state, fighter) in enumerate([(self.f1_state, self.fighter1), (self.f2_state, self.fighter2)]):
            # Stamina recovery between rounds — affected by breathing + cardio
            breathing_cap = state.get("breathing_capacity", 100)
            breathing_mod = get_breathing_recovery_modifier(breathing_cap)
            title_penalty = 0.33 if is_title_round else 1.0

            # Scale recovery by cardio attribute
            cardio_attr = fighter.get_effective_attribute("cardio", 0)
            cardio_recovery_mod = 0.5 + (cardio_attr / 100.0)  # 0.5 at 0 cardio, 1.5 at 100
            stamina_recovery = (15 + (100 - state.get("stamina", 100)) * 0.12) * breathing_mod * title_penalty * cardio_recovery_mod
            state["stamina"] = min(100, state["stamina"] + stamina_recovery)
            state["fatigue_level"] = 1.0 - (state["stamina"] / 100)

            # Breathing recovery between rounds
            breathing_recovery = BREATHING_RECOVERY_BETWEEN_ROUNDS
            if is_title_round and breathing_cap < 30:
                breathing_recovery = 5  # very little recovery in deep title rounds
            elif is_title_round:
                breathing_recovery = 10
            state["breathing_capacity"] = min(100, breathing_cap + breathing_recovery)

            # Leg damage recovery (10% per round, corner work adds 15%)
            state["lead_leg_damage"] = max(0, state.get("lead_leg_damage", 0) - 10)
            state["rear_leg_damage"] = max(0, state.get("rear_leg_damage", 0) - 10)
            state["leg_damage"] = (state.get("lead_leg_damage", 0) + state.get("rear_leg_damage", 0)) / 2

            # Reduce stun/hurt timers
            state["stunned_timer"] = max(0, state["stunned_timer"] - 2)
            if state["stunned_timer"] == 0:
                state["stunned"] = False

            # Reset knockdown flag from previous round
            state["knockdown"] = False
            state["knockdown_count"] = 0

            # Reduce swelling slightly (cut man between rounds)
            state["swelling"] = max(0, state["swelling"] - 5)

            # Cut progression: cuts worsen if not managed between rounds
            for cut in state.get("cuts", []):
                if random.random() < 0.2:
                    cut["severity"] = min(1.0, cut["severity"] * 1.3)

            # Head damage recovery between rounds (corner work)
            head_damage = self.f1_head_damage if idx == 0 else self.f2_head_damage
            head_recovery = head_damage * 0.20
            if is_title_round and round_num >= 4:
                head_recovery *= 0.5
            if idx == 0:
                self.f1_head_damage = max(0, self.f1_head_damage - head_recovery)
            else:
                self.f2_head_damage = max(0, self.f2_head_damage - head_recovery)

            # Reset combo tracking
            state["combo_count"] = 0
            state["feint_count"] = 0
            state["unanswered_ground_strikes"] = 0
            state["pattern_read"] = False
            state["pattern_read_bonus"] = 1.0

            # Conditionally clear hurt flag if health has recovered
            head_pct = fighter.get_group_health("head")
            body_pct = fighter.get_group_health("body")
            if head_pct >= 55 and body_pct >= 45:
                state["hurt"] = False
                self._transition_fighter_state(fighter, state, "NORMAL")
            elif not state.get("stunned", False):
                if state.get("state") == "STUNNED":
                    self._transition_fighter_state(fighter, state, "HURT")

    # ============================================================
    # STRIKE CHECKS
    # ============================================================

    def _check_stun(self, attacker, defender, atk_state, def_state, damage, target, fatigue):
        """Simplified stun — based on head damage accumulation."""
        if target != "head" and target not in ("jaw", "temple"):
            return False

        # Jaw/temple hits are stun-prone
        stun_threshold = 40 if target in ("jaw", "temple") else 55

        mental = defender.get_effective_attribute("mental_toughness", fatigue)
        durability = defender.get_effective_attribute("durability", fatigue)
        stun_chance = max(0, (damage * 0.8 - durability * 0.12 - mental * 0.08) * 1.2)

        if stun_chance > 6 and utils.random_roll(1, 100) <= int(stun_chance):
            def_state["stunned"] = True
            def_state["stunned_timer"] = random.randint(2, 4)
            self._transition_fighter_state(defender, def_state, "STUNNED")
            self.fight_log.append(f"{defender.name} is stunned by that shot!")
            return True
        return False

    def _check_knockdown(self, attacker, defender, atk_state, def_state, target, damage, fatigue, strike_type):
        jaw_health = defender.get_zone_health("jaw")
        temple_health = defender.get_zone_health("temple")
        overall_head = defender.get_group_health("head")
        ko_stage = def_state.get("ko_stage", 0)

        # Determine if knockdown happens
        knockdown = False
        if jaw_health <= 5 or temple_health <= 5:
            knockdown = True
        elif overall_head <= 15:
            knockdown = True
        elif ko_stage >= 3 and self._last_severity in ("Flush", "Devastating"):
            knockdown = True
        elif ko_stage >= 2 and self._last_severity == "Devastating":
            knockdown = random.random() < 0.5

        if not knockdown:
            return False

        attacker_num = 1 if attacker == self.fighter1 else 2
        self._update_momentum(attacker_num, 15)
        self._update_momentum(3 - attacker_num, -15)
        self._update_crowd_excitement(15)

        def_state["knockdown_count"] += 1
        if attacker == self.fighter1:
            self.f1_knockdowns_this_round += 1
        else:
            self.f2_knockdowns_this_round += 1
        def_state["knockdown"] = True
        def_state["stunned"] = False
        def_state["stunned_timer"] = 0
        def_state["unanswered_ground_strikes"] = 0

        self.fight_log.append(f"!!! {self.commentary.generate_knockdown_commentary(defender)}")

        # Check if this is an instant KO (head critical damage or stage 4)
        if ko_stage >= 4 or overall_head <= 4 or (ko_stage >= 3 and overall_head <= 15):
            self.winner = attacker
            self.loser = defender
            self.win_method = "KO"
            self.win_round = self.current_round
            self.fight_log.append(f"{defender.name} is out cold!")
            return True

        # Decide whether to chase to the ground or let them back up
        atk_agg = attacker.get_effective_attribute("aggression", atk_state["fatigue_level"])
        atk_fiq = attacker.get_effective_attribute("fight_iq", atk_state["fatigue_level"])
        finish_chance = min(0.65, 0.40 + (atk_agg / 300.0) + (atk_fiq / 400.0))

        if random.random() < finish_chance:
            self.fight_log.append(f"{defender.name} goes down! {attacker.name} swarms, looking for the finish!")
            self.position_system._set_ground(attacker, defender, Position.GROUND_GUARD)
        else:
            self.fight_log.append(f"{defender.name} is down! {attacker.name} lets them back up — wants to keep it standing!")
            def_state["knockdown"] = False  # Ground game doesn't get fast TKO

        return True

    # ============================================================
    # ROUND SCORING
    # ============================================================

    def _score_round(self, round_num: int):
        """10-point Must System — scored after each round."""
        rd = self._gather_round_data()

        for judge in self.judges:
            f1_score, f2_score = judge.score_round(rd)

        r_idx = len(self.judges[0].scores) - 1
        self.f1_round_scores.append([j.scores[r_idx][0] for j in self.judges])
        self.f2_round_scores.append([j.scores[r_idx][1] for j in self.judges])

        f1_avg = sum(j.scores[-1][0] for j in self.judges) / 3.0
        f2_avg = sum(j.scores[-1][1] for j in self.judges) / 3.0
        score_text = f"{int(f1_avg)}-{int(f2_avg)}"

        # Enhanced scoring commentary
        f1_damage = self._calc_effective_striking(self.fighter1, self.f1_state)
        f2_damage = self._calc_effective_striking(self.fighter2, self.f2_state)
        f1_grapple = self._calc_effective_grappling(self.fighter1, self.f1_state)
        f2_grapple = self._calc_effective_grappling(self.fighter2, self.f2_state)
        f1_kd = self.f1_knockdowns_this_round
        f2_kd = self.f2_knockdowns_this_round

        deciding_factor = None
        if f1_kd != f2_kd:
            decider = self.fighter1 if f1_kd > f2_kd else self.fighter2
            deciding_factor = f"{decider.name}'s knockdown was the difference"
        elif abs(f1_damage - f2_damage) > 15:
            decider = self.fighter1 if f1_damage > f2_damage else self.fighter2
            deciding_factor = f"Effective striking by {decider.name}"
        elif abs(f1_grapple - f2_grapple) > 3:
            decider = self.fighter1 if f1_grapple > f2_grapple else self.fighter2
            deciding_factor = f"{decider.name}'s ground control"

        if not deciding_factor:
            f1_strikes = self.f1_state.get("significant_strikes_landed", 0)
            f2_strikes = self.f2_state.get("significant_strikes_landed", 0)
            if f1_strikes != f2_strikes:
                decider = self.fighter1 if f1_strikes > f2_strikes else self.fighter2
                deciding_factor = f"{decider.name} out-landed their opponent"

        if deciding_factor:
            self.fight_log.append(f"Round {round_num}: {deciding_factor}")
        self.fight_log.append(f"Score: {score_text}")

    def _gather_round_data(self) -> dict:
        """Gather data for round scoring based on 10-point must system criteria."""
        return {
            "effective_striking_f1": self._calc_effective_striking(self.fighter1, self.f1_state),
            "effective_striking_f2": self._calc_effective_striking(self.fighter2, self.f2_state),
            "effective_grappling_f1": self._calc_effective_grappling(self.fighter1, self.f1_state),
            "effective_grappling_f2": self._calc_effective_grappling(self.fighter2, self.f2_state),
            "aggression_f1": self._calc_aggression(self.f1_state),
            "aggression_f2": self._calc_aggression(self.f2_state),
            "octagon_control_f1": self._calc_octagon_control(self.f1_state),
            "octagon_control_f2": self._calc_octagon_control(self.f2_state),
            "knockdowns_f1": self.f1_knockdowns_this_round,
            "knockdowns_f2": self.f2_knockdowns_this_round,
            "f1_sig_strikes": self.f1_state.get("significant_strikes_landed", 0),
            "f2_sig_strikes": self.f2_state.get("significant_strikes_landed", 0),
            "f1_grapple": self.f1_state.get("effective_grappling_points", 0.0),
            "f2_grapple": self.f2_state.get("effective_grappling_points", 0.0),
        }

    def _calc_effective_striking(self, fighter, state) -> float:
        """Effective striking = significant strikes landed * damage + accuracy."""
        sig_strikes = state.get("significant_strikes_landed", 0)
        damage = sum(state.get("rounds_damage_dealt", []))
        accuracy_bonus = sig_strikes * 0.3
        return sig_strikes * 2.0 + damage * 0.5 + accuracy_bonus

    def _calc_effective_grappling(self, fighter, state) -> float:
        """Effective grappling = takedowns + ground control time + guard passes."""
        tds = state.get("takedowns_landed", 0) * 3.0
        control = state.get("effective_grappling_points", 0.0)
        guard_passes = state.get("guard_passes", 0) * 2.0
        return tds + control * 0.5 + guard_passes

    def _calc_aggression(self, state) -> float:
        """Aggression = forward pressure points + action volume."""
        return state.get("forward_pressure_points", 0) * 2.0 + state.get("significant_strikes_landed", 0) * 0.5

    def _calc_octagon_control(self, state) -> float:
        """Octagon control = dictating where the fight takes place."""
        cage_work = max(0, 5 - state.get("unanswered_ground_strikes", 0))
        pressure = state.get("forward_pressure_points", 0)
        return cage_work * 2.0 + pressure * 0.5

    # ============================================================
    # AI MID-ROUND ADAPTATION
    # ============================================================

    def _check_ai_mid_round(self):
        """More frequent AI adaptation during rounds — uses strategy drift."""
        if not self.judges[0].scores:
            return
        round_diffs = [int(sum(j.scores[r][1] - j.scores[r][0] for j in self.judges) / 3.0)
                       for r in range(len(self.judges[0].scores))]

        new_strat = StrategySystem.pick_ai_strategy(
            self.fighter2, self.fighter1,
            round_diffs, self.current_round, self.rounds, self.strategy2.current_strategy)

        # Use drift instead of instant switch (Phase 3A)
        fight_iq = self.fighter2.get_effective_attribute("fight_iq", self.f2_state["fatigue_level"])
        adaptability = self.fighter2.get_effective_attribute("adaptability", self.f2_state["fatigue_level"])
        switched = self.strategy2.drift_toward_strategy(new_strat, fight_iq, adaptability)

        if switched:
            self.fight_log.append(f"{self.fighter2.name} is adjusting their approach!")
        self.strategy1.set_opponent_strategy(self.strategy2.current_strategy)

    def _calculate_ring_generalship(self, fighter: Fighter) -> float:
        """Compute ring generalship from athleticism, hand_speed, and fight_iq."""
        ath = fighter.get_effective_attribute("athleticism", 0)
        speed = fighter.get_effective_attribute("hand_speed", 0)
        iq = fighter.get_effective_attribute("fight_iq", 0)
        return (ath * 0.35 + speed * 0.25 + iq * 0.40) / 100.0

    def _check_ring_generalship(self):
        """Evaluate ring control and apply pressure/cage effects."""
        # Calculate ring generalship for both fighters
        f1_rg = self._calculate_ring_generalship(self.fighter1)
        f2_rg = self._calculate_ring_generalship(self.fighter2)
        rg_diff = f1_rg - f2_rg

        # Higher ring generalship fighter controls distance
        if abs(rg_diff) > 0.05 and random.random() < abs(rg_diff) * 0.5:
            controller = self.fighter1 if rg_diff > 0 else self.fighter2
            controlled = self.fighter2 if rg_diff > 0 else self.fighter1
            c_state = self.f1_state if rg_diff > 0 else self.f2_state

            # If at distance, push toward cage
            if self.position_system.current_position in (Position.DISTANCE, Position.POCKET):
                c_state["forward_pressure_points"] = c_state.get("forward_pressure_points", 0) + 1
                if random.random() < 0.3:
                    self.position_system.set_cage_position(controlled)
                    self.fight_log.append(f"{controller.name} pressures {controlled.name} against the cage!")

        # Backing up penalty: if a fighter has been retreating without countering
        for state, fighter, opponent in [
            (self.f1_state, self.fighter1, self.fighter2),
            (self.f2_state, self.fighter2, self.fighter1),
        ]:
            retreats = state.get("consecutive_retreats", 0)
            if retreats >= 3:
                state["forward_pressure_points"] = max(0, state.get("forward_pressure_points", 0) - 2)
                state["consecutive_retreats"] = 0
                if random.random() < 0.3:
                    self.fight_log.append(f"{fighter.name} needs to stop backing up!")

    def _check_ai_adaptation(self, round_num: int):
        """Between-round AI adaptation — uses strategy drift."""
        # Build score differential from judge scores
        round_diffs = []
        if self.judges[0].scores:
            round_diffs = [int(sum(j.scores[r][1] - j.scores[r][0] for j in self.judges) / 3.0)
                           for r in range(len(self.judges[0].scores))]

        new_strat = StrategySystem.pick_ai_strategy(
            self.fighter2, self.fighter1,
            round_diffs, self.current_round, self.rounds, self.strategy2.current_strategy)

        fight_iq = self.fighter2.get_effective_attribute("fight_iq", self.f2_state["fatigue_level"])
        adaptability = self.fighter2.get_effective_attribute("adaptability", self.f2_state["fatigue_level"])
        switched = self.strategy2.drift_toward_strategy(new_strat, fight_iq, adaptability)

        if switched:
            self.fight_log.append(f"{self.fighter2.name} is making adjustments between rounds!")
        self.strategy1.set_opponent_strategy(self.strategy2.current_strategy)

        # Pattern detection
        if self.f1_state.get("combo_count", 0) > 5:
            self.fight_log.append(f"{self.fighter2.name} starts reading the patterns!")

    def _check_pattern_recognition(self):
        """Analyze opponent action history for repeated patterns."""
        for fighter, opponent, state, opp_state in [
            (self.fighter1, self.fighter2, self.f1_state, self.f2_state),
            (self.fighter2, self.fighter1, self.f2_state, self.f1_state),
        ]:
            history = opp_state.get("opponent_action_history", [])
            if len(history) < 6:
                continue
            fight_iq = fighter.get_effective_attribute("fight_iq", state["fatigue_level"])
            if fight_iq < 50:
                continue
            recog_score = fight_iq * 0.6

            # Check for repeated strategy patterns
            strat_entries = [h.split("_")[1] if "_" in h else h for h in history[-10:]]
            from collections import Counter
            pattern_counts = Counter(strat_entries)
            most_common, count = pattern_counts.most_common(1)[0]

            if count >= 4 and random.random() < recog_score / 100.0:
                state["pattern_read"] = True
                if random.random() < 0.5:
                    self.fight_log.append(f"{fighter.name} reads {opponent.name}'s pattern!")
                # Bonus: next defensive action gets +10% effectiveness
                state["pattern_read_bonus"] = 1.10

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _describe_round(self, round_num: int) -> str:
        if self.winner:
            return f"{self.winner.name} ends it!"
        f1_total = sum(j.scores[-1][0] for j in self.judges) if self.judges[0].scores else 10
        f2_total = sum(j.scores[-1][1] for j in self.judges) if self.judges[0].scores else 10
        if f1_total > f2_total:
            return f"{self.fighter1.name} takes the round"
        elif f2_total > f1_total:
            return f"{self.fighter2.name} takes the round"
        return "close round"

    def _get_decision_details(self) -> str:
        f1_total = sum(sum(j.scores[r][0] for j in self.judges) for r in range(len(self.judges[0].scores)))
        f2_total = sum(sum(j.scores[r][1] for j in self.judges) for r in range(len(self.judges[0].scores)))
        return f"Final Scorecards: {self.fighter1.name} {f1_total:.0f} - {self.fighter2.name} {f2_total:.0f}"

    def _get_total_score_for(self, fighter_num: int) -> int:
        """Get cumulative total score for a fighter across all scored rounds."""
        if not self.judges[0].scores:
            return 0
        total = 0
        for r in range(len(self.judges[0].scores)):
            for j in self.judges:
                if fighter_num == 1:
                    total += j.scores[r][0]
                else:
                    total += j.scores[r][1]
        return total

    def _determine_decision(self):
        """Score the fight from all judges and determine the winner."""
        f1_wins = 0
        f2_wins = 0
        draws = 0
        for j in self.judges:
            f1_total = sum(s[0] for s in j.scores)
            f2_total = sum(s[1] for s in j.scores)
            if f1_total > f2_total:
                f1_wins += 1
            elif f2_total > f1_total:
                f2_wins += 1
            else:
                draws += 1

        if f1_wins > f2_wins:
            self.winner = self.fighter1
            self.loser = self.fighter2
            if draws > 0:
                self.win_method = "Majority Decision"
            elif f2_wins == 0:
                self.win_method = "Unanimous Decision"
            else:
                self.win_method = "Split Decision"
        elif f2_wins > f1_wins:
            self.winner = self.fighter2
            self.loser = self.fighter1
            if draws > 0:
                self.win_method = "Majority Decision"
            elif f1_wins == 0:
                self.win_method = "Unanimous Decision"
            else:
                self.win_method = "Split Decision"
        else:
            self.winner = None
            self.loser = None
            if draws == 3:
                self.win_method = "Unanimous Draw"
            elif draws >= 2:
                self.win_method = "Majority Draw"
            else:
                self.win_method = "Split Draw"

    def _get_total_scores(self) -> dict:
        """Return cumulative scores for the decision."""
        f1_total = self._get_total_score_for(1)
        f2_total = self._get_total_score_for(2)
        return {self.fighter1.name: f1_total, self.fighter2.name: f2_total}

    def _get_fight_details(self) -> dict:
        def stats_for(state, fighter):
            return {
                "sig_strikes": state.get("significant_strikes_landed", 0),
                "strikes_thrown": state.get("strikes_thrown", 0),
                "takedowns": state.get("takedowns_landed", 0),
                "takedowns_attempted": state.get("takedowns_attempted", 0),
                "submissions": state.get("submissions_attempted", 0),
                "knockdowns": state.get("knockdown_count", 0),
                "guard_passes": state.get("guard_passes", 0),
            }
        return {
            "f1": stats_for(self.f1_state, self.fighter1),
            "f2": stats_for(self.f2_state, self.fighter2),
        }

    def _get_display_health(self, fighter: Fighter) -> dict:
        """Format health display for the frontend."""
        f_state = self.f1_state if fighter == self.fighter1 else self.f2_state
        breathing_cap = f_state.get("breathing_capacity", 100)
        breathing_lvl = get_breathing_level(breathing_cap)
        leg_damage = (f_state.get("lead_leg_damage", 0) + f_state.get("rear_leg_damage", 0)) / 2
        return {
            "head": round(fighter.get_group_health("head"), 1),
            "body": round(fighter.get_group_health("body"), 1),
            "legs": round(fighter.get_group_health("legs"), 1),
            "overall": round(fighter.get_overall_health_pct(), 1),
            "stamina": round(f_state.get("stamina", 100), 1),
            "blood": round(fighter._blood_level, 1),
            "breathing": round(breathing_cap, 1),
            "breathing_level": breathing_lvl,
            "lead_leg_damage": round(f_state.get("lead_leg_damage", 0), 1),
            "rear_leg_damage": round(f_state.get("rear_leg_damage", 0), 1),
            "leg_damage": round(leg_damage, 1),
            "cardio_zone": f_state.get("cardio_zone", "aerobic"),
        }

    def _get_attacker_state(self, fighter):
        return self.f1_state if fighter == self.fighter1 else self.f2_state

    def _get_opponent_state(self, fighter):
        return self.f2_state if fighter == self.fighter1 else self.f1_state

    def _get_mod(self, attr: str, strategy: StrategySystem) -> float:
        return strategy.get_modifier_for_attr(attr)

    def _get_hit_quality(self, accuracy: float, defense: float) -> tuple:
        roll = random.gauss(accuracy - defense, 15)
        if roll > 35:
            return "flush", utils.SEVERITY_TIERS[4]["mult"]
        elif roll > 10:
            return "clean", utils.SEVERITY_TIERS[2]["mult"]
        elif roll > -5:
            return "glancing", utils.SEVERITY_TIERS[1]["mult"]
        return "miss", 0.0

    # ============================================================
    # WEB FIGHT INTERFACE
    # ============================================================

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
            self.strategy2.set_opponent_strategy(self.strategy1.current_strategy)
        return self.advance_web_fight()

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
                    self.strategy1.set_opponent_strategy(self.strategy2.current_strategy)
                    self.strategy2.set_opponent_strategy(self.strategy1.current_strategy)
        except StopIteration:
            pass
        return self._generate_result()

    def _generate_result(self) -> Dict:
        return {
            "winner": self.winner.name if self.winner else "Draw",
            "method": self.win_method,
            "round": self.win_round,
            "log": self.fight_log,
            "f1_health": self._get_display_health(self.fighter1),
            "f2_health": self._get_display_health(self.fighter2),
            "total_scores": self._get_total_scores(),
            "f1_total_score": self._get_total_score_for(1),
            "f2_total_score": self._get_total_score_for(2),
            "f1_state": self.f1_machine.get_state(),
            "f2_state": self.f2_machine.get_state(),
        }