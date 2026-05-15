from typing import Dict, List, Optional, Tuple
from fighter import Fighter
from datetime import datetime, timedelta
import utils
import random

class Contract:
    def __init__(self, fighter: Fighter, promotion: 'Promotion', fights_remaining: int,
                 base_pay: float, win_bonus: float, performance_bonus: float = 5000.0,
                 champion: bool = False, game_date: datetime = None):
        self.fighter = fighter
        self.promotion = promotion
        self.fights_remaining = fights_remaining
        self.base_pay = base_pay
        self.win_bonus = win_bonus
        self.performance_bonus = performance_bonus
        self.signed_date = game_date or datetime.now()
        self.original_base_pay = base_pay
        self.champion = champion

    def complete_fight(self, won: bool, perf_bonus: bool = False) -> float:
        pay = self.base_pay
        if won:
            pay += self.win_bonus
        if perf_bonus:
            pay += self.performance_bonus
        self.fights_remaining = max(0, self.fights_remaining - 1)
        return pay

    def is_expired(self) -> bool:
        return self.fights_remaining <= 0

    def renegotiate(self, rank: int, win_streak: int, champion: bool = False):
        rank_factor = max(1, 51 - rank) / 50.0
        streak_bonus = 1.0 + (win_streak * 0.05)
        champ_mult = 2.0 if champion else 1.0
        new_base = self.original_base_pay * rank_factor * streak_bonus * champ_mult
        new_base = max(self.base_pay, new_base)
        self.base_pay = round(new_base, -2)
        self.win_bonus = self.base_pay * 0.5
        self.champion = champion
        return self.base_pay

    def get_details(self) -> str:
        expiry = "expired" if self.is_expired() else f"{self.fights_remaining} fights left"
        return (f"Base: {utils.format_currency(self.base_pay)} | "
                f"Win: {utils.format_currency(self.win_bonus)} | "
                f"Perf: {utils.format_currency(self.performance_bonus)} | "
                f"{expiry}")

