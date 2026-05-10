from typing import Dict, List, Optional, Tuple
from fighter import Fighter
from promotion import Promotion, Contract
from events import FightBooking
from datetime import datetime, timedelta
import utils
import random

class Rivalry:
    def __init__(self, fighter1: Fighter, fighter2: Fighter):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.fights: List[FightBooking] = []
        self.intensity = 0.0
        self.fan_interest = 0.0
        self.trilogy = False

    def add_fight(self, fight: FightBooking):
        self.fights.append(fight)
        self.intensity = min(1.0, self.intensity + 0.25)
        self.fan_interest = min(1.0, self.fan_interest + 0.2)
        if len(self.fights) >= 3:
            self.trilogy = True
            self.fan_interest = min(1.0, self.fan_interest + 0.3)

    def get_record(self, fighter: Fighter) -> str:
        wins = sum(1 for f in self.fights if f.winner == fighter)
        return f"{wins}-{len(self.fights) - wins}"

    def get_opponent(self, fighter: Fighter) -> Fighter:
        return self.fighter2 if fighter == self.fighter1 else self.fighter1

class CareerSystem:
    def __init__(self, fighter: Fighter):
        self.fighter = fighter
        self.current_promotion: Optional[Promotion] = None
        self.current_tier_index: int = -1
        self.contract: Optional[Contract] = None
        self.rivalries: List[Rivalry] = []
        self.title_defenses = 0
        self.career_earnings = 0.0
        self.retirement_countdown = 0
        self._milestones: List[str] = []
        self._fastest_ko_round = 99
        self._most_consecutive_wins = 0
        self._longest_win_streak = 0

    def sign_with_promotion(self, promotion: Promotion, fights: int = 4, game_date: datetime = None) -> bool:
        if self.current_promotion:
            self.current_promotion.release_fighter(self.fighter)
        self.contract = promotion.sign_fighter(self.fighter, fights, game_date)
        self.current_promotion = promotion
        if promotion.tier_name == "Regional":
            self.current_tier_index = 2
        elif promotion.tier_name == "National":
            self.current_tier_index = 1
        elif promotion.tier_name == "World":
            self.current_tier_index = 0
        return True

    def check_title_shot(self) -> bool:
        if not self.current_promotion:
            return False
        rank = self.fighter.rank
        wc = self.fighter.weight_class
        champion = self.current_promotion.champions.get(wc)
        if rank <= 2:
            return True
        return False

    def win_title(self):
        if self.current_promotion:
            self.current_promotion.set_champion(self.fighter)
            self.title_defenses = 0
            if self.contract:
                self.contract.renegotiate(self.fighter.rank, self.fighter.win_streak, True)

    def defend_title(self):
        self.title_defenses += 1
        if self.contract:
            self.contract.renegotiate(self.fighter.rank, self.fighter.win_streak, True)

    def add_rivalry(self, other_fighter: Fighter) -> Rivalry:
        for riv in self.rivalries:
            if other_fighter in [riv.fighter1, riv.fighter2]:
                return riv
        rivalry = Rivalry(self.fighter, other_fighter)
        self.rivalries.append(rivalry)
        return rivalry

    def get_or_create_rivalry(self, opponent: Fighter) -> Rivalry:
        for riv in self.rivalries:
            if opponent in [riv.fighter1, riv.fighter2]:
                return riv
        return self.add_rivalry(opponent)

    def check_promotion_offer(self, promotions: Tuple[Promotion, Promotion, Promotion] = None) -> Optional[Promotion]:
        if self.current_tier_index <= 0:
            return None
        if not self.current_promotion:
            return None
        if self.fighter.rank == 1 and promotions:
            next_tier = promotions[self.current_tier_index - 1]
            rating = self.fighter.get_overall_rating()
            if rating >= 50:
                return next_tier
        return None

    def try_retire(self, force: bool = False, game_date: datetime = None) -> bool:
        now = game_date or datetime.now()
        if force or self.fighter.age >= 40:
            self.fighter.retired = True
            self.fighter.retirement_date = now
            return True
        if self.fighter.loss_streak >= 3 and self.fighter.age >= 35:
            if random.random() < 0.3:
                self.fighter.retired = True
                self.fighter.retirement_date = now
                return True
        return False

    def try_comeback(self, game_date: datetime = None) -> bool:
        if not self.fighter.retired:
            return False
        if self.fighter.retirement_date:
            now = game_date or datetime.now()
            years_retired = (now - self.fighter.retirement_date).days / 365
            if years_retired < 2:
                self.fighter.retired = False
                self.fighter.months_inactive = max(12, self.fighter.months_inactive)
                return True
        return False

    def get_summary(self) -> Dict:
        return {
            "record": self.fighter.get_record_string(),
            "peak_rank": self.fighter.peak_rank,
            "title_defenses": self.title_defenses,
            "career_earnings": self.career_earnings,
            "rivalries": len(self.rivalries),
            "promotion": self.current_promotion.name if self.current_promotion else "Free Agent",
            "rank": self.fighter.rank,
            "age": self.fighter.age,
            "retired": self.fighter.retired,
            "milestones": getattr(self, '_milestones', []),
        }

    def check_milestones(self, won: bool, method: str, round_num: int) -> List[str]:
        new_milestones = []
        wc = self.fighter.weight_class

        if won:
            self._most_consecutive_wins += 1
            if self._most_consecutive_wins > self._longest_win_streak:
                self._longest_win_streak = self._most_consecutive_wins
        else:
            self._most_consecutive_wins = 0

        total_wins = self.fighter.wins

        if total_wins == 1:
            new_milestones.append(f"First career win — the journey begins!")
        if total_wins == 5:
            new_milestones.append(f"5 wins — establishing yourself in the {wc} division!")
        if total_wins == 10:
            new_milestones.append(f"10 wins — double digits! The division is taking notice.")
        if total_wins == 20:
            new_milestones.append(f"20 wins — a true veteran of the sport!")

        if self._longest_win_streak == 3:
            new_milestones.append(f"3 wins in a row — first real winning streak!")
        if self._longest_win_streak == 5:
            new_milestones.append(f"5 straight wins — contender status!")
        if self._longest_win_streak == 7:
            new_milestones.append(f"7 fight win streak — you're a force to be reckoned with!")
        if self._longest_win_streak == 10:
            new_milestones.append(f"10 IN A ROW! Historic dominance in the {wc} division!")

        if "KO" in method or "TKO" in method:
            if round_num and round_num < self._fastest_ko_round:
                self._fastest_ko_round = round_num
                new_milestones.append(f"Fastest finish yet! {method} in round {round_num}!")

        if self.title_defenses == 1:
            new_milestones.append("First title defense successful! You're a legitimate champion.")
        if self.title_defenses == 3:
            new_milestones.append("3 title defenses — dominant champion!")
        if self.title_defenses == 5:
            new_milestones.append(f"5 TITLE DEFENSES! One of the greatest {wc} champions ever!")

        if self.fighter.peak_rank == 5:
            new_milestones.append("Cracked the top 5! You're fighting the best in the world.")
        if self.fighter.peak_rank == 1 and self.fighter.rank <= 1:
            new_milestones.append("YOU'RE THE CHAMPION! All that work has paid off!")

        if self._milestones:
            existing = set(self._milestones)
            new_milestones = [m for m in new_milestones if m not in existing]
        self._milestones.extend(new_milestones)
        return new_milestones

    def get_rivalry_summary(self) -> List[str]:
        lines = []
        for riv in self.rivalries:
            opp = riv.get_opponent(self.fighter)
            record = riv.get_record(self.fighter)
            tril = " (Trilogy)" if riv.trilogy else ""
            lines.append(f"{opp.name}: {record}{tril} (intensity: {riv.intensity:.0%})")
        return lines
