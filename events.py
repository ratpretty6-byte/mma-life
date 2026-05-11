from typing import Dict, List, Optional
from datetime import datetime
from fighter import Fighter
from promotion import Promotion
import random

class FightBooking:
    def __init__(self, fighter1: Fighter, fighter2: Fighter, date: datetime, weight_class: str, promotion: Promotion, is_title_fight: bool = False):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.date = date
        self.weight_class = weight_class
        self.promotion = promotion
        self.is_title_fight = is_title_fight
        self.fight_position = "prelim"
        self.status = "announced"
        self.phase = "announced"
        self.winner = None
        self.method = None
        self.round = None
        self.cancellation_reason = None
        self.bonuses = []
        self.fight_stats: Dict = {}

    def cancel(self, reason: str = "injury"):
        self.status = "cancelled"
        self.cancellation_reason = reason

    def advance_phase(self) -> str:
        phases = ["announced", "press_conference", "open_workouts", "weigh_ins", "fight", "completed"]
        current_idx = phases.index(self.phase) if self.phase in phases else 0
        if current_idx < len(phases) - 1:
            self.phase = phases[current_idx + 1]
        return self.phase

    def set_fight_position(self, rank: int, is_title: bool):
        if is_title:
            self.fight_position = "main_event"
        elif rank <= 5:
            self.fight_position = "main_card"
        else:
            self.fight_position = "prelim"

    def complete(self, winner: Fighter, method: str, round: Optional[int] = None, fight_stats: Dict = None):
        self.status = "completed"
        self.phase = "completed"
        self.winner = winner
        self.method = method
        self.round = round
        self.fight_stats = fight_stats or {}

        if winner:
            loser = self.fighter2 if winner == self.fighter1 else self.fighter1
            winner.wins += 1
            loser.losses += 1
            winner.update_streaks(True)
            loser.update_streaks(False)
            if "KO" in method or "TKO" in method:
                winner.knockouts += 1
            elif "Submission" in method:
                winner.submissions += 1
            # Shake ring rust on win
            winner.shake_ring_rust()
            loser.shake_ring_rust()
        else:
            self.fighter1.draws += 1
            self.fighter2.draws += 1
        self.promotion.update_rankings()

    def record_round_stats(self, round_num: int, stats: Dict):
        """Record per-round statistics for enhanced scoring and news."""
        if "rounds" not in self.fight_stats:
            self.fight_stats["rounds"] = {}
        self.fight_stats["rounds"][round_num] = stats


