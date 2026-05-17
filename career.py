import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import utils
from events import FightBooking
from fighter import Fighter
from news import StorylineTracker
from promotion import Contract, Promotion


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

AWARD_CATEGORIES = ["Fighter of the Year", "Knockout of the Year", "Submission of the Year",
                     "Fight of the Year", "Comeback of the Year", "Rookie of the Year"]

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
        self.storyline_tracker = StorylineTracker()
        self.season_months = 0
        self._awards: Dict[str, int] = {}
        self._yearly_wins = 0
        self._yearly_kos = 0
        self._yearly_subs = 0
        self._best_ko_this_year = None
        self._best_sub_this_year = None
        self._best_fight_this_year = None
        self._current_season_fights: List[Dict] = []

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

    def check_promotion_offer(self, promotions: List[Promotion] = None) -> Optional[Promotion]:
        if self.current_tier_index <= 0:
            return None
        if not self.current_promotion:
            return None
        if self.fighter.rank == 1 and promotions:
            current_tier = self.current_promotion.tier_name
            if current_tier == "Regional":
                next_tier_name = "National"
            elif current_tier == "National":
                next_tier_name = "World"
            else:
                return None
            next_tier_promos = [p for p in promotions if p.tier_name == next_tier_name]
            if next_tier_promos:
                rating = self.fighter.get_overall_rating()
                if rating >= 50:
                    return next_tier_promos[0]
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

    def advance_season(self, game_date: datetime) -> Optional[Dict]:
        self.season_months += 1
        if game_date:
            if not getattr(self, '_awards_this_year', False):
                late_dec = game_date.month == 12 and game_date.day >= 25
                early_jan = game_date.month == 1 and game_date.day <= 5
                if late_dec or early_jan:
                    self._awards_this_year = True
                    return self._calculate_year_end_awards()
            if game_date.month == 1 and game_date.day > 5:
                self._awards_this_year = False
        return None

    def record_season_fight(self, won: bool, method: str, round_num: int, opponent: Fighter, is_title: bool = False):
        self._current_season_fights.append({
            "won": won, "method": method, "round": round_num,
            "opponent": opponent.name, "opponent_rating": opponent.get_overall_rating(),
            "is_title": is_title, "date": datetime.now(),
        })
        self._yearly_wins += 1 if won else 0
        if "KO" in method:
            self._yearly_kos += 1
            ko_rd = round_num or 99
            if not self._best_ko_this_year or ko_rd < self._best_ko_this_year.get("round", 99):
                self._best_ko_this_year = {"opponent": opponent.name, "round": round_num}
        if "Submission" in method:
            self._yearly_subs += 1
            self._best_sub_this_year = self._best_sub_this_year or {"opponent": opponent.name, "method": method}
        if round_num and round_num >= 3 and won:
            fight_score = (opponent.get_overall_rating() if opponent.get_overall_rating() > 50 else 0)
            if not self._best_fight_this_year or fight_score > self._best_fight_this_year.get("score", 0):
                self._best_fight_this_year = {"opponent": opponent.name, "round": round_num, "score": fight_score}

    def _calculate_year_end_awards(self) -> Dict:
        awards = {}
        if self._yearly_wins >= 5:
            awards["Fighter of the Year"] = 1
        if self._best_ko_this_year:
            awards["Knockout of the Year"] = 1
        if self._best_sub_this_year:
            awards["Submission of the Year"] = 1
        if self._best_fight_this_year:
            awards["Fight of the Year"] = 1
        if self._yearly_wins >= 3 and self.fighter.age <= 23:
            awards["Rookie of the Year"] = 1
        comeback = sum(1 for f in self._current_season_fights if not f["won"])
        if self._yearly_wins >= 3 and comeback >= 2:
            wins_after_loss = sum(1 for i, f in enumerate(self._current_season_fights)
                                   if not f["won"] and i + 1 < len(self._current_season_fights)
                                   and self._current_season_fights[i + 1]["won"])
            if wins_after_loss >= 1:
                awards["Comeback of the Year"] = 1

        for cat in awards:
            self._awards[cat] = self._awards.get(cat, 0) + 1
            self._milestones.append(f"{cat} — {self.fighter.name} wins {cat}!")
            if cat == "Fighter of the Year":
                self.fighter.attributes["charisma"] = utils.clamp(
                    self.fighter.attributes.get("charisma", 50) + 3, utils.ATTR_MIN, utils.ATTR_MAX)

        # Reset yearly counters
        self._yearly_wins = 0
        self._yearly_kos = 0
        self._yearly_subs = 0
        self._best_ko_this_year = None
        self._best_sub_this_year = None
        self._best_fight_this_year = None
        self._current_season_fights = []

        if awards:
            return {"type": "award", "awards": list(awards.keys()), "winner": self.fighter.name}
        return None

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
            new_milestones.append("First career win — the journey begins!")
        if total_wins == 5:
            new_milestones.append(f"5 wins — establishing yourself in the {wc} division!")
        if total_wins == 10:
            new_milestones.append("10 wins — double digits! The division is taking notice.")
        if total_wins == 20:
            new_milestones.append("20 wins — a true veteran of the sport!")

        if self._longest_win_streak == 3:
            new_milestones.append("3 wins in a row — first real winning streak!")
        if self._longest_win_streak == 5:
            new_milestones.append("5 straight wins — contender status!")
        if self._longest_win_streak == 7:
            new_milestones.append("7 fight win streak — you're a force to be reckoned with!")
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
