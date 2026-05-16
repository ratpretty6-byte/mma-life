import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import utils
from fighter import Fighter


# Promotion personality templates
PROMOTION_PERSONALITIES = [
    {
        "name": "Aggressive Matchmaking",
        "matchmaking_style": "aggressive",
        "contract_flexibility": "strict",
        "medical_coverage": "partial",
        "marketing_power": 1.2,
        "prestige": 3,
        "description": "Rewards winners with big fights. Tough on losers.",
    },
    {
        "name": "Fighter-Friendly",
        "matchmaking_style": "protective",
        "contract_flexibility": "flexible",
        "medical_coverage": "full",
        "marketing_power": 0.8,
        "prestige": 2,
        "description": "Puts fighter health first, easy matchmaking.",
    },
    {
        "name": "Prestige Focus",
        "matchmaking_style": "balanced",
        "contract_flexibility": "standard",
        "medical_coverage": "full",
        "marketing_power": 1.5,
        "prestige": 5,
        "description": "High pay, high expectations. Only the best.",
    },
    {
        "name": "Developmental League",
        "matchmaking_style": "protective",
        "contract_flexibility": "flexible",
        "medical_coverage": "partial",
        "marketing_power": 0.5,
        "prestige": 1,
        "description": "Builds prospects. Low pay, low pressure.",
    },
    {
        "name": "Hardcore Fight Club",
        "matchmaking_style": "aggressive",
        "contract_flexibility": "standard",
        "medical_coverage": "none",
        "marketing_power": 0.7,
        "prestige": 2,
        "description": "Fight or go home. Aggressive matchups, no handouts.",
    },
    {
        "name": "International Spotlight",
        "matchmaking_style": "balanced",
        "contract_flexibility": "flexible",
        "medical_coverage": "full",
        "marketing_power": 1.3,
        "prestige": 4,
        "description": "Global events, media focus, big paydays.",
    },
]

PROMOTION_NAMES = [
    # Regional
    "Xtreme Cage Fighting", "Dynasty Combat", "Warrior Championship", "Legacy Fight League",
    "Thunderstrike Promotions",
    # National
    "American Combat Championship", "Pan-Asian Fighting", "Euro Fighting Alliance",
    "North American MMA", "Superior Combat",
    # World
    "Global Fight Federation", "Premier Fighting Championship", "World Combat Series",
    "Ultimate Fighting Alliance",
]


