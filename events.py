from datetime import datetime
from typing import Dict, List, Optional

from fighter import Fighter
from promotion import Promotion

CARD_POSITION_LABELS = ["prelim", "main_card", "co_main", "main_event"]
FIGHT_WEEK_PHASES = ["announced", "press_conference", "open_workouts", "weigh_ins", "fight", "completed"]


def position_to_index(pos: str) -> int:
    return CARD_POSITION_LABELS.index(pos) if pos in CARD_POSITION_LABELS else 0


def card_bonus_for_position(position: str) -> float:
    return {"prelim": 0, "main_card": 2000, "co_main": 5000, "main_event": 10000}.get(position, 0)


class FightBooking:
    def __init__(self, fighter1: Fighter, fighter2: Fighter, date: datetime, weight_class: str, promotion: Promotion,
                 is_title_fight: bool = False, risk_level: str = "50-50"):
        self.fighter1 = fighter1
        self.fighter2 = fighter2
        self.date = date
        self.weight_class = weight_class
        self.promotion = promotion
        self.is_title_fight = is_title_fight
        self.risk_level = risk_level
        self.fight_position = "prelim"
        self.status = "announced"
        self._phase_offset = 0
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
        if self._phase_offset < len(FIGHT_WEEK_PHASES) - 1:
            self._phase_offset += 1
        return self.phase

    @property
    def phase(self) -> str:
        return FIGHT_WEEK_PHASES[self._phase_offset] if self._phase_offset < len(FIGHT_WEEK_PHASES) else "completed"

    def set_fight_position(self, position: str):
        if position in CARD_POSITION_LABELS:
            self.fight_position = position

    def get_card_position_index(self) -> int:
        return position_to_index(self.fight_position)

    def complete(self, winner: Fighter, method: str, round: Optional[int] = None, fight_stats: Dict = None):
        self.status = "completed"
        self._phase_offset = len(FIGHT_WEEK_PHASES) - 1
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
            winner.shake_ring_rust()
            loser.shake_ring_rust()
        else:
            self.fighter1.draws += 1
            self.fighter2.draws += 1
        self.promotion.update_rankings()

    def record_round_stats(self, round_num: int, stats: Dict):
        if "rounds" not in self.fight_stats:
            self.fight_stats["rounds"] = {}
        self.fight_stats["rounds"][round_num] = stats

    def card_bonus(self) -> float:
        return card_bonus_for_position(self.fight_position)


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
        best_fight = None
        best_perf = None
        best_perf_score = 0
        best_fight_score = 0

        for f in self.fights:
            if f.status != "completed" or not f.winner:
                continue
            score = 50
            if f.round and f.round <= 2:
                score += 25
            if f.round and f.round <= 1:
                score += 35
            if "Submission" in (f.method or ""):
                score += 15
            if "KO" in (f.method or ""):
                score += 20
            if "TKO (Referee" in (f.method or ""):
                score += 10
            stats = f.fight_stats
            if stats:
                rounds = stats.get("rounds", {})
                total_sig_strikes = sum(
                    (r.get(f.winner.name, {}) if isinstance(r, dict) else {}).get("sig_strikes", 0)
                    for r in rounds.values()
                )
                if total_sig_strikes > 50:
                    score += 10
            if score > best_perf_score:
                best_perf_score = score
                best_perf = f

        for f in self.fights:
            if f.status != "completed":
                continue
            if f.winner and f.round and f.round >= 3:
                score = (f.fighter1.wins + f.fighter2.wins) * 2
                fight_stats = f.fight_stats.get("rounds", {})
                if len(fight_stats) >= 3:
                    score += 15
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

    def get_sorted_fights(self) -> List[FightBooking]:
        return sorted(self.fights, key=lambda f: f.get_card_position_index())


class EventSystem:
    def __init__(self):
        self.upcoming_events: List[Event] = []
        self.past_events: List[Event] = []

    def create_event(self, name: str, date: datetime, promotion: Promotion, location: str = "") -> Event:
        event = Event(name, date, promotion, location)
        self.upcoming_events.append(event)
        return event

    def book_fight(self, event: Event, fighter1: Fighter, fighter2: Fighter,
                   is_title_fight: bool = False, risk_level: str = "50-50") -> Optional[FightBooking]:
        if event not in self.upcoming_events or fighter1.weight_class != fighter2.weight_class:
            return None
        fight = FightBooking(fighter1, fighter2, event.date, fighter1.weight_class, event.promotion,
                             is_title_fight, risk_level)
        event.add_fight(fight)
        return fight

    def generate_card(self, event: Event, player_fb: FightBooking, promotion: Promotion, player: Fighter):
        wc = player.weight_class
        ranked = promotion.rankings.get(wc, [])
        available = [f for f in ranked if f.is_available() and f != player and f != (player_fb.fighter1 if player_fb.fighter2 == player else player_fb.fighter2)]
        import random
        random.shuffle(available)

        # Sort into positions
        positions = []
        # Main event is the player's fight (or the best other fight)
        player_fb.set_fight_position("main_event" if player_fb.risk_level == "sacrifice" else self._auto_position(player))
        positions.append(player_fb)

        # Co-main: top available fighters
        if len(available) >= 2:
            fb = self.book_fight(event, available[0], available[1])
            if fb:
                fb.set_fight_position("co_main")
                positions.append(fb)

        # Main card: 3 fights
        idx = 2
        for _ in range(3):
            if idx + 1 < len(available):
                fb = self.book_fight(event, available[idx], available[idx + 1])
                if fb:
                    fb.set_fight_position("main_card")
                    positions.append(fb)
                idx += 2

        # Prelims: 3-4 fights
        for _ in range(4):
            if idx + 1 < len(available):
                fb = self.book_fight(event, available[idx], available[idx + 1])
                if fb:
                    fb.set_fight_position("prelim")
                    positions.append(fb)
                idx += 2

    def _auto_position(self, player: Fighter) -> str:
        pop = getattr(player, "popularity", 0)
        rank = player.rank
        if rank <= 2 or pop >= 70:
            return "main_event"
        if rank <= 4 or pop >= 50:
            return "co_main"
        if rank <= 8 or pop >= 30:
            return "main_card"
        return "prelim"

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
