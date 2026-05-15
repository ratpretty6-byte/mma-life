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

ATTRIBUTE_GROUPS = {
    "striking": ["striking_power", "striking_accuracy", "hand_speed"],
    "kicking": ["kick_power", "kick_accuracy", "kick_speed"],
    "takedown": ["takedown_power", "takedown_accuracy", "wrestling_defense"],
    "clinch": ["clinch_control", "clinch_escapes", "clinch_strikes", "clinch_throws"],
    "ground": ["top_control", "bottom_control", "submission_offense", "submission_defense"],
    "physical": ["cardio", "durability", "athleticism"],
    "mental": ["mental_toughness", "fight_iq", "heart", "discipline", "composure", "adaptability"],
    "personality": ["charisma", "aggression"],
}

ARCHETYPE_PROFILES = {
    "brawler": {"striking": {"power": 8, "accuracy": -5}, "physical": {"durability": 5, "cardio": -3}},
    "counter_striker": {"striking": {"accuracy": 8, "power": -5}, "mental": {"composure": 5}, "hand_speed": 5},
    "wrestler": {"takedown": {"power": 8, "accuracy": 5}, "clinch": {"control": 3, "throws": 3}, "kicking": {"power": -5, "accuracy": -3}},
    "submission_artist": {"ground": {"offense": 8, "defense": 5}, "takedown": {"accuracy": 3}, "striking": {"power": -5}},
    "kickboxer": {"kicking": {"power": 8, "accuracy": 5, "speed": 5}, "striking": {"accuracy": -3}},
    "boxer": {"striking": {"power": 5, "accuracy": 8, "hand_speed": 8}, "kicking": {"power": -8, "accuracy": -5}},
    "muay_thai": {"clinch": {"control": 8, "strikes": 8, "throws": 5}, "kicking": {"power": 5}, "striking": {"accuracy": -3}},
    "clinch_fighter": {"clinch": {"control": 10, "throws": 8, "escapes": 5}, "takedown": {"power": 5}},
    "balanced": {},
}

NATIONALITY_WEIGHTS = {
    "American": 35, "Brazilian": 10, "Russian": 8, "Japanese": 6, "British": 6,
    "Canadian": 4, "French": 3, "Dutch": 3, "Australian": 3, "Polish": 2,
    "Korean": 2, "Mexican": 4, "Chinese": 2, "Swedish": 2, "Irish": 2,
    "Nigerian": 2, "German": 2, "Italian": 2, "Spanish": 1, "Ukrainian": 1,
    "Cuban": 1, "Jamaican": 1, "South African": 1, "Swiss": 1, "Belgian": 1,
    "Norwegian": 1, "Finnish": 1, "Danish": 1, "Icelandic": 1, "New Zealander": 1,
}

def pick_nationality_and_region():
    """Pick a nationality weighted by real-world MMA representation, and return a matching region."""
    nations = list(NATIONALITY_WEIGHTS.keys())
    weights = list(NATIONALITY_WEIGHTS.values())
    nat = random.choices(nations, weights=weights, k=1)[0]
    regions = utils.REGIONS.get(nat, ["Capital"])
    region = random.choice(regions)
    return nat, region

