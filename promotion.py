from typing import Dict, List, Optional, Tuple
from fighter import Fighter
from datetime import datetime, timedelta
import utils

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
        self.fights_remaining -= 1
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

    def update_rankings(self):
        for wc in self.weight_classes:
            fighters = self.rankings[wc]
            scored = []
            for f in fighters:
                opp_ratings = [50.0]
                sos = utils.calculate_strength_of_schedule(f.wins, f.losses, opp_ratings)
                score = (f.wins * 3 + f.knockouts * 2 + f.submissions * 2
                         + f.win_streak * 5 - f.losses * 2 - f.loss_streak * 3
                         + sos * 10)
                scored.append((f, score))
            scored.sort(key=lambda x: (-x[1], x[0].name))
            champion = self.champions.get(wc)
            if champion:
                scored.sort(key=lambda x: (0 if x[0] == champion else 1, -x[1], x[0].name))
            self.rankings[wc] = [s[0] for s in scored]
            for idx, fighter in enumerate(self.rankings[wc], 1):
                fighter.rank = idx
                fighter.update_rank(idx)

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

    def get_available_opponents(self, fighter: Fighter) -> List[Tuple[Fighter, str]]:
        if fighter.weight_class not in self.rankings:
            return []
        ranked = self.rankings[fighter.weight_class]
        if fighter not in ranked:
            return [(f, "unranked matchup") for f in ranked[:10]]

        idx = ranked.index(fighter)
        opponents = []
        nearby = ranked[max(0, idx-3):idx] + ranked[idx+1:idx+4]
        for opp in nearby:
            if opp.is_available():
                if opp.rank < fighter.rank:
                    difficulty = "step up" if opp.rank < fighter.rank - 2 else "tough test"
                elif opp.rank > fighter.rank:
                    difficulty = "should win" if opp.rank > fighter.rank + 2 else "pick em"
                else:
                    difficulty = "even matchup"
                opponents.append((opp, difficulty))
        return opponents[:5]

def create_promotions(weight_classes: List[str]) -> List[Promotion]:
    regional = Promotion("Regional Fight Circuit", utils.PRO_TIERS[0], weight_classes)
    national = Promotion("National Combat Championship", utils.PRO_TIERS[1], weight_classes)
    world = Promotion("World MMA Federation", utils.PRO_TIERS[2], weight_classes)
    return [world, national, regional]