class Event:
    def __init__(self, name: str, date: datetime, promotion: Promotion, location: str = ""):
        self.name = name
        self.date = date
        self.promotion = promotion
        self.location = location or ""
        self.fights: List[FightBooking] = []
        self.is_completed = False
        self.fight_of_night = None
        self.perf_of_night = None

    def add_fight(self, fight: FightBooking) -> bool:
        if fight.promotion != self.promotion:
            return False
        self.fights.append(fight)
        return True

    def cancel_fight(self, fight: FightBooking, reason: str = "injury"):
        if fight in self.fights:
            fight.cancel(reason)
            replacement = self._find_replacement(fight)
            if replacement:
                new_fight = FightBooking(
                    fighter1=fight.fighter1 if replacement != fight.fighter1 else fight.fighter2,
                    fighter2=replacement,
                    date=fight.date,
                    weight_class=fight.weight_class,
                    promotion=fight.promotion,
                    is_title_fight=False
                )
                self.fights.append(new_fight)

    def _find_replacement(self, original_fight: FightBooking) -> Optional[Fighter]:
        candidates = [
            f for f in self.promotion.fighters
            if f.weight_class == original_fight.weight_class
            and f not in [original_fight.fighter1, original_fight.fighter2]
            and f.weigh_in_pass
            and f.is_available()
        ]
        if not candidates:
            return None
        original_rank = min(original_fight.fighter1.rank, original_fight.fighter2.rank)
        candidates.sort(key=lambda f: abs(f.rank - original_rank))
        return candidates[0] if candidates else None

    def determine_bonuses(self) -> Optional[Dict]:
        """
        Enhanced bonus determination that considers:
        - Fight excitement (significant strikes, near-finishes)
        - Round finishes
        - Submission/KO quality
        - Fight of the Night vs Performance of the Night split
        """
        best_fight = None
        best_fight_score = 0
        best_perf = None
        best_perf_score = 0

        for f in self.fights:
            if f.status != "completed" or not f.winner:
                continue

            score = 50  # Base score

            # Bonus for early round finishes
            if f.round and f.round <= 2:
                score += 25
            elif f.round and f.round <= 1:
                score += 35

            # Method bonuses
            if "Submission" in (f.method or ""):
                score += 15
                # Back mount or rare submission = extra
                if "rear_naked" in (f.method or "").lower():
                    score += 10
            if "KO" in (f.method or ""):
                score += 20
            if "TKO (Referee" in (f.method or ""):
                score += 10  # Dominant performance

            # Fight stats bonus if available
            stats = f.fight_stats
            if stats:
                rounds = stats.get("rounds", {})
                total_sig_strikes = sum(
                    (r.get(f.winner.name, {}) if isinstance(r, dict) else {}).get("sig_strikes", 0)
                    for r in rounds.values()
                )
                if total_sig_strikes > 50:
                    score += 10

            # Update best performance
            if score > best_perf_score:
                best_perf_score = score
                best_perf = f

        # Find best fight (back-and-forth, significant strikes)
        if self.fights and not best_fight:
            best_fight = self.fights[0]
            best_fight_score = best_perf_score

        for f in self.fights:
            if f.status != "completed":
                continue
            # Fights going to decision with high activity are FOTN candidates
            if f.winner and f.round and f.round >= 3:
                score = (f.fighter1.wins + f.fighter2.wins) * 2
                fight_stats = f.fight_stats.get("rounds", {})
                # Check if fight was competitive
                if len(fight_stats) >= 3:
                    score += 15  # Competitive multi-round fight
                if score > best_fight_score:
                    best_fight_score = score
                    best_fight = f

        result = {}
        if best_fight:
            name = f"{best_fight.fighter1.name} vs {best_fight.fighter2.name}"
            self.fight_of_night = name
            result["fight_of_night"] = name
        if best_perf:
            self.perf_of_night = best_perf.winner.name
            result["perf_of_night"] = best_perf.winner.name
        return result if result else None


class EventSystem:
    def __init__(self):
        self.upcoming_events: List[Event] = []
        self.past_events: List[Event] = []

    def create_event(self, name: str, date: datetime, promotion: Promotion, location: str = "") -> Event:
        event = Event(name, date, promotion, location)
        self.upcoming_events.append(event)
        return event

    def book_fight(self, event: Event, fighter1: Fighter, fighter2: Fighter, is_title_fight: bool = False) -> Optional[FightBooking]:
        if event not in self.upcoming_events or fighter1.weight_class != fighter2.weight_class:
            return None
        fight = FightBooking(fighter1, fighter2, event.date, fighter1.weight_class, event.promotion, is_title_fight)
        fight.set_fight_position(fighter1.rank if fighter1 in event.promotion.fighters else 999, is_title_fight)
        event.add_fight(fight)
        return fight

    def generate_card(self, event: Event, fighter: Fighter, promotion: Promotion):
        wc = fighter.weight_class
        ranked = promotion.rankings.get(wc, [])
        if len(ranked) >= 4:
            for i in range(0, min(len(ranked) - 1, 6), 2):
                f1 = ranked[i]
                f2 = ranked[i + 1]
                if f1 == fighter or f2 == fighter:
                    continue
                if not f1.is_available() or not f2.is_available():
                    continue
                fb = self.book_fight(event, f1, f2, is_title_fight=False)
                if fb:
                    fb.set_fight_position(min(f1.rank, f2.rank), False)

    def advance_time(self, game_date: datetime):
        for event in self.upcoming_events[:]:
            if event.date <= game_date:
                all_completed = all(
                    f.status == "completed" or f.status == "cancelled"
                    for f in event.fights
                )
                if all_completed:
                    self.upcoming_events.remove(event)
                    self.past_events.append(event)
                    event.is_completed = True

    def get_upcoming_fights_for(self, fighter: Fighter) -> List[FightBooking]:
        results = []
        for event in self.upcoming_events:
            for fight in event.fights:
                if fight.fighter1 == fighter or fight.fighter2 == fighter:
                    results.append(fight)
        return results