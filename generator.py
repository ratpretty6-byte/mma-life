import random
import math
from typing import List, Dict, Tuple
from fighter import Fighter
from promotion import Promotion
import utils

ARCHETYPE_STRATEGY_MAP = {
    "brawler": "aggressive_striking",
    "counter_striker": "defensive_striking",
    "wrestler": "wrestling_focus",
    "submission_artist": "submission_hunting",
    "kickboxer": "kickboxing_focus",
    "boxer": "boxing_focus",
    "muay_thai": "muay_thai_focus",
    "clinch_fighter": "clinch_dominance",
    "balanced": None,
}

def pick_archetype(attributes: Dict[str, float]) -> str:
    phys = attributes
    scores = {
        "brawler": phys.get("striking_power", 50) + phys.get("durability", 50) + phys.get("aggression", 50),
        "counter_striker": phys.get("striking_accuracy", 50) + phys.get("hand_speed", 50) + phys.get("composure", 50),
        "wrestler": phys.get("takedown_power", 50) + phys.get("takedown_accuracy", 50) + phys.get("top_control", 50),
        "submission_artist": phys.get("submission_offense", 50) + phys.get("submission_defense", 50) + phys.get("bottom_control", 50),
        "kickboxer": phys.get("kick_power", 50) + phys.get("kick_accuracy", 50) + phys.get("kick_speed", 50),
        "boxer": phys.get("striking_power", 50) + phys.get("hand_speed", 50) + phys.get("striking_accuracy", 50),
        "muay_thai": phys.get("clinch_control", 50) + phys.get("clinch_strikes", 50) + phys.get("kick_power", 50),
        "clinch_fighter": phys.get("clinch_control", 50) + phys.get("clinch_throws", 50) + phys.get("takedown_power", 50),
        "balanced": phys.get("fight_iq", 50) + phys.get("adaptability", 50),
    }
    return max(scores, key=scores.get)

def assign_archetype_strategy(fighter: Fighter):
    strat_id = ARCHETYPE_STRATEGY_MAP.get(fighter.archetype)
    return strat_id

def generate_single_fighter(weight_lbs: float, skill_mean: float = 50.0, skill_std: float = 15.0) -> Fighter:
    background = random.choice(["mma", "wrestling", "bjj", "muay_thai", "boxing", "judo", "taekwondo", "karate", "sambo", "kickboxing", "capoeira"])
    first_name, last_name = utils.generate_name()
    full_name = f"{first_name} {last_name}"
    age = random.randint(18, 38)
    archetype = random.choice(utils.ARCHETYPES)
    trait = random.choice(utils.TRAITS) if random.random() < 0.6 else None
    personality = random.choice(utils.PERSONALITIES)

    fighter = Fighter(full_name, age, weight_lbs, background, archetype,
                      trait_id=trait["id"] if trait else None,
                      personality_id=personality["id"])
    fighter.height = utils.gaussian_random(68, 4, 60, 84)
    fighter.reach = utils.gaussian_random(72, 4, 60, 88)

    talent_bias = utils.gaussian_random(0, 15, -30, 30)
    for attr in fighter.PHYSICAL_ATTRS + fighter.MENTAL_ATTRS:
        if attr in fighter.attributes:
            attr_roll = random.uniform(-1, 1)
            burst = 15 if attr_roll > 0.85 else (15 if attr_roll < -0.85 else 0)
            adjustment = talent_bias + utils.gaussian_random(0, 25, -45, 45) + burst
            fighter.attributes[attr] = utils.clamp(fighter.attributes[attr] + adjustment, utils.ATTR_MIN, utils.ATTR_MAX)

    fighter.archetype = pick_archetype(fighter.attributes)

    rating = fighter.get_overall_rating()
    if rating >= 70:
        w, l = utils.gaussian_random(15, 5, 5, 30), utils.gaussian_random(3, 2, 0, 10)
    elif rating >= 55:
        w, l = utils.gaussian_random(10, 5, 2, 25), utils.gaussian_random(5, 3, 0, 15)
    elif rating >= 40:
        w, l = utils.gaussian_random(6, 4, 0, 18), utils.gaussian_random(8, 4, 1, 20)
    else:
        w, l = utils.gaussian_random(2, 2, 0, 8), utils.gaussian_random(12, 5, 3, 25)

    fighter.wins = max(0, int(w))
    fighter.losses = max(0, int(l))
    fighter.draws = random.choices([0, 1, 2], weights=[80, 15, 5])[0]
    fighter.knockouts = int(fighter.wins * random.uniform(0.3, 0.7))
    fighter.submissions = int(fighter.wins * random.uniform(0.1, 0.4))
    fighter.win_streak = min(fighter.wins, random.randint(0, fighter.wins))
    fighter.loss_streak = min(fighter.losses, random.randint(0, fighter.losses))
    fighter.confidence = 50 + fighter.win_streak * 5 - fighter.loss_streak * 8
    fighter.confidence = utils.clamp(fighter.confidence, 10, 100)
    fighter.net_worth = fighter.wins * random.randint(1000, 10000) + random.randint(0, 50000)
    fighter.months_inactive = random.randint(1, 8)

    return fighter

def assign_to_promotions(fighters: List[Fighter], promotions: List[Promotion]):
    world, national, regional = promotions
    for fighter in fighters:
        rating = fighter.get_overall_rating()
        win_pct = fighter.wins / max(1, fighter.wins + fighter.losses)
        if rating >= 68 and win_pct >= 0.60:
            world.sign_fighter(fighter)
        elif rating >= 42:
            national.sign_fighter(fighter)
        else:
            regional.sign_fighter(fighter)

def generate_fighters(total: int = 5000) -> List[Fighter]:
    weight_probs = [0.10, 0.12, 0.14, 0.18, 0.16, 0.14, 0.10, 0.06]
    fighters = []
    weight_classes = utils.WEIGHT_CLASSES
    for i in range(total):
        wc_idx = random.choices(range(len(weight_classes)), weights=weight_probs)[0]
        wc = weight_classes[wc_idx]
        weight_lbs = random.randint(wc["min"], wc["max"])
        skill_mean = utils.gaussian_random(50, 10, 25, 75)
        skill_std = utils.gaussian_random(15, 3, 8, 22)
        fighter = generate_single_fighter(weight_lbs, skill_mean, skill_std)
        fighters.append(fighter)
    return fighters

def generate_fighter_pool(promotions: List[Promotion], total: int = 5000) -> List[Fighter]:
    fighters = generate_fighters(total)
    assign_to_promotions(fighters, promotions)
    return fighters
