import random
import math
from typing import Dict, Optional, List, Generator
from fighter import Fighter
from positions import PositionSystem, Position
from strategy import StrategySystem, STRATEGIES
from commentary import CommentaryEngine
import utils

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

STAMINA_COST = {
    "jab": 1, "cross": 2, "hook": 3, "uppercut": 3,
    "kick": 5, "knee": 4, "elbow": 3,
    "hammerfist": 2, "punch": 2, "superman_punch": 4,
    "takedown_attempt": 6, "clinch_attempt": 3,
    "ground_strike": 2, "submission_attempt": 4,
    "stand_up": 5, "sweep": 4, "pass_guard": 3,
    "advance_mount": 3, "take_back": 4,
}

COMBINATIONS = {
    "1-2":              {"strikes": ["jab", "cross"],           "power_bonus": 0.15, "stamina_mult": 1.1,  "iq_req": 20},
    "1-2-3":            {"strikes": ["jab", "cross", "hook"],   "power_bonus": 0.25, "stamina_mult": 1.3,  "iq_req": 35},
    "jab-hook":         {"strikes": ["jab", "hook"],            "power_bonus": 0.20, "stamina_mult": 1.15, "iq_req": 25},
    "double-jab-cross": {"strikes": ["jab", "jab", "cross"],    "power_bonus": 0.20, "stamina_mult": 1.25, "iq_req": 30},
    "uppercut-hook":    {"strikes": ["uppercut", "hook"],       "power_bonus": 0.35, "stamina_mult": 1.4,  "iq_req": 40},
    "3-2-body":         {"strikes": ["jab", "cross", "body_shot"], "power_bonus": 0.20, "stamina_mult": 1.2, "iq_req": 30},
    "leg-kick-set":     {"strikes": ["leg_kick", "jab-cross"],  "power_bonus": 0.15, "stamina_mult": 1.2,  "iq_req": 25},
}


# ============================================================
# MMA REFEREE
# ============================================================

class Referee:
    """MMA referee — no 8-count. Manages cage-side stoppages and standups."""

    def __init__(self, fighter1=None, fighter2=None):
        self.standup_pending = False
        self.target_fighter = None
        self.warning_issued = False
        self.consecutive_damage_count = 0
        self.fighter_ref = fighter1
        self.fighter2_ref = fighter2
        self.f1_unanswered_strikes = 0
        self.f2_unanswered_strikes = 0
        self.last_standup_round = 0

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
        if unanswered >= 5:
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
            if eye_health < 8:
                return f"Doctor stoppage: {fighter.name}'s {eye.replace('_', ' ')} is too damaged"

        # Jaw injuries
        jaw_health = fighter.get_zone_health_pct("jaw")
        if jaw_health < 5:
            return f"Doctor stoppage: {fighter.name}'s jaw is broken"

        if state.get("swelling", 0) > 95:
            return f"Doctor stoppage: Severe swelling on {fighter.name}"

        return None

    def check_foul(self, position, attacker_action) -> bool:
        """Basic foul detection — no strikes to back of head, no eye gouging, etc."""
        # 12-6 elbows (striking downward with elbow) — not allowed in some orgs
        # For this sim we keep it lenient — elbows allowed everywhere
        return False

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