class Promotion:
    def __init__(self, name: str, tier: Dict, weight_classes: List[str]):
        self.name = name
        self.tier_name = tier["name"]
        self.base_pay = tier["base_pay"]
        self.win_bonus = tier["win_bonus"]
        self.perf_bonus = tier["perf_bonus"]
        self.ranking_weight = tier["ranking_weight"]
        self.weight_classes = weight_classes
        self.fighters: List[Fighter] = []
        self.rankings: Dict[str, List[Fighter]] = {wc: [] for wc in weight_classes}
        self.champions: Dict[str, Optional[Fighter]] = {wc: None for wc in weight_classes}
        self.contracts: Dict[Fighter, Contract] = {}
        self._last_ranking_update: Dict[str, datetime] = {}
        self._mandatory_challenges: Dict[str, Fighter] = {}

    def _add_fighter_batch(self, fighter: Fighter):
        """Add a fighter without updating rankings (for batch imports)."""
        if fighter in self.fighters:
            return
        self.fighters.append(fighter)
        self.contracts[fighter] = Contract(fighter, self, 4, self.base_pay, self.base_pay * 0.5, self.perf_bonus)
        if fighter.weight_class in self.rankings:
            self.rankings[fighter.weight_class].append(fighter)
        fighter.current_contract = self.contracts[fighter]

    def sign_fighter(self, fighter: Fighter, fights: int = 4, game_date: datetime = None) -> Contract:
        if fighter in self.fighters:
            return self.contracts[fighter]
        self.fighters.append(fighter)

        rank_factor = max(1, 51 - len(self.rankings.get(fighter.weight_class, []))) / 50.0
        rating_factor = fighter.get_overall_rating() / 100.0
        adjusted_base = max(self.base_pay, self.base_pay * (0.5 + rating_factor) * rank_factor)
        adjusted_win = adjusted_base * 0.5

        contract = Contract(fighter, self, fights, round(adjusted_base, -1), round(adjusted_win, -1), self.perf_bonus, game_date=game_date)
        self.contracts[fighter] = contract

        if fighter.weight_class in self.rankings:
            self.rankings[fighter.weight_class].append(fighter)
            self.update_rankings()

        fighter.current_contract = contract
        return contract

    def release_fighter(self, fighter: Fighter):
        if fighter in self.fighters:
            self.fighters.remove(fighter)
        if fighter.weight_class in self.rankings and fighter in self.rankings[fighter.weight_class]:
            self.rankings[fighter.weight_class].remove(fighter)
        if fighter in self.contracts:
            del self.contracts[fighter]
        fighter.current_contract = None
        self.update_rankings()

    def update_rankings(self, game_date: datetime = None):
        for wc in self.weight_classes:
            fighters = self.rankings[wc]
            scored = []
            div_ratings = [f2.get_overall_rating() for f2 in fighters]
            for f in fighters:
                others = [r for r in div_ratings if r != f.get_overall_rating()]
                opp_ratings = others if others else [f.get_overall_rating()]
                sos = utils.calculate_strength_of_schedule(opp_ratings)

                # Momentum bonus for win streaks
                momentum_bonus = 0
                if f.win_streak >= 3:
                    momentum_bonus = 2
                if f.win_streak >= 5:
                    momentum_bonus = 5
                if f.win_streak >= 7:
                    momentum_bonus = 10
                if f.loss_streak >= 3:
                    momentum_bonus = -3
                if f.loss_streak >= 5:
                    momentum_bonus = -6

                # Inactivity penalty
                inactivity_penalty = 0
                if f.months_inactive > 4:
                    inactivity_penalty = min(5, int((f.months_inactive - 4) * 0.5))

                score = (f.wins * 3 + f.knockouts * 2 + f.submissions * 2
                         + f.win_streak * 5 - f.losses * 2 - f.loss_streak * 3
                         + sos * 10 + momentum_bonus - inactivity_penalty)
                scored.append((f, score))
            scored.sort(key=lambda x: (-x[1], x[0].name))
            champion = self.champions.get(wc)
            if champion:
                scored.sort(key=lambda x: (0 if x[0] == champion else 1, -x[1], x[0].name))
            self.rankings[wc] = [s[0] for s in scored]
            for idx, fighter in enumerate(self.rankings[wc], 1):
                prev_rank = fighter.rank
                fighter.rank = idx
                fighter.update_rank(idx)
            self._last_ranking_update[wc] = game_date or datetime.now()
        self._check_title_stripping(game_date)
        self._check_mandatory_challenges(game_date)

    def _check_title_stripping(self, game_date: datetime = None):
        for wc in self.weight_classes:
            champ = self.champions.get(wc)
            if champ and hasattr(champ, 'last_fight_date') and champ.last_fight_date:
                now = game_date or datetime.now()
                days_since_defense = (now - champ.last_fight_date).days
                if days_since_defense > 180:
                    contender = self.get_title_challenger(wc)
                    if contender:
                        self.set_champion(contender)
                        return {"type": "title_stripped", "fighter": champ.name, "new_champion": contender.name}

    def _check_mandatory_challenges(self, game_date: datetime = None):
        for wc in self.weight_classes:
            champ = self.champions.get(wc)
            if not champ:
                continue
            rankings = self.rankings.get(wc, [])
            if len(rankings) < 2:
                continue
            top_contender = rankings[1] if rankings[0] == champ else rankings[0]
            defenses_since_challenge = 0
            if hasattr(champ, 'last_title_defense_date') and champ.last_title_defense_date:
                now = game_date or datetime.now()
                days_since = (now - champ.last_title_defense_date).days
                defenses_since_challenge = max(0, days_since // 180)
            if defenses_since_challenge >= 3:
                self._mandatory_challenges[wc] = top_contender

    def is_undisputed_champion(self, fighter: Fighter, other_promotions: List['Promotion'] = None) -> bool:
        if not other_promotions:
            return False
        for promo in other_promotions:
            if promo.champions.get(fighter.weight_class) != fighter:
                return False
        return True

    def get_title_challenger(self, weight_class: str) -> Optional[Fighter]:
        if weight_class not in self.rankings or len(self.rankings[weight_class]) < 2:
            return None
        rankings = self.rankings[weight_class]
        champion = self.champions.get(weight_class)
        if champion and champion == rankings[0]:
            return rankings[1]
        return rankings[0]

    def set_champion(self, fighter: Fighter):
        if fighter.weight_class in self.champions:
            self.champions[fighter.weight_class] = fighter
        self.update_rankings()

    def get_contract_offer(self, fighter: Fighter, fights: int = 4, game_date: datetime = None) -> Contract:
        rank_factor = max(1, 51 - fighter.rank) / 50.0
        rating_factor = fighter.get_overall_rating() / 100.0
        adjusted_base = max(self.base_pay, self.base_pay * (0.5 + rating_factor) * rank_factor)
        adjusted_win = adjusted_base * 0.5
        return Contract(fighter, self, fights, round(adjusted_base, -1), round(adjusted_win, -1), self.perf_bonus, game_date=game_date)

    def get_ranked_fighters(self, weight_class: str, exclude: Optional[List[Fighter]] = None) -> List[Fighter]:
        if weight_class not in self.rankings:
            return []
        exclude = exclude or []
        return [f for f in self.rankings[weight_class] if f not in exclude]

    def get_available_opponents(self, fighter: Fighter, all_promotions: List['Promotion'] = None) -> List[Tuple[Fighter, str]]:
        if fighter.weight_class not in self.rankings:
            return []
        ranked = self.rankings[fighter.weight_class]
        if fighter not in ranked:
            return [(f, "unranked matchup") for f in ranked[:12]]

        idx = ranked.index(fighter)
        opponents = []
        nearby = ranked[max(0, idx-5):idx] + ranked[idx+1:idx+6]
        for opp in nearby:
            if opp.is_available():
                if opp.rank < fighter.rank:
                    diff_pts = fighter.rank - opp.rank
                    difficulty = "step up" if diff_pts >= 5 else ("tough test" if diff_pts >= 2 else "even matchup")
                elif opp.rank > fighter.rank:
                    diff_pts = opp.rank - fighter.rank
                    difficulty = "should win" if diff_pts >= 5 else ("pick em" if diff_pts >= 2 else "even matchup")
                else:
                    difficulty = "even matchup"
                opponents.append((opp, difficulty))

        # Champion fight: if fighter is rank 1 or 2 and a champion exists
        champion = self.champions.get(fighter.weight_class)
        if champion and champion.is_available() and champion != fighter and champion not in [o[0] for o in opponents]:
            if fighter.rank <= 2 or (self.tier_name == "Regional" and fighter.rank <= 5):
                opponents.append((champion, "title shot"))

        # Cross-tier opponents: if player is rank 1-5 in Regional, show top National fighters
        if all_promotions and self.tier_name == "Regional" and fighter.rank <= 5:
            for promo in all_promotions:
                if promo.tier_name == "National" and fighter.weight_class in promo.rankings:
                    nat_ranked = promo.rankings[fighter.weight_class][:6]
                    for opp in nat_ranked:
                        if opp.is_available() and opp not in [o[0] for o in opponents]:
                            opponents.append((opp, "prestige fight"))

        if self.tier_name in ("Regional", "National"):
            opponents = [o for o in opponents if o[0].nationality == fighter.nationality]
            if len(opponents) < 3:
                for opp in ranked:
                    if opp.nationality == fighter.nationality and opp.is_available() and opp != fighter:
                        opp_rank_diff = abs(opp.rank - fighter.rank)
                        if opp_rank_diff <= 10 and opp not in [o[0] for o in opponents]:
                            if opp.rank < fighter.rank:
                                d = "step up" if fighter.rank - opp.rank >= 5 else ("tough test" if fighter.rank - opp.rank >= 2 else "even matchup")
                            elif opp.rank > fighter.rank:
                                d = "should win" if opp.rank - fighter.rank >= 5 else ("pick em" if opp.rank - fighter.rank >= 2 else "even matchup")
                            else:
                                d = "even matchup"
                            opponents.append((opp, d))
                            if len(opponents) >= 10:
                                break
                # For National, if still too few, expand to any nationality
                if len(opponents) < 3 and self.tier_name == "National":
                    for opp in ranked:
                        if opp != fighter and opp.is_available() and opp not in [o[0] for o in opponents]:
                            opp_rank_diff = abs(opp.rank - fighter.rank)
                            if opp_rank_diff <= 10:
                                d = "even matchup"
                                opponents.append((opp, d))
                                if len(opponents) >= 5:
                                    break
        return opponents[:10]

def create_promotions(weight_classes: List[str]) -> List[Promotion]:
    regional = Promotion("Regional Fight Circuit", utils.PRO_TIERS[0], weight_classes)
    national = Promotion("National Combat Championship", utils.PRO_TIERS[1], weight_classes)
    world = Promotion("World MMA Federation", utils.PRO_TIERS[2], weight_classes)
    return [world, national, regional]
