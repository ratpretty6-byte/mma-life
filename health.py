from typing import Dict, List, Optional
from fighter import Fighter
from datetime import datetime, timedelta
import random

INJURY_TYPES = {
    "cut": {"base_severity": 0.3, "recovery_days": 7, "affected_attrs": ["striking_accuracy"]},
    "swelling": {"base_severity": 0.2, "recovery_days": 5, "affected_attrs": ["composure"]},
    "bruise": {"base_severity": 0.2, "recovery_days": 5, "affected_attrs": ["durability"]},
    "strain": {"base_severity": 0.4, "recovery_days": 10, "affected_attrs": ["athleticism"]},
    "broken_bone": {"base_severity": 0.8, "recovery_days": 60, "affected_attrs": ["striking_power", "kick_power"]},
    "concussion": {"base_severity": 0.7, "recovery_days": 45, "affected_attrs": ["composure", "fight_iq"]},
    "ligament_tear": {"base_severity": 0.6, "recovery_days": 42, "affected_attrs": ["athleticism", "takedown_power"]},
    "rib_injury": {"base_severity": 0.5, "recovery_days": 30, "affected_attrs": ["striking_power", "cardio"]},
}


class HealthSystem:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.medical_suspension: Optional[datetime] = None
        self.concussion_count = 0  # Track cumulative concussions
        self.last_fight_injury_severity = 0.0

    def add_injury(self, injury_type: str, severity_mult: float = 1.0, game_date: datetime = None) -> Dict:
        if injury_type not in INJURY_TYPES:
            return {}
        info = INJURY_TYPES[injury_type]
        # Injury severity scales with how much damage was taken
        severity = min(1.0, info["base_severity"] * severity_mult)
        recovery_days = int(info["recovery_days"] * (0.5 + severity))
        now = game_date or datetime.now()
        injury = {
            "type": injury_type,
            "severity": severity,
            "affected_attrs": info["affected_attrs"],
            "recovery_end": now + timedelta(days=recovery_days)
        }
        self.fighter.add_injury(injury_type, severity, info["affected_attrs"], recovery_days, game_date)
        if severity >= 0.6:
            self.medical_suspension = injury["recovery_end"]

        # Track concussion legacy
        if injury_type == "concussion":
            self.concussion_count += 1
            # Cumulative concussions increase future KO susceptibility
            self.fighter.attributes["durability"] = max(0, self.fighter.attributes["durability"] - self.concussion_count * 2)

        self.last_fight_injury_severity = severity
        return injury

    def add_medical_suspension(self, days: int, reason: str = "medical", game_date: datetime = None):
        now = game_date or datetime.now()
        end = now + timedelta(days=days)
        if not self.medical_suspension or end > self.medical_suspension:
            self.medical_suspension = end

    def get_medical_suspension_days(self, game_date: datetime = None) -> int:
        if not self.medical_suspension:
            return 0
        now = game_date or datetime.now()
        remaining = (self.medical_suspension - now).days
        return max(0, remaining)

    def recover(self, game_date: datetime = None):
        now = game_date or datetime.now()
        self.fighter.recover_injuries(game_date)
        if self.medical_suspension and self.medical_suspension <= now:
            self.medical_suspension = None

    def get_active_injuries(self, game_date: datetime = None) -> List[Dict]:
        self.recover(game_date)
        return self.fighter.injuries

    def is_cleared_to_fight(self, game_date: datetime = None) -> bool:
        self.recover(game_date)
        return len(self.fighter.injuries) == 0 and not self.medical_suspension

    @staticmethod
    def get_ring_rust_penalty(months_inactive: int) -> float:
        if months_inactive <= 6:
            return 0.0
        return min(0.25, (months_inactive - 6) * 0.03)

    @staticmethod
    def get_medical_suspension_duration(method: str, severity: float = 0.5) -> int:
        if "KO" in method:
            return max(30, int(severity * 90))
        elif "TKO" in method:
            return max(14, int(severity * 60))
        elif "Submission" in method:
            return 14
        else:
            return 7

    def get_post_fight_injury_report(self, method: str, fight_damage: float) -> Dict:
        """Generate post-fight injury assessment based on fight outcome."""
        report = {"injuries": [], "medical_suspension_days": 0}

        # KO/TKO fighters need longer recovery
        if "KO" in method or "TKO" in method:
            report["medical_suspension_days"] = max(30, int(fight_damage * 0.5))

        # Generate injuries based on fight severity
        if fight_damage > 30:
            # High damage fight — risk of cuts, bruising
            if random.random() < 0.4:
                report["injuries"].append({
                    "type": "cut",
                    "severity": min(0.8, fight_damage / 100),
                    "recovery_days": 7
                })
            if random.random() < 0.3:
                report["injuries"].append({
                    "type": "swelling",
                    "severity": min(0.6, fight_damage / 150),
                    "recovery_days": 5
                })

        return report