class Judge:
    def __init__(self, name: str, bias: float = 0.0):
        self.name = name
        self.bias = bias
        self.scores: List[List[int]] = []
        self.round_details: List[dict] = []

    def score_round(self, rd: dict) -> tuple:
        """
        10-point must system with UFC-style criteria.
        rd contains: effective_striking, effective_grappling, aggression, octagon_control,
                      knockdowns_f1, knockdowns_f2, significant_advantage
        """
        # Effective striking (40%)
        strike_diff = rd["effective_striking_f1"] - rd["effective_striking_f2"]
        strike_score = self.normalize(strike_diff) * 0.40

        # Effective grappling (35%)
        grapple_diff = rd["effective_grappling_f1"] - rd["effective_grappling_f2"]
        grapple_score = self.normalize(grapple_diff) * 0.35

        # Effective aggression (15%)
        agg_diff = rd["aggression_f1"] - rd["aggression_f2"]
        agg_score = self.normalize(agg_diff) * 0.15

        # Octagon control (10%)
        cage_diff = rd["octagon_control_f1"] - rd["octagon_control_f2"]
        cage_score = self.normalize(cage_diff) * 0.10

        # Knockdown bonus (applied as additive, overrides other scoring)
        kd_diff = rd["knockdowns_f1"] - rd["knockdowns_f2"]

        f1_raw = strike_score + grapple_score + agg_score + cage_score + self.bias * 0.3
        f2_raw = -(strike_score + grapple_score + agg_score + cage_score) - self.bias * 0.3

        # Knockdowns shift the score
        if kd_diff != 0:
            f1_raw += kd_diff * 1.5
            f2_raw -= kd_diff * 1.5

        f1_round, f2_round = 10, 10
        diff = f1_raw - f2_raw

        if abs(diff) < 0.15:
            f1_round, f2_round = 10, 10  # Draw round
        elif diff > 0:
            f1_round = 10
            f2_round = max(7, 10 - self._score_diff_to_points(diff))
        else:
            f2_round = 10
            f1_round = max(7, 10 - self._score_diff_to_points(abs(diff)))

        if kd_diff >= 2:
            f2_round = min(f2_round, 7)
        elif kd_diff <= -2:
            f1_round = min(f1_round, 7)

        self.scores.append([f1_round, f2_round])
        self.round_details.append(rd)
        return (f1_round, f2_round)

    @staticmethod
    def normalize(value: float) -> float:
        """Normalize a difference to roughly -1.0 to 1.0 range."""
        return utils.clamp(value * 0.01, -1.0, 1.0)

    @staticmethod
    def _score_diff_to_points(diff: float) -> int:
        """Convert raw score difference to point deduction."""
        if diff < 0.3:
            return 1
        elif diff < 1.0:
            return 2
        elif diff < 2.5:
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

        # Referee
        self.referee = Referee(fighter1, fighter2)

        # Judges
        self.judges = [
            Judge("Judge A", bias=0.3),
            Judge("Judge B", bias=0.0),
            Judge("Judge C", bias=-0.3),
        ]

        # KO tracking
        self.f1_head_damage = 0.0  # Accumulated head damage for KO threshold
        self.f2_head_damage = 0.0
        self.f1_knockdowns_this_round = 0
        self.f2_knockdowns_this_round = 0

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
        self.f1_round_snap_grapple = 0.0
        self.f2_round_snap_grapple = 0.0

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
            "hurt": False,
            "stunned": False,
            "stunned_timer": 0,
            "rocked": False,
            "combo_count": 0,
            "submission_threat": {},
            "body_fatigue": 0,
            "vision_impairment": 0,
            "significant_strikes_landed": 0,
            "takedowns_landed": 0,
            "guard_passes": 0,
            "submissions_attempted": 0,
            "unanswered_ground_strikes": 0,
            "forward_pressure_points": 0,
            "effective_grappling_points": 0.0,
            "damage_taken_log": [],
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
        if score_deficit > 5:
            base += 0.2
        elif score_deficit > 15:
            base += 0.4

        return min(base, 2.0)

    def _get_score_deficit(self, fighter_num: int) -> int:
        """How much a fighter is losing by on the scorecards."""
        if not self.judges[0].scores:
            return 0
        last_idx = len(self.judges[0].scores) - 1
        total1 = sum(j.scores[last_idx][0] for j in self.judges)
        total2 = sum(j.scores[last_idx][1] for j in self.judges)
        if fighter_num == 1:
            return max(0, total2 - total1)
        return max(0, total1 - total2)

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
        if fighter == self.fighter1:
            self.f1_head_damage += damage / 1.5
            self.f1_state["damage_taken_log"].append({"type": "head", "damage": damage, "round": self.current_round})
        else:
            self.f2_head_damage += damage / 1.5
            self.f2_state["damage_taken_log"].append({"type": "head", "damage": damage, "round": self.current_round})

    def _track_ko_accumulation(self, fighter: Fighter, damage: float, zone_mult: float):
        # No KOs in round 1 to prevent instant finishes
        if self.current_round < 2:
            return
        chin_resistance = fighter.get_chin_resistance()
        ko_threshold = chin_resistance

        if fighter == self.fighter1:
            if self.f1_head_damage > ko_threshold:
                self.winner = self.fighter2
                self.loser = self.fighter1
                # Determine if it's a KO or TKO based on how quickly damage accumulated
                recent_head_dmg = sum(
                    d["damage"] for d in self.f1_state["damage_taken_log"]
                    if self.current_round - d["round"] <= 1
                )
                if recent_head_dmg > ko_threshold * 0.5:
                    self.win_method = "KO"
                else:
                    self.win_method = "TKO"
                self.win_round = self.current_round
                self.fight_log.append(f"\n*** {self.fighter2.name} stops {self.fighter1.name}! {self.win_method} in round {self.current_round}! ***")
        else:
            if self.f2_head_damage > ko_threshold:
                self.winner = self.fighter1
                self.loser = self.fighter2
                recent_head_dmg = sum(
                    d["damage"] for d in self.f2_state["damage_taken_log"]
                    if self.current_round - d["round"] <= 1
                )
                if recent_head_dmg > ko_threshold * 0.5:
                    self.win_method = "KO"
                else:
                    self.win_method = "TKO (Strikes)"
                self.win_round = self.current_round
                self.fight_log.append(f"\n*** {self.fighter1.name} stops {self.fighter2.name}! {self.win_method} in round {self.current_round}! ***")

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
            self.f1_round_snap_grapple = self.f1_state.get("effective_grappling_points", 0.0)
            self.f2_round_snap_grapple = self.f2_state.get("effective_grappling_points", 0.0)

            # Determine number of actions this round (~based on pace)
            total_actions = self._determine_actions_this_round(round_num)

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
                phase = self._get_phase(phase_progress)

                # Check referee standup (MMA-specific)
                if self.referee.should_stand_up(self, round_num):
                    standup_text = "The referee stands them up!"
                    yield {"type": "action", "text": standup_text, "round": round_num, "time": self._get_time_str()}
                    self.position_system.current_position = Position.DISTANCE
                    self.position_system.position_time = 0
                    self.referee.last_standup_round = round_num
                    continue

                self._simulate_action(phase=phase)

                if not self.winner and round_num >= 2 and action_idx > 0 and action_idx % 15 == 0 and random.random() < 0.3:
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
                            return

                # Yield action result with time stamp
                if self.fight_log:
                    last = self.fight_log[-1]
                    event = {"type": "action", "text": last, "round": round_num,
                             "f1_health": self._get_display_health(self.fighter1),
                             "f2_health": self._get_display_health(self.fighter2),
                             "f1_state": self.f1_machine.get_state(),
                             "f2_state": self.f2_machine.get_state(),
                             "f1_total_score": self._get_total_score_for(1),
                             "f2_total_score": self._get_total_score_for(2),
                             "time": self._get_time_str()}
                    yield event

                # Mid-round AI adaptation (every 6 actions)
                if action_idx % 6 == 5 and round_num > 1 and not self.winner:
                    self._check_ai_mid_round()

            if self.winner:
                # Knockout/Submission finish
                if "KO" in self.win_method or "TKO" in self.win_method:
                    yield {"type": "knockout", "text": self.commentary.generate_knockout_commentary(self.loser),
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
                           "total_scores": self._get_total_scores()}
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
                yield {"type": "strategy_prompt", "round": round_num,
                       "f1_stats": {"sig_strikes": f1_sig, "takedowns": f1_td, "grapple_points": round(f1_gp, 1), "fatigue": round(f1_fat)},
                       "f2_stats": {"sig_strikes": f2_sig, "takedowns": f2_td, "grapple_points": round(f2_gp, 1), "fatigue": round(f2_fat)},
                       "f1_total_score": self._get_total_score_for(1),
                       "f2_total_score": self._get_total_score_for(2),
                       "f1_health": self._get_display_health(self.fighter1),
                       "f2_health": self._get_display_health(self.fighter2),
                       "f1Name": self.fighter1.name,
                       "f2Name": self.fighter2.name,
                       "score_detail": f"{int(f1_avg)}-{int(f2_avg)}"}

            if round_num >= 2 and round_num < self.rounds and not self.winner:
                for fighter, state in [(self.fighter1, self.f1_state), (self.fighter2, self.f2_state)]:
                    stop_reason = self.referee.check_doctor_stoppage(fighter, state, self)
                    if stop_reason and random.random() < 0.5:
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

        yield {"type": "complete", "winner": self.winner.name if self.winner else "Draw",
               "method": self.win_method, "round": self.win_round,
               "f1_health": self._get_display_health(self.fighter1),
               "f2_health": self._get_display_health(self.fighter2),
               "total_scores": self._get_total_scores()}

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
        Determine how many actions in this round based on fight pace.
        Later rounds with high fatigue = fewer effective actions.
        Early rounds = more actions, championship pacing.
        """
        base_actions = random.randint(28, 40)
        avg_fatigue = (self.f1_state["fatigue_level"] + self.f2_state["fatigue_level"]) / 2
        # Past round 3, fatigue reduces action count
        if round_num > 3:
            reduction = avg_fatigue * (round_num - 3) * 3
            base_actions = max(15, int(base_actions - reduction))
        return base_actions

    def _get_phase(self, progress: float) -> str:
        if progress < 0.15:
            return "feeling_out"
        elif progress > 0.75:
            return "desperation"
        return "exchanges"

    # ============================================================
    # CORE ACTION SIMULATION
    # ============================================================

    def _simulate_action(self, phase="exchanges"):
        """Simulate one action exchange between fighters."""
        atk1, def1, atk_state1, def_state1, strat1 = (
            self.fighter1, self.fighter2, self.f1_state, self.f2_state, self.strategy1)
        atk2, def2, atk_state2, def_state2, strat2 = (
            self.fighter2, self.fighter1, self.f2_state, self.f1_state, self.strategy2)

        # Determine who is the attacker this exchange
        # Higher aggression = higher chance to initiate
        agg1 = atk1.get_effective_attribute("aggression", atk_state1["fatigue_level"])
        agg2 = atk2.get_effective_attribute("aggression", atk_state2["fatigue_level"])

        if random.random() < agg1 / (agg1 + agg2 + 1):
            attacker, defender, atk_state, def_state, atk_strategy, df_strategy = \
                atk1, def1, atk_state1, def_state1, strat1, strat2
        else:
            attacker, defender, atk_state, def_state, atk_strategy, df_strategy = \
                atk2, def2, atk_state2, def_state2, strat2, strat1

        # Check state-based accuracy/power modifiers
        state_mods = self.f1_machine.get_stat_modifier() if attacker == self.fighter1 else self.f2_machine.get_stat_modifier()
        if state_mods["accuracy"] <= 0.4:
            # Fighter is essentially out — skip
            return

        # Ground game: use dedicated ground action system
        if Position.is_ground(self.position_system.current_position):
            self._simulate_ground_action(atk_state["fatigue_level"],
                                         atk_strategy.get_action_weights(), atk_strategy)
            self.referee.record_damage_taken(defender, False, attacker=attacker)
            return

        # Determine if combo or single strike
        fight_iq = attacker.get_effective_attribute("fight_iq", atk_state["fatigue_level"])
        fatigue = atk_state["fatigue_level"]

        combo_type = None
        if random.random() < utils.calculate_combo_chance(fight_iq, fatigue):
            available_combos = [c for c in COMBINATIONS if COMBINATIONS[c]["iq_req"] <= fight_iq]
            if available_combos and random.random() < 0.4:  # 40% chance to combo
                combo_type = random.choice(available_combos)

        if combo_type:
            self._execute_combo(attacker, defender, atk_state, def_state, atk_strategy, combo_type, phase, state_mods)
        else:
            self._execute_single_strike(attacker, defender, atk_state, def_state, atk_strategy, phase, state_mods)

        # Check defensive action for defender
        self._execute_defense(attacker, defender, atk_state, def_state, atk_strategy, df_strategy, phase)

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
        target = self._select_target(strike_type, pos, def_state)

        self._perform_strike(attacker, defender, atk_state, def_state, strike_type, target, strategy, phase, state_mods)

    def _execute_combo(self, attacker, defender, atk_state, def_state, strategy, combo_key, phase, state_mods):
        combo = COMBINATIONS[combo_key]
        strikes = combo["strikes"]
        self.fight_log.append(f"{attacker.name} throws a {combo_key.replace('-', ' ')}!")

        stamina_mult = combo.get("stamina_mult", 1.0)
        base_bonus = combo.get("power_bonus", 0.0)

        for i, strike_type in enumerate(strikes):
            pos = self.position_system.current_position
            target = self._select_target(strike_type, pos, def_state)

            # Combos have slightly reduced accuracy on later strikes
            accuracy_penalty = 1.0 - (i * 0.08)
            mod_copy = state_mods.copy()
            mod_copy["accuracy"] *= accuracy_penalty

            self._perform_strike(attacker, defender, atk_state, def_state, strike_type, target,
                                strategy, phase, mod_copy, combo_bonus=base_bonus, stamina_mult=stamina_mult)

            # Defender can be staggered mid-combo
            head_pct = defender.get_zone_health_pct("jaw") * 0.5 + defender.get_zone_health_pct("temple") * 0.5
            if head_pct < 40 and random.random() < 0.3:
                self.fight_log.append(f"{defender.name} is staggered by the combination!")
                break

            # Check if combo broke
            if def_state.get("state") == "DOWN" or self.winner:
                break

    def _execute_defense(self, attacker, defender, atk_state, def_state, atk_strategy, df_strategy, phase):
        """Simulate defender's active defense — sometimes they block/slip/parry."""
        defense_action = self._select_defense(defender, atk_strategy)
        if defense_action == "block":
            pass  # Damage already reduced by block factor
        elif defense_action == "slip":
            if random.random() < 0.3:
                self.fight_log.append(f"{defender.name} slips the strike!")
        elif defense_action == "parry":
            if random.random() < 0.25:
                self.fight_log.append(f"{defender.name} parries and creates an opening!")

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
        elif phase == "desperation":
            weights["takedown"] *= 0.5  # Less takedowns when desperate
            weights["clinch"] *= 0.6

        # Position adjustments
        if pos == Position.DISTANCE:
            weights["strike"] *= 1.5
            weights["takedown"] *= 0.6
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
            return self._select_specific_strike(pos)
        elif choice == "takedown":
            return "takedown_attempt"
        elif choice == "clinch":
            return "clinch_attempt"
        return "jab"

    def _select_specific_strike(self, pos) -> str:
        """Select from specific strikes based on position."""
        if pos == Position.DISTANCE:
            return random.choice(["jab", "cross", "kick", "superman_punch"])
        elif pos == Position.POCKET:
            return random.choice(["jab", "cross", "hook", "uppercut", "knee", "elbow"])
        elif pos in (Position.CLINCH,):
            return random.choice(["knee", "elbow"])
        elif Position.is_ground(pos):
            return random.choice(["hammerfist", "elbow", "punch"])
        return "jab"

    def _select_target(self, strike_type, pos, def_state) -> str:
        """Select body target based on strike type and strategy context."""
        is_kick = "kick" in strike_type
        is_ground = Position.is_ground(pos)

        if is_kick:
            # Leg kicks become more likely as fight progresses
            return random.choice(["head", "body", "legs"])

        if is_ground:
            return random.choice(["head", "body"])

        if strike_type in ("jab", "cross"):
            # Head-focused but some body work
            return random.choice(["head", "head", "head", "body", "jaw"])
        elif strike_type in ("hook", "uppercut"):
            return random.choice(["head", "jaw", "body"])
        elif strike_type in ("knee", "elbow"):
            return random.choice(["head", "body"])
        elif strike_type == "body_shot":
            return "body"

        return random.choice(["head", "body", "jaw"])

    def _perform_strike(self, attacker, defender, atk_state, def_state,
                        strike_type, target, strategy, phase, state_mods,
                        combo_bonus=0.0, stamina_mult=1.0):
        """Execute a strike with full damage calculation."""
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
        phase_power = {"feeling_out": 0.75, "desperation": 1.3}.get(phase, 1.0)

        # Reach advantage
        reach_mod = self.position_system.get_reach_advantage(attacker, defender)

        # State modifiers from fighter state machine
        power = attacker.get_effective_attribute(power_attr, atk_state["fatigue_level"]) * sp_mod * phase_power
        speed = attacker.get_effective_attribute(speed_attr, atk_state["fatigue_level"]) * hs_mod
        raw_accuracy = attacker.get_effective_attribute(accuracy_attr, atk_state["fatigue_level"])

        # Composite accuracy calculation
        accuracy = raw_accuracy * (speed / 100) * reach_mod * (1.0 + fight_iq / 600)
        accuracy *= (0.8 if phase == "feeling_out" else (1.15 if phase == "desperation" else 1.0))
        accuracy *= state_mods.get("accuracy", 1.0)

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

        # Clamp accuracy
        accuracy = utils.clamp(accuracy, 3, 98)

        # Determine if strike lands and at what severity
        defense_score = self._get_composite_defense(defender, def_state, atk_state)
        tier = utils.determine_severity(accuracy, defense_score, power, composure,
                                         self.get_adrenaline(1 if attacker == self.fighter1 else 2))

        # Check for critical hit
        is_critical = utils.check_critical_hit(accuracy, composure,
                                                self.get_adrenaline(1 if attacker == self.fighter1 else 2))

        # Calculate damage
        weight_mod = self._strike_weight_modifier(attacker.weight_class)
        cardio = attacker.get_effective_attribute("cardio", atk_state["fatigue_level"])
        self._apply_stamina_cost(atk_state, strike_type, atk_state["fatigue_level"], cardio, stamina_mult)

        # Build damage formula
        base_damage = profile["base_damage"]
        damage_multiplier = tier["mult"] * weight_mod * (1.0 + combo_bonus)

        # Power contribution (non-linear scaling)
        power_contribution = (power / 50.0) ** 0.85

        # Defense contribution (non-linear — diminishing returns at high defense)
        defense_factor = defense_score / 150.0
        defense_reduction = 1.0 / (1.0 + defense_factor * 1.5)

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
        if target == "body":
            damage = int(damage * 0.8)
        elif target == "legs":
            damage = int(damage * 0.55)
        elif target in ("jaw", "temple"):
            damage = int(damage * 1.2)

        # Apply damage to zone
        actual_damage = defender.apply_damage_to_zone(target, damage, self)

        # Update state tracking
        if attacker == self.fighter1:
            self.f1_actions_landed += 1
            self.f1_state["significant_strikes_landed"] += 1
            self.f1_state["rounds_damage_dealt"].append(actual_damage)
        else:
            self.f2_actions_landed += 1
            self.f2_state["significant_strikes_landed"] += 1
            self.f2_state["rounds_damage_dealt"].append(actual_damage)

        # Update body fatigue
        defender_state = def_state
        if target == "body":
            defender_state["body_fatigue"] = min(100, defender_state["body_fatigue"] + actual_damage * 0.5)
            # Body damage drains attacker stamina too (body shots are tiring)
            stamina_drain = int(actual_damage * 0.3)
            atk_state["stamina"] = max(0, atk_state["stamina"] - stamina_drain)

        # Leg damage tracking
        if target == "legs":
            defender_state["leg_damage"] = min(100, defender_state["leg_damage"] + actual_damage * 0.6)

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
        if target == "body":
            body_damage = defender_state["body_fatigue"]
            bd_effects = utils.get_body_damage_level(body_damage)
            if bd_effects:
                stamina_drain_mod = bd_effects["stamina_drain"]
                def_state["stamina"] = max(0, def_state["stamina"] - int(stamina_drain_mod * 15))

        # Check for stun and state transitions
        head_pct = defender.get_group_health("head")
        body_pct = defender.get_group_health("body")
        leg_pct = defender.get_group_health("legs")

        # Mark hurt state
        if head_pct < 55 or body_pct < 45:
            defender_state["hurt"] = True
            self._transition_fighter_state(defender, def_state, "HURT")
        if head_pct < 30:
            defender_state["stunned"] = True
            defender_state["stunned_timer"] = max(defender_state["stunned_timer"], 2)

        # Stun check from strike severity
        stun_chance = tier.get("knockdown_chance", 0)
        if defender_state["stunned"]:
            stun_chance *= 1.5
        if defender_state["hurt"]:
            stun_chance *= 1.2
        if random.random() < stun_chance:
            defender_state["stunned"] = True
            defender_state["stunned_timer"] = random.randint(2, 4)

        # Check for knockdown (KO threshold) — minimum round 2 before KOs
        if self.current_round >= 2 and tier["name"] == "Devastating" and target in ("head", "jaw", "temple"):
            self._check_knockdown(attacker, defender, atk_state, def_state, target, actual_damage,
                                   atk_state["fatigue_level"], strike_type)

        # Generate commentary
        strike_commentary = self.commentary.generate_strike_commentary(
            attacker, defender, strike_type, target,
            self.position_system.current_position)

        # Prefix with severity descriptor
        severity_prefix = {
            "Blocked": "blocks",
            "Glancing": "glances off",
            "Clean": "lands a clean",
            "Solid": "lands a solid",
            "Flush": "cracks in with a flush",
            "Devastating": "DEVASTATES with a",
            "CRITICAL Blocked": "blocks desperately",
            "CRITICAL Glancing": "barely grazes",
            "CRITICAL Clean": "SMASHES a critical",
            "CRITICAL Solid": "THUNDERS home a critical",
            "CRITICAL Flush": "DELIVERS a devastating critical",
            "CRITICAL Devastating": "UNLEASHES a fight-ending critical",
        }.get(tier["name"], "lands a")

        # Update combo tracking
        atk_state["combo_count"] += 1

        # Log the action (commentary will be generated)
        log_entry = f"{attacker.name} {severity_prefix} {strike_type} to {defender.name}'s {target}"
        if is_critical:
            log_entry += " — CRITICAL HIT!"
        self.fight_log.append(log_entry)

        # Vision impairment update
        vision_damage = tier.get("vision_damage", 0) * 100
        def_state["vision_impairment"] = min(80, def_state["vision_impairment"] + vision_damage)

    def _get_composite_defense(self, defender, def_state, atk_state) -> float:
        """
        Calculate complete defensive rating for this moment.
        Includes: durability, composure, fight IQ, state modifiers, fatigue.
        """
        fatigue = def_state["fatigue_level"]
        durability = defender.get_effective_attribute("durability", fatigue)
        composure = defender.get_effective_attribute("composure", fatigue)
        fight_iq = defender.get_effective_attribute("fight_iq", fatigue)

        # Base defense score
        defense = (durability * 0.40 + composure * 0.25 + fight_iq * 0.20)

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

        # Vision impairment reduces defense
        vision = def_state.get("vision_impairment", 0)
        if vision > 20:
            defense *= max(0.6, 1.0 - (vision - 20) / 200.0)

        # Guard up when hurt — bonus defense but costs stamina
        if def_state["hurt"]:
            # Higher fight IQ = better defensive reads when hurt
            defense += fight_iq * 0.1

        return utils.clamp(defense, 10, 95)

    def _apply_stamina_cost(self, state, action_key: str, fatigue: float, cardio: int, stamina_mult: float = 1.0):
        base_cost = STAMINA_COST.get(action_key, 2)
        cardio_eff = cardio / 100.0
        cost = base_cost * (1.15 - cardio_eff * 0.2)
        cost *= (1.0 + fatigue * 0.3)

        combo_count = state.get("combo_count", 0)
        if combo_count > 3:
            cost *= (1.0 + (combo_count - 3) * 0.1)

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

            # Commentary on state transitions
            if new_state == "HURT":
                self.fight_log.append(f"{fighter.name} is hurt!")
            elif new_state == "ROCKED":
                self.fight_log.append(f"{fighter.name} is ROCKED!")
            elif new_state == "STUNNED":
                self.fight_log.append(f"{fighter.name} is STUNNED!")

    # ============================================================
    # TAKEDOWN SYSTEM
    # ============================================================

    def _simulate_takedown(self, attacker, defender, fatigue, strategy):
        td_mod = self._get_mod("takedown_power", strategy)
        tda_mod = self._get_mod("takedown_accuracy", strategy)
        wd_mod = self._get_mod("wrestling_defense", strategy)

        at_attrs = attacker.attributes
        temp_power = at_attrs.get("takedown_power", 50) * td_mod
        temp_accuracy = at_attrs.get("takedown_accuracy", 50) * tda_mod

        attacker.takedown_power_temp = temp_power
        attacker.takedown_accuracy_temp = temp_accuracy

        defender.wrestling_defense_temp = defender.attributes.get("wrestling_defense", 50) * wd_mod

        # Weight class advantage in grappling
        weight_advantage = (attacker.base_weight_lbs - defender.base_weight_lbs) / 50.0
        weight_advantage = utils.clamp(weight_advantage, -0.3, 0.3)
        temp_power *= (1.0 + weight_advantage)

        # Leg damage reduces takedown power
        if attacker == self.fighter1:
            leg_penalty = 1.0 - (self.f1_state["leg_damage"] / 300.0)
        else:
            leg_penalty = 1.0 - (self.f2_state["leg_damage"] / 300.0)
        temp_power *= max(0.7, leg_penalty)

        attacker.takedown_power_temp *= leg_penalty

        defender_state = self._get_opponent_state(attacker)
        self._apply_stamina_cost(
            self._get_attacker_state(attacker),
            "takedown_attempt", fatigue,
            attacker.get_effective_attribute("cardio", fatigue)
        )

        is_clinch = self.position_system.current_position == Position.CLINCH
        if is_clinch:
            success = self.position_system.takedown_from_clinch(attacker, defender, fatigue)
        else:
            success = self.position_system.attempt_takedown(attacker, defender, fatigue)
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
            def_state = self._get_opponent_state(attacker)
            def_state["unanswered_ground_strikes"] = 0
        else:
            # Defended takedown — counter opportunity
            if random.random() < 0.2:
                self.fight_log.append(f"{defender.name} stuffs it and looks for a guillotine!")

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
        """Ground game with strategy-weighted decisions."""
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

        # Weighted decision based on strategy
        if random.random() < 0.5:
            self._process_ground_top_action(top, bottom, top_state, bottom_state, fatigue, top_strategy, action_weights, pos, pt)
        else:
            self._process_ground_bottom_action(top, bottom, top_state, bottom_state, fatigue, bottom_strategy, pos, pt)

    def _process_ground_top_action(self, top, bottom, top_state, bottom_state, fatigue, strategy, action_weights, pos, pt):
        top_cardio = top.get_effective_attribute("cardio", fatigue)

        # Guard pass attempt
        if pos == Position.GROUND_GUARD and pt > 4 and random.random() < 0.35:
            if self.position_system.pass_guard(top, bottom, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "pass_guard", fighter=top.name, opponent=bottom.name))
                top_state["guard_passes"] += 1
                top_state["effective_grappling_points"] += 4.0
                self._apply_stamina_cost(top_state, "pass_guard", fatigue, top_cardio)
                bottom_state["unanswered_ground_strikes"] = 0
                return

        # Side control → mount
        elif pos == Position.GROUND_SIDE:
            if pt > 3:
                if random.random() < 0.3 and self.position_system.advance_to_mount(top, bottom, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "mount", fighter=top.name, opponent=bottom.name))
                    top_state["effective_grappling_points"] += 5.0
                    self._apply_stamina_cost(top_state, "advance_mount", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return
                elif random.random() < 0.15 and self.position_system.take_back(top, bottom, fatigue):
                    self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                        "back_take", fighter=top.name, opponent=bottom.name))
                    top_state["effective_grappling_points"] += 6.0
                    self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                    bottom_state["unanswered_ground_strikes"] = 0
                    return

        # Mount → back take
        elif pos == Position.GROUND_MOUNT:
            if pt > 3 and random.random() < 0.15 and self.position_system.take_back(top, bottom, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "back_take", fighter=top.name, opponent=bottom.name))
                top_state["effective_grappling_points"] += 6.0
                self._apply_stamina_cost(top_state, "take_back", fatigue, top_cardio)
                bottom_state["unanswered_ground_strikes"] = 0
                return

        # Submission attempt from top
        sub_chance = action_weights.get("submission", 0.3) * (1.3 if pos in (Position.GROUND_SIDE, Position.GROUND_MOUNT) else 1.0)
        if random.random() < sub_chance:
            self._simulate_submission_attempt(top, bottom, fatigue, strategy, pos)
        else:
            self._simulate_ground_strike(top, bottom, top_state, bottom_state, fatigue, strategy, pos)

    def _process_ground_bottom_action(self, top, bottom, top_state, bottom_state, fatigue, strategy, pos, pt):
        bottom_cardio = bottom.get_effective_attribute("cardio", fatigue)

        # Guard submissions from bottom
        if pos == Position.GROUND_GUARD and pt > 3 and random.random() < 0.25:
            if random.random() < 0.4:
                self._simulate_submission_attempt(bottom, top, fatigue, strategy, pos)
                return

        # Sweep attempts
        pos_bonus = 1.0 if pos == Position.GROUND_GUARD else (0.7 if pos == Position.GROUND_SIDE else (0.4 if pos == Position.GROUND_MOUNT else 0.2))
        if random.random() < 0.4 * pos_bonus:
            if self.position_system.sweep_from_bottom(bottom, top, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "sweep", bottom=bottom.name, top=top.name))
                bottom_state["effective_grappling_points"] += 5.0
                self._apply_stamina_cost(bottom_state, "sweep", fatigue, bottom_cardio)
            else:
                self.fight_log.append(f"{bottom.name} tries to sweep but {top.name} defends.")
        else:
            if self.position_system.stand_up_from_bottom(bottom, top, fatigue):
                self.fight_log.append(self.commentary.generate_ground_transition_commentary(
                    "stand_up", fighter=bottom.name))
                bottom_state["effective_grappling_points"] += 2.0
                self._apply_stamina_cost(bottom_state, "stand_up", fatigue, bottom_cardio)
            else:
                self.fight_log.append(f"{bottom.name} tries to stand but {top.name} keeps them down.")

    def _simulate_ground_strike(self, attacker, defender, atk_state, def_state, fatigue, strategy, pos=Position.GROUND_GUARD):
        strike_type = random.choice(["hammerfist", "elbow", "punch"])
        target = random.choice(["head", "body"])
        sp_mod = self._get_mod("striking_power", strategy)
        power = attacker.get_effective_attribute("striking_power", fatigue) * sp_mod
        durability = defender.get_effective_attribute("durability", 1.0 - (def_state["stamina"] / 100))

        pos_power = {Position.GROUND_GUARD: 0.30, Position.GROUND_SIDE: 0.45,
                     Position.GROUND_MOUNT: 0.60, Position.GROUND_BACK: 0.35}
        pos_bonus = pos_power.get(pos, 0.3)

        tc_mod = self._get_mod("top_control", strategy)
        top_bonus = 1.0 + (tc_mod - 1.0) * 0.6

        ground_strike_bonus = strategy.get_modifiers().get("ground_strike_damage", 1.0)

        raw = (power / 50) * 5 * pos_bonus * top_bonus * ground_strike_bonus
        damage = max(1, int(raw * (1 - durability / 200)))

        actual_damage = defender.apply_damage_to_zone(target, damage, self)
        def_state["accumulated_damage"] += actual_damage

        def_state["unanswered_ground_strikes"] = def_state.get("unanswered_ground_strikes", 0) + 1
        if attacker == self.fighter1:
            self.f1_state["unanswered_ground_strikes"] = def_state.get("unanswered_ground_strikes", 0)
        else:
            self.f2_state["unanswered_ground_strikes"] = def_state.get("unanswered_ground_strikes", 0)

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

        # TKO from ground strikes (referee stoppage)
        unanswered = def_state.get("unanswered_ground_strikes", 0)
        if unanswered >= 10 and pos not in (Position.GROUND_GUARD,):
            self.winner = attacker
            self.loser = defender
            self.win_method = "TKO (Ground Strikes)"
            self.win_round = self.current_round
            self.fight_log.append(f"The referee steps in! {defender.name} can't defend themselves!")
            return
        elif unanswered >= 7 and pos == Position.GROUND_MOUNT:
            self.winner = attacker
            self.loser = defender
            self.win_method = "TKO (Ground Strikes)"
            self.win_round = self.current_round
            self.fight_log.append(f"The referee steps in! {defender.name} is taking too much damage from mount!")
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
        guard_subs_top = ["kimura", "d'arce choke", "americana"]
        guard_subs_bottom = ["triangle choke", "armbar", "guillotine"]
        side_subs = ["kimura", "d'arce choke", "armbar"]
        mount_subs = ["armbar", "mounted triangle"]
        back_subs = ["rear naked choke"]

        if pos == Position.GROUND_GUARD:
            return guard_subs_top if attacker_is_top else guard_subs_bottom
        elif pos == Position.GROUND_SIDE:
            return side_subs
        elif pos == Position.GROUND_MOUNT:
            return mount_subs
        elif pos == Position.GROUND_BACK:
            return back_subs
        return ["armbar"]

    def _simulate_submission_attempt(self, attacker, defender, fatigue, strategy, pos=Position.GROUND_GUARD):
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

        self.fight_log.append(self.commentary.generate_ground_commentary(
            "submission_attempt", attacker=attacker.name, submission=submission))

        # Positional advantage multiplier
        pos_bonus = {Position.GROUND_GUARD: 1.0, Position.GROUND_SIDE: 1.2,
                     Position.GROUND_MOUNT: 1.4, Position.GROUND_BACK: 1.7}
        pb = pos_bonus.get(pos, 1.0)

        # Get correct defensive state
        if attacker == self.fighter1:
            def_state = self.f2_state
        else:
            def_state = self.f1_state

        threat_key = submission
        current_threat = def_state.get("submission_threat", {}).get(threat_key, 0)

        # Submission threat builds with more realistic formula
        base_threat = (sub_off * 0.1 - sub_def * 0.05) * pb
        mental_resistance = mental / 250.0
        cardio_resistance = cardio / 200.0
        threat_increment = base_threat * (1.0 - mental_resistance * 0.3) * (1.0 - cardio_resistance * 0.2)
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

        # Defense calculation
        mental_factor = mental / 200.0
        cardio_factor = cardio / 200.0
        sub_def_factor = sub_def / 150.0
        defense_factor = 0.35 + mental_factor + cardio_factor * 0.4 + sub_def_factor * 0.25

        # Damage-based urgency: lower health = harder to defend
        defender_health = (defender.get_zone_health("head") + defender.get_zone_health("body")) / 100.0
        health_urgency = max(0.5, 1.0 - (1.0 - defender_health) * 0.5)

        success_chance = max(2, min(60, (new_threat * 1.1 - sub_def * defense_factor * 0.12) * pb * health_urgency))

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
        """Apply end-of-round effects: stamina recovery, injury checks."""
        for state in [self.f1_state, self.f2_state]:
            # Stamina recovery between rounds
            stamina_recovery = 20 + state.get("stamina", 100) * 0.15
            state["stamina"] = min(100, state["stamina"] + stamina_recovery)
            state["fatigue_level"] = 1.0 - (state["stamina"] / 100)

            # Reduce stun/hurt timers
            state["stunned_timer"] = max(0, state["stunned_timer"] - 2)
            if state["stunned_timer"] == 0:
                state["stunned"] = False

            # Reduce swelling slightly
            state["swelling"] = max(0, state["swelling"] - 5)

            # Reset combo tracking
            state["combo_count"] = 0

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
            self.fight_log.append(f"{defender.name} is stunned by that shot!")
            return True
        return False

    def _check_knockdown(self, attacker, defender, atk_state, def_state, target, damage, fatigue, strike_type):
        """MMA knockdown — when head health drops to critical levels."""
        jaw_health = defender.get_zone_health("jaw")
        temple_health = defender.get_zone_health("temple")
        overall_head = defender.get_group_health("head")

        if jaw_health <= 0 or temple_health <= 0 or overall_head <= 10:
            def_state["knockdown_count"] += 1
            if attacker == self.fighter1:
                self.f1_knockdowns_this_round += 1
            else:
                self.f2_knockdowns_this_round += 1
            def_state["knockdown"] = True
            def_state["stunned"] = False
            def_state["stunned_timer"] = 0

            self.fight_log.append(self.commentary.generate_knockdown_commentary(defender))
            self.fight_log.append(f"{defender.name} goes down!")

            # MMA — fighter has time to recover (referee will stop if can't)
            heart = defender.get_effective_attribute("heart", fatigue)
            composure = defender.get_effective_attribute("composure", fatigue)
            mental = defender.get_effective_attribute("mental_toughness", fatigue)
            chin = defender.get_chin_resistance()

            recovery_score = heart * 0.3 + composure * 0.2 + mental * 0.2 + chin * 0.002

            if overall_head <= 4:
                # Very low health — likely won't get up
                self.winner = attacker
                self.loser = defender
                self.win_method = "KO"
                self.win_round = self.current_round
                self.fight_log.append(f"{defender.name} can't beat the count! It's over!")
                return True
            elif recovery_score < 35:
                self.winner = attacker
                self.loser = defender
                self.win_method = "TKO"
                self.win_round = self.current_round
                self.fight_log.append(f"{defender.name} is struggling to get up... ref waves it off!")
                return True
            else:
                self.fight_log.append(f"{defender.name} is trying to recover...")
                return True
        return False

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

        # Scorecard update commentary
        self.fight_log.append(f"End of Round {round_num}:")
        for judge in self.judges:
            self.fight_log.append(f"  {judge.name}: {judge.scores[r_idx][0]}-{judge.scores[r_idx][1]}")
        self.fight_log.append(f"  Score: {score_text}")

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
        """More frequent AI adaptation during rounds."""
        f1_total = sum(sum(j.scores[r][0] for j in self.judges) for r in range(len(self.judges[0].scores))) if self.judges[0].scores else 0
        f2_total = sum(sum(j.scores[r][1] for j in self.judges) for r in range(len(self.judges[0].scores))) if self.judges[0].scores else 0

        round_diffs = [int(sum(j.scores[r][1] - j.scores[r][0] for j in self.judges) / 3.0)
                       for r in range(len(self.judges[0].scores))]

        new_strat = StrategySystem.pick_ai_strategy(
            self.fighter2, self.fighter1,
            round_diffs, self.current_round, self.rounds, self.strategy2.current_strategy)
        self.strategy2.adjust_strategy(new_strat)
        self.strategy1.set_opponent_strategy(self.strategy2.current_strategy)

    def _check_ai_adaptation(self, round_num: int):
        """Between-round AI adaptation."""
        new_strat = StrategySystem.pick_ai_strategy(
            self.fighter2, self.fighter1,
            [], self.current_round, self.rounds, self.strategy2.current_strategy)
        self.strategy2.adjust_strategy(new_strat)
        self.strategy1.set_opponent_strategy(self.strategy2.current_strategy)

        # Pattern recognition: detect if one fighter keeps using same strategy
        if self.f1_state.get("combo_count", 0) > 5:
            # Fighter1 keeps throwing combos, AI adapts
            self.fight_log.append(f"{self.fighter2.name} starts reading the patterns!")

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

    def _get_display_health(self, fighter: Fighter) -> dict:
        """Format health display for the frontend."""
        f_state = self.f1_state if fighter == self.fighter1 else self.f2_state
        return {
            "head": round(fighter.get_group_health("head"), 1),
            "body": round(fighter.get_group_health("body"), 1),
            "legs": round(fighter.get_group_health("legs"), 1),
            "overall": round(fighter.get_overall_health_pct(), 1),
            "stamina": round(f_state.get("stamina", 100), 1),
            "blood": round(fighter._blood_level, 1),
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