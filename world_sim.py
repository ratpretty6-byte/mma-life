import copy
import random
from datetime import datetime
from typing import Dict, List, Optional

import utils
from events import EventSystem
from fight import Fight
from fighter import Fighter
from generator import generate_single_fighter
from promotion import Promotion


class WorldSimulator:
    def __init__(self, promotions: List[Promotion], all_fighters: List = None):
        self.promotions = promotions
        self.all_fighters = all_fighters
        self.month_counter = 0
        self._init_champions()

    def _init_champions(self):
        for promo in self.promotions:
            for wc in promo.weight_classes:
                if wc not in promo.champions or promo.champions.get(wc) is None:
                    ranked = promo.rankings.get(wc, [])
                    if ranked:
                        promo.champions[wc] = ranked[0]
            promo.update_rankings()

    def simulate_month(self, game_date: datetime, event_sys: EventSystem) -> List[Dict]:
        results = []
        self.month_counter += 1

        # Promotion mobility checks (every 2 months)
        if self.month_counter % 2 == 0:
            mobility_news = self._check_promotion_mobility(game_date)
            results.extend(mobility_news)

        for promo in self.promotions:
            for wc in promo.weight_classes:
                wc_results = self._simulate_weight_class(promo, wc, game_date, event_sys)
                results.extend(wc_results)
            promo.update_rankings(game_date)

        if self.month_counter % 4 == 0:
            prospect_news = self._generate_prospects(game_date)
            results.extend(prospect_news)

        replenish_news = self._replenish_thin_divisions(game_date)
        results.extend(replenish_news)

        self._simulate_aging()

        retirement_news = self._simulate_retirements(game_date)
        results.extend(retirement_news)

        return results

    def _check_promotion_mobility(self, game_date: datetime) -> List[Dict]:
        news = []
        tiers = {"Regional": [], "National": [], "World": []}
        for p in self.promotions:
            tiers.setdefault(p.tier_name, []).append(p)

        # Move top Regional fighters up to National
        regional_promos = tiers.get("Regional", [])
        national_promos = tiers.get("National", [])
        world_promos = tiers.get("World", [])

        for rp in regional_promos:
            for wc in rp.weight_classes:
                if not rp.rankings.get(wc):
                    continue
                top = rp.rankings[wc][0]
                if getattr(top, 'is_player', False):
                    continue
                if top.win_streak >= 3 and top.is_available(game_date) and not top.retired:
                    if national_promos:
                        target = random.choice(national_promos)
                        rp.release_fighter(top)
                        target.sign_fighter(top, game_date=game_date)
                        news.append({
                            "type": "fighter_moved",
                            "fighter": top.name,
                            "from": rp.name,
                            "to": target.name,
                            "direction": "up",
                            "reason": "called_up",
                        })

        # Move top National fighters up to World
        for np in national_promos:
            for wc in np.weight_classes:
                if not np.rankings.get(wc):
                    continue
                top = np.rankings[wc][0]
                if getattr(top, 'is_player', False):
                    continue
                if top.win_streak >= 2 and top.get_overall_rating() >= 65 and top.is_available(game_date) and not top.retired:
                    if world_promos:
                        target = random.choice(world_promos)
                        np.release_fighter(top)
                        target.sign_fighter(top, game_date=game_date)
                        news.append({
                            "type": "fighter_moved",
                            "fighter": top.name,
                            "from": np.name,
                            "to": target.name,
                            "direction": "up",
                            "reason": "called_up",
                        })

        # Demote fighters on 3+ loss streaks
        for tier_name, promo_list in [("World", world_promos), ("National", national_promos)]:
            down_tier = "National" if tier_name == "World" else "Regional"
            down_promos = tiers.get(down_tier, [])
            for p in promo_list:
                for wc in p.weight_classes:
                    for f in p.fighters[:]:
                        if getattr(f, 'is_player', False):
                            continue
                        if f.loss_streak >= 3 and f.rank > 3 and not f.retired and p.champions.get(wc) != f:
                            if down_promos:
                                target = random.choice(down_promos)
                                p.release_fighter(f)
                                target.sign_fighter(f, game_date=game_date)
                                news.append({
                                    "type": "fighter_moved",
                                    "fighter": f.name,
                                    "from": p.name,
                                    "to": target.name,
                                    "direction": "down",
                                    "reason": "demoted",
                                })
                                break
        return news

    def _generate_prospects(self, game_date: datetime) -> List[Dict]:
        news = []
        num_prospects = random.randint(2, 3)
        for _ in range(num_prospects):
            wc_idx = random.choices(range(8), weights=[0.10, 0.12, 0.14, 0.18, 0.16, 0.14, 0.10, 0.06])[0]
            wc = utils.WEIGHT_CLASSES[wc_idx]
            weight = random.randint(wc["min"], wc["max"])
            fighter = generate_single_fighter(weight, skill_mean=random.gauss(25, 5), skill_std=random.gauss(10, 3))
            fighter.age = random.randint(18, 23)
            fighter.months_inactive = 0
            for promo in self.promotions:
                if promo.tier_name == "Regional":
                    promo.sign_fighter(fighter)
                    if self.all_fighters is not None:
                        self.all_fighters.append(fighter)
                    news.append({
                        "type": "prospect",
                        "fighter": fighter.name,
                        "age": fighter.age,
                        "weight_class": wc["name"],
                        "promotion": promo.name,
                    })
                    break
        return news

    def _replenish_thin_divisions(self, game_date: datetime) -> List[Dict]:
        """Top up any per-promotion weight class that has fewer than 15 active fighters."""
        news = []
        for promo in self.promotions:
            for wc in promo.weight_classes:
                active = [f for f in promo.rankings.get(wc, []) if not f.retired]
                if len(active) >= 15:
                    continue
                to_create = 20 - len(active)
                wc_data = next((wc_item for wc_item in utils.WEIGHT_CLASSES if wc_item["name"] == wc), None)
                if not wc_data:
                    continue
                for _ in range(to_create):
                    fighter = generate_single_fighter(
                        random.randint(wc_data["min"], wc_data["max"]),
                        skill_mean=utils.gaussian_random(45, 10, 25, 65),
                        skill_std=utils.gaussian_random(14, 3, 6, 20)
                    )
                    fighter.age = random.randint(20, 30)
                    fighter.months_inactive = 0
                    promo.sign_fighter(fighter)
                    if self.all_fighters is not None:
                        self.all_fighters.append(fighter)
                promo.update_rankings()
                if to_create > 0 and self.month_counter % 3 == 0:
                    news.append({
                        "type": "replenish",
                        "promotion": promo.name,
                        "weight_class": wc,
                        "count": to_create,
                    })
        return news

    def _simulate_aging(self):
        for promo in self.promotions:
            for fighter in promo.fighters:
                if not fighter.retired:
                    fighter.age += 1 / 12.0

    def _simulate_retirements(self, game_date: datetime) -> List[Dict]:
        news = []
        for promo in self.promotions:
            for fighter in promo.fighters[:]:
                if fighter.retired:
                    continue
                if fighter.age >= 38:
                    fighter.retired = True
                    fighter.retirement_date = game_date
                    news.append({
                        "type": "retirement",
                        "fighter": fighter.name,
                        "age": int(fighter.age),
                        "record": fighter.get_record_string(),
                        "legacy_score": 0,
                    })
                elif fighter.age >= 35 and fighter.loss_streak >= 3 and random.random() < 0.25:
                    fighter.retired = True
                    fighter.retirement_date = game_date
                    news.append({
                        "type": "retirement",
                        "fighter": fighter.name,
                        "age": int(fighter.age),
                        "record": fighter.get_record_string(),
                        "legacy_score": 0,
                    })
                elif fighter.career_ko_losses >= 3 and random.random() < 0.10:
                    fighter.retired = True
                    fighter.retirement_date = game_date
                    news.append({
                        "type": "retirement",
                        "fighter": fighter.name,
                        "age": int(fighter.age),
                        "record": fighter.get_record_string(),
                        "legacy_score": 0,
                    })
        return news

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

        # Track career damage
        for orig, f_copy in [(f1, f1_copy), (f2, f2_copy)]:
            head_pct = f_copy.get_group_health("head")
            body_pct = f_copy.get_group_health("body")
            damage_taken = (100 - head_pct) * 0.5 + (100 - body_pct) * 0.3
            orig.career_damage_taken = getattr(orig, "career_damage_taken", 0.0) + damage_taken

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