def generate_single_fighter(weight_lbs: float, skill_mean: float = 50.0, skill_std: float = 15.0) -> Fighter:
    background = random.choice(["mma", "wrestling", "bjj", "muay_thai", "boxing", "judo", "taekwondo", "karate", "sambo", "kickboxing", "capoeira"])
    first_name, last_name = utils.generate_name()
    full_name = f"{first_name} {last_name}"
    age = random.randint(18, 38)
    archetype = random.choice(utils.ARCHETYPES)
    trait = random.choice(utils.TRAITS) if random.random() < 0.6 else None
    personality = random.choice(utils.PERSONALITIES)
    nationality, home_region = pick_nationality_and_region()

    fighter = Fighter(full_name, age, weight_lbs, background, archetype,
                      nationality=nationality, home_region=home_region,
                      trait_id=trait["id"] if trait else None,
                      personality_id=personality["id"])
    fighter.height = utils.gaussian_random(68, 4, 60, 84)
    fighter.reach = utils.gaussian_random(72, 4, 60, 88)

    # Use skill_mean and skill_std as baseline — this is the key fix
    base_val = utils.clamp(utils.gaussian_random(skill_mean, skill_std, 15, 95), 15, 95)

    # Generate group-level talent modifiers (correlated attributes within groups)
    group_mods = {}
    for group_name, attrs in ATTRIBUTE_GROUPS.items():
        group_mods[group_name] = utils.gaussian_random(0, 5, -10, 10)

    for attr in fighter.PHYSICAL_ATTRS + fighter.MENTAL_ATTRS:
        if attr not in fighter.attributes:
            continue

        # Find which group this attr belongs to
        attr_group = None
        for gname, gattrs in ATTRIBUTE_GROUPS.items():
            if attr in gattrs:
                attr_group = gname
                break

        group_mod = group_mods.get(attr_group, 0)
        # Per-attribute variance ±5 around the group baseline
        per_attr_var = utils.gaussian_random(0, 3, -6, 6)
        new_val = utils.clamp(base_val + group_mod + per_attr_var, utils.ATTR_MIN, utils.ATTR_MAX)
        fighter.attributes[attr] = new_val

    # Ensure minimum durability for all fighters to prevent glass jaws
    fighter.attributes["durability"] = max(fighter.attributes.get("durability", 0), 40)
    fighter.attributes["mental_toughness"] = max(fighter.attributes.get("mental_toughness", 0), 35)
    fighter.attributes["heart"] = max(fighter.attributes.get("heart", 0), 35)
    fighter.attributes["composure"] = max(fighter.attributes.get("composure", 0), 30)
    fighter.attributes["aggression"] = max(fighter.attributes.get("aggression", 0), 25)
    fighter.attributes["fight_iq"] = max(fighter.attributes.get("fight_iq", 0), 20)

    # Apply archetype stat profile
    profile = ARCHETYPE_PROFILES.get(archetype, {})
    for group_or_attr, adjustments in profile.items():
        if group_or_attr in ATTRIBUTE_GROUPS:
            for adj_attr, delta in adjustments.items():
                full_attr = f"{group_or_attr}_{adj_attr}" if "_" not in adj_attr else adj_attr
                if full_attr in fighter.attributes:
                    fighter.attributes[full_attr] = utils.clamp(
                        fighter.attributes[full_attr] + delta, utils.ATTR_MIN, utils.ATTR_MAX)
        elif "_" in group_or_attr:
            if group_or_attr in fighter.attributes:
                fighter.attributes[group_or_attr] = utils.clamp(
                    fighter.attributes[group_or_attr] + adjustments, utils.ATTR_MIN, utils.ATTR_MAX)

    # Cherry-pick direct flat adjustments (hand_speed, etc.)
    for attr_spec, val in profile.items():
        if isinstance(val, int) and attr_spec in fighter.attributes:
            fighter.attributes[attr_spec] = utils.clamp(
                fighter.attributes[attr_spec] + val, utils.ATTR_MIN, utils.ATTR_MAX)

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
    max_streak = random.randint(0, max(fighter.wins, fighter.losses))
    if random.random() < 0.6:
        fighter.win_streak = min(fighter.wins, max_streak)
        fighter.loss_streak = 0
    else:
        fighter.loss_streak = min(fighter.losses, max_streak)
        fighter.win_streak = 0
    fighter.confidence = 50 + fighter.win_streak * 5 - fighter.loss_streak * 8
    fighter.confidence = utils.clamp(fighter.confidence, 10, 100)
    fighter.net_worth = fighter.wins * random.randint(1000, 10000) + random.randint(0, 50000)
    fighter.months_inactive = random.randint(1, 8)

    # Cap starting fights based on age for realism
    max_starting_fights = max(3, fighter.age - 15)
    if fighter.wins + fighter.losses > max_starting_fights:
        total_fights = fighter.wins + fighter.losses
        ratio = fighter.wins / max(1, total_fights)
        fighter.wins = int(max_starting_fights * ratio)
        fighter.losses = max_starting_fights - fighter.wins
        fighter.knockouts = min(fighter.knockouts, fighter.wins)
        fighter.submissions = min(fighter.submissions, fighter.wins)

    return fighter

def assign_to_promotions(fighters: List[Fighter], promotions: List[Promotion]):
    world, national, regional = promotions
    for fighter in fighters:
        rating = fighter.get_overall_rating()
        win_pct = fighter.wins / max(1, fighter.wins + fighter.losses)
        if rating >= 68 and win_pct >= 0.60:
            world._add_fighter_batch(fighter)
        elif rating >= 35:
            national._add_fighter_batch(fighter)
        else:
            regional._add_fighter_batch(fighter)

    # Apply tier-based stat floors — elite fighters should be clearly better
    for f in world.fighters:
        for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
            f.attributes[attr] = max(f.attributes[attr], 45)
    for f in national.fighters:
        for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
            f.attributes[attr] = max(f.attributes[attr], 30)
    for f in regional.fighters:
        for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
            f.attributes[attr] = max(f.attributes[attr], 25)

    # Re-rank all promotions once after batch
    for p in promotions:
        p.update_rankings()

def generate_fighters(total: int = 8000) -> List[Fighter]:
    weight_probs = [0.10, 0.12, 0.14, 0.18, 0.16, 0.14, 0.10, 0.10]
    fighters = []
    weight_classes = utils.WEIGHT_CLASSES
    for i in range(total):
        wc_idx = random.choices(range(len(weight_classes)), weights=weight_probs)[0]
        wc = weight_classes[wc_idx]
        weight_lbs = random.randint(wc["min"], wc["max"])
        skill_mean = utils.gaussian_random(55, 8, 35, 75)
        skill_std = utils.gaussian_random(10, 3, 5, 16)
        # Reject extreme stat variance — max-min difference must be <= 50
        for attempt in range(3):
            fighter = generate_single_fighter(weight_lbs, skill_mean, skill_std)
            vals = list(fighter.attributes.values())
            if max(vals) - min(vals) <= 50:
                break
        fighters.append(fighter)
    return fighters

def generate_fighter_pool(promotions: List[Promotion], total: int = 5000) -> List[Fighter]:
    fighters = generate_fighters(total)
    assign_to_promotions(fighters, promotions)
    return fighters