class Contract:
    def __init__(self, fighter: Fighter, promotion: 'Promotion', fights_remaining: int,
                 base_pay: float, win_bonus: float, performance_bonus: float = 5000.0,
                 champion: bool = False, game_date: datetime = None, personality: Dict = None):
        self.fighter = fighter
        self.promotion = promotion
        self.fights_remaining = fights_remaining
        self.base_pay = base_pay
        self.win_bonus = win_bonus
        self.performance_bonus = performance_bonus
        self.signed_date = game_date or datetime.now()
        self.original_base_pay = base_pay
        self.champion = champion

    def complete_fight(self, won: bool, perf_bonus: bool = False, card_bonus: float = 0.0) -> float:
        pay = self.base_pay + card_bonus
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
    def __init__(self, name: str, tier: Dict, weight_classes: List[str], personality: Dict = None):
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
        self.personality = personality or {}

    def get_personality_trait(self, key: str, default=None):
        return self.personality.get(key, default)

    def _add_fighter_batch(self, fighter: Fighter):
        if fighter in self.fighters:
            return
        self.fighters.append(fighter)
        pp = self.personality
        pay_mult = 1.0
        if pp.get("marketing_power"):
            pay_mult = pp["marketing_power"]
        adj_base = max(self.base_pay, int(self.base_pay * pay_mult))
        self.contracts[fighter] = Contract(fighter, self, 4, adj_base, adj_base * 0.5, self.perf_bonus)
        if fighter.weight_class in self.rankings:
            self.rankings[fighter.weight_class].append(fighter)
        fighter.current_contract = self.contracts[fighter]

    def sign_fighter(self, fighter: Fighter, fights: int = 4, game_date: datetime = None, personality: Dict = None) -> Contract:
        if fighter in self.fighters:
            return self.contracts[fighter]
        self.fighters.append(fighter)

        rank_factor = max(1, 51 - len(self.rankings.get(fighter.weight_class, []))) / 50.0
        rating_factor = fighter.get_overall_rating() / 100.0
        pp = self.personality
        pay_mult = 1.0
        if pp.get("marketing_power"):
            pay_mult = pp["marketing_power"]
        adjusted_base = max(self.base_pay, self.base_pay * (0.5 + rating_factor) * rank_factor * pay_mult)
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
        pp = self.personality
        pay_mult = 1.0
        if pp.get("marketing_power"):
            pay_mult = pp["marketing_power"]
        adjusted_base = max(self.base_pay, self.base_pay * (0.5 + rating_factor) * rank_factor * pay_mult)
        adjusted_win = adjusted_base * 0.5
        return Contract(fighter, self, fights, round(adjusted_base, -1), round(adjusted_win, -1), self.perf_bonus, game_date=game_date)

    def get_ranked_fighters(self, weight_class: str, exclude: Optional[List[Fighter]] = None) -> List[Fighter]:
        if weight_class not in self.rankings:
            return []
        exclude = exclude or []
        return [f for f in self.rankings[weight_class] if f not in exclude]

    # === FIGHT OFFER SYSTEM ===

    def generate_fight_offers(self, player: Fighter, count: int = 3) -> List[Dict]:
        offers = []
        if player.weight_class not in self.rankings or player not in self.rankings[player.weight_class]:
            return offers
        ranked = self.rankings[player.weight_class]
        idx = ranked.index(player)
        candidates = []

        # Gimme: opponents ranked much lower
        for i in range(idx + 1, min(idx + 6, len(ranked))):
            opp = ranked[i]
            if opp != player and opp.is_available() and (opp.losses >= opp.wins or opp.rank - player.rank >= 4):
                candidates.append({"opponent": opp, "risk": "gimme"})
                if len(candidates) >= count:
                    break

        # 50-50: nearby ranked
        nearby_range = list(range(max(0, idx - 3), idx)) + list(range(idx + 1, min(idx + 4, len(ranked))))
        for i in nearby_range:
            opp = ranked[i]
            if opp != player and opp.is_available() and abs(opp.rank - player.rank) <= 2:
                if not any(c["opponent"] == opp for c in candidates):
                    candidates.append({"opponent": opp, "risk": "50-50"})

        # Tough: opponents ranked higher
        for i in range(max(0, idx - 5), idx):
            opp = ranked[i]
            if opp != player and opp.is_available() and player.rank - opp.rank >= 2:
                opp_wins = max(opp.wins, 1)
                if opp.win_streak >= 2 or opp.losses < opp_wins * 0.3:
                    if not any(c["opponent"] == opp for c in candidates):
                        candidates.append({"opponent": opp, "risk": "tough"})

        # Sacrifice: champion or top 2
        champion = self.champions.get(player.weight_class)
        if champion and champion.is_available() and champion != player:
            candidates.append({"opponent": champion, "risk": "sacrifice"})
        if len(ranked) > 2:
            top2 = ranked[0] if ranked[0] != player else ranked[1]
            if top2.is_available() and top2 != player:
                candidates.append({"opponent": top2, "risk": "sacrifice"})

        # Deduplicate and sort
        seen = set()
        unique = []
        for c in candidates:
            if c["opponent"] not in seen:
                seen.add(c["opponent"])
                unique.append(c)

        # Pick best variety
        risk_order = {"sacrifice": 0, "tough": 1, "50-50": 2, "gimme": 3}
        unique.sort(key=lambda x: risk_order.get(x["risk"], 99))
        offered_risks = set()
        for c in unique[:count * 2]:
            if len(offers) >= count:
                break
            if c["risk"] in offered_risks:
                continue
            offered_risks.add(c["risk"])
            diff = idx - ranked.index(c["opponent"]) if ranked.index(c["opponent"]) < idx else ranked.index(c["opponent"]) - idx
            purse_mult = {"sacrifice": 1.5, "tough": 1.2, "50-50": 1.0, "gimme": 0.8}.get(c["risk"], 1.0)
            pop_gain = {"sacrifice": 15, "tough": 8, "50-50": 5, "gimme": 2}.get(c["risk"], 5)
            card_slot = self._get_card_position(player, c["opponent"], c["risk"])
            offers.append({
                "opponent": c["opponent"],
                "risk": c["risk"],
                "purse_bonus": purse_mult,
                "popularity_gain": pop_gain,
                "card_position": card_slot,
                "base_purse": int(self.base_pay * purse_mult),
                "win_bonus": int(self.win_bonus * purse_mult),
            })

        return offers[:count]

    def _get_card_position(self, player: Fighter, opponent: Fighter, risk: str) -> str:
        avg_rank = (player.rank + opponent.rank) / 2
        pop = getattr(player, "popularity", 0)
        if risk == "sacrifice":
            return "main_event"
        if avg_rank <= 2 or pop >= 70:
            return "main_event"
        if avg_rank <= 4 or pop >= 50:
            return "co_main"
        if avg_rank <= 8 or pop >= 30:
            return "main_card"
        return "prelim"

    def _get_card_bonus(self, position: str) -> float:
        return {"prelim": 0, "main_card": 2000, "co_main": 5000, "main_event": 10000}.get(position, 0)

    def check_contract_relationship(self, player: Fighter) -> Dict:
        pp = self.personality
        declined = getattr(player, "declined_offers_count", 0)
        status = "good"
        warning = ""
        if declined >= 3:
            pp_flex = pp.get("contract_flexibility", "standard")
            if pp_flex == "strict":
                status = "strained"
                warning = "Your promotion is unhappy with repeated declined fights."
            elif pp_flex == "standard":
                status = "warning"
                warning = "Declining too many fights may affect your standing."
        return {"status": status, "warning": warning, "declined_offers": declined}


def create_promotions(weight_classes: List[str]) -> List[Promotion]:
    promotions = []
    names = PROMOTION_NAMES[:]
    random.shuffle(names)

    # Regional: 5 promotions
    for i in range(5):
        name = names.pop(0) if names else f"Regional FC #{i+1}"
        pers = PROMOTION_PERSONALITIES[i % len(PROMOTION_PERSONALITIES)]
        promos = Promotion(name, utils.PRO_TIERS[0], weight_classes, dict(pers))
        promotions.append(promos)

    # National: 4 promotions
    for i in range(4):
        name = names.pop(0) if names else f"National FC #{i+1}"
        pers = PROMOTION_PERSONALITIES[(i + 3) % len(PROMOTION_PERSONALITIES)]
        promos = Promotion(name, utils.PRO_TIERS[1], weight_classes, dict(pers))
        promotions.append(promos)

    # World: 3 promotions
    for i in range(3):
        name = names.pop(0) if names else f"World FC #{i+1}"
        pers = PROMOTION_PERSONALITIES[(i + 5) % len(PROMOTION_PERSONALITIES)]
        promos = Promotion(name, utils.PRO_TIERS[2], weight_classes, dict(pers))
        promotions.append(promos)

    return promotions
