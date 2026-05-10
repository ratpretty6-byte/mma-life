from typing import Dict, List, Optional, Tuple
from datetime import datetime
from fighter import Fighter
from promotion import Promotion
from fight import Fight
from events import EventSystem
import random
import copy

class WorldSimulator:
    def __init__(self, promotions: List[Promotion]):
        self.promotions = promotions

    def simulate_month(self, game_date: datetime, event_sys: EventSystem) -> List[Dict]:
        results = []
        for promo in self.promotions:
            for wc in promo.weight_classes:
                wc_results = self._simulate_weight_class(promo, wc, game_date, event_sys)
                results.extend(wc_results)
            promo.update_rankings()
        return results

    def _simulate_weight_class(self, promo: Promotion, wc: str, game_date: datetime, event_sys: EventSystem) -> List[Dict]:
        fighters = promo.rankings.get(wc, [])
        champion = promo.champions.get(wc)
        booked = set()
        if event_sys:
            for ev in event_sys.upcoming_events:
                for fb in ev.fights:
                    booked.add(fb.fighter1.name)
                    booked.add(fb.fighter2.name)

        available = [f for f in fighters if f.is_available(game_date) and f.name not in booked]
        if len(available) < 2:
            return []

        results = []

        if champion and champion in available:
            available.remove(champion)
            contenders = [f for f in available if f.rank < 10 or f.win_streak >= 3]
            if contenders:
                opponent = max(contenders, key=lambda f: f.rank if f.rank != 1000 else 9999)
                available.remove(opponent)
                result = self._simulate_fight(champion, opponent, promo, wc, True, game_date, event_sys)
                results.append(result)

        sorted_f = sorted(available, key=lambda f: f.rank if f.rank != 1000 else 9999)
        num_fights = min(3, len(sorted_f) // 2)
        for i in range(num_fights):
            idx = i * 2
            if idx + 1 >= len(sorted_f):
                break
            f1 = sorted_f[idx]
            f2 = sorted_f[idx + 1]
            result = self._simulate_fight(f1, f2, promo, wc, False, game_date, event_sys)
            results.append(result)

        return results

    def _simulate_fight(self, f1: Fighter, f2: Fighter, promo: Promotion, wc: str, is_title: bool, game_date: datetime, event_sys: EventSystem) -> Dict:
        f1_copy = copy.deepcopy(f1)
        f2_copy = copy.deepcopy(f2)
        rounds = 5 if is_title else 3
        fight = Fight(f1_copy, f2_copy, rounds=rounds, is_title_fight=is_title)
        fight.simulate_full()

        winner = fight.winner
        method = fight.win_method or "Draw"
        win_round = fight.win_round or 0

        news_item = {
            "type": "fight_result",
            "promotion": promo.name,
            "promotion_tier": promo.tier_name,
            "weight_class": wc,
            "is_title_fight": is_title,
            "fighter1": f1.name,
            "fighter2": f2.name,
            "winner": winner.name if winner else "Draw",
            "loser": f2.name if winner == f1_copy else (f1.name if winner else None),
            "method": method,
            "round": win_round,
            "rating1": f1.get_overall_rating(),
            "rating2": f2.get_overall_rating(),
            "was_upset": False,
        }

        if winner:
            loser = f2 if winner == f1_copy else f1
            winner_real = f1 if winner == f1_copy else f2
            loser_real = f2 if winner == f1_copy else f1

            news_item["was_upset"] = loser.get_overall_rating() > winner.get_overall_rating() + 5

            winner_real.wins += 1
            winner_real.knockouts += 1 if "KO" in method or "TKO" in method else 0
            winner_real.submissions += 1 if "Submission" in method else 0
            winner_real.update_streaks(True)

            loser_real.losses += 1
            loser_real.update_streaks(False)

            if is_title:
                promo.set_champion(winner_real)
                news_item["title_changed"] = True
        else:
            f1.draws += 1
            f2.draws += 1

            news_item["title_changed"] = False

        inj = self._maybe_injure_loser(winner, f2 if winner == f1_copy else f1 if winner else None, game_date)
        if inj:
            news_item["injury"] = inj

        return news_item

    def _maybe_injure_loser(self, winner: Optional[Fighter], loser: Optional[Fighter], game_date: datetime) -> Optional[Dict]:
        if not loser or random.random() > 0.15:
            return None
        injuries = [
            {"type": "cut", "severity": 0.4, "affected_attrs": ["striking_accuracy"], "recovery_days": 14},
            {"type": "concussion", "severity": 0.6, "affected_attrs": ["mental_toughness", "fight_iq"], "recovery_days": 30},
            {"type": "broken_bone", "severity": 0.7, "affected_attrs": ["striking_power", "hand_speed"], "recovery_days": 60},
            {"type": "strain", "severity": 0.3, "affected_attrs": ["athleticism"], "recovery_days": 10},
        ]
        inj = random.choice(injuries)
        loser.add_injury(inj["type"], inj["severity"], inj["affected_attrs"], inj["recovery_days"], game_date)
        return inj
