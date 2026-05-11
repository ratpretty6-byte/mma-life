from typing import Dict, List, Optional, Tuple
import random
import math

WEIGHT_CLASSES = [
    {"name": "Flyweight", "min": 125, "max": 125},
    {"name": "Bantamweight", "min": 126, "max": 135},
    {"name": "Featherweight", "min": 136, "max": 145},
    {"name": "Lightweight", "min": 146, "max": 155},
    {"name": "Welterweight", "min": 156, "max": 170},
    {"name": "Middleweight", "min": 171, "max": 185},
    {"name": "Light Heavyweight", "min": 186, "max": 205},
    {"name": "Heavyweight", "min": 206, "max": 265},
]

ATTR_MIN = 0
ATTR_MAX = 100

# --- Severity Tiers (6-tier strike grading) ---
SEVERITY_TIERS = [
    {"name": "Blocked",     "mult": 0.05, "score": 0.1,  "knockdown_chance": 0.0,  "vision_damage": 0.0},
    {"name": "Glancing",    "mult": 0.30, "score": 0.3,  "knockdown_chance": 0.0,  "vision_damage": 0.01},
    {"name": "Clean",       "mult": 0.70, "score": 0.7,  "knockdown_chance": 0.01, "vision_damage": 0.02},
    {"name": "Solid",       "mult": 1.00, "score": 1.0,  "knockdown_chance": 0.03, "vision_damage": 0.04},
    {"name": "Flush",       "mult": 1.40, "score": 1.3,  "knockdown_chance": 0.06, "vision_damage": 0.08},
    {"name": "Devastating", "mult": 1.90, "score": 1.8,  "knockdown_chance": 0.12, "vision_damage": 0.12},
]
SEVERITY_NAMES = {t["name"]: t for t in SEVERITY_TIERS}

# --- Body damage accumulation thresholds ---
BODY_DAMAGE_LEVELS = [
    {"name": "healthy",    "threshold": 0,   "stamina_drain": 0.0,  "accuracy_mod": 0.0,  "desc": ""},
    {"name": "minor",      "threshold": 20,  "stamina_drain": 0.05, "accuracy_mod": -0.02, "desc": ""},
    {"name": "moderate",   "threshold": 40,  "stamina_drain": 0.15, "accuracy_mod": -0.04, "desc": "{fighter} grimaces from body shots"},
    {"name": "severe",     "threshold": 60,  "stamina_drain": 0.35, "accuracy_mod": -0.08, "desc": "{fighter} is hunched over from body damage"},
    {"name": "critical",   "threshold": 80,  "stamina_drain": 0.60, "accuracy_mod": -0.14, "desc": "{fighter} can barely breathe!"},
    {"name": "destroyed",  "threshold": 95,  "stamina_drain": 0.90, "accuracy_mod": -0.22, "desc": "{fighter} is folding from body shots!"},
]

# --- Leg damage thresholds ---
LEG_DAMAGE_LEVELS = [
    {"threshold": 0,   "movement_mod": 1.0,  "kick_mod": 1.0,  "td_mod": 1.0,   "desc": ""},
    {"threshold": 25,  "movement_mod": 0.93, "kick_mod": 0.85, "td_mod": 0.95,  "desc": "{fighter}'s leg showing kick damage"},
    {"threshold": 50,  "movement_mod": 0.82, "kick_mod": 0.65, "td_mod": 0.80,  "desc": "{fighter} is limping noticeably"},
    {"threshold": 75,  "movement_mod": 0.65, "kick_mod": 0.35, "td_mod": 0.55,  "desc": "{fighter} can barely put weight on that leg"},
    {"threshold": 90,  "movement_mod": 0.35, "kick_mod": 0.10, "td_mod": 0.20,  "desc": "{fighter}'s leg is nearly destroyed"},
]

# --- Fighter state progression ---
FIGHTER_STATES = ["NORMAL", "HURT", "ROCKED", "STUNNED", "DOWN"]
STATE_TRANSITIONS = {
    "NORMAL":  {"hurt_head": 55, "hurt_body": 50},       # head or body zone drops below threshold
    "HURT":    {"rocked": 30, "stunned": 20},             # head drops below these
    "ROCKED":  {"stunned": 15, "normal_rest": 40},        # recover if above 40 with rest
    "STUNNED": {"down": 5, "recover": 25},                # recover chance based on heart/durability
}

ARCHETYPES = [
    "brawler", "counter_striker", "wrestler", "submission_artist",
    "kickboxer", "boxer", "muay_thai", "clinch_fighter", "balanced"
]

FIRST_NAMES = [
    "James","John","Robert","Michael","William","David","Richard","Joseph",
    "Thomas","Charles","Chris","Daniel","Matthew","Anthony","Mark","Donald",
    "Steven","Paul","Andrew","Joshua","Kenneth","Kevin","Brian","George",
    "Timothy","Ronald","Edward","Jason","Jeffrey","Ryan","Jacob","Gary",
    "Nicholas","Eric","Jonathan","Stephen","Larry","Justin","Scott","Brandon",
    "Benjamin","Samuel","Raymond","Gregory","Frank","Alexander","Patrick",
    "Jack","Dennis","Jerry","Tyler","Aaron","Jose","Nathan","Henry",
    "Douglas","Peter","Adam","Zachary","Walter","Andre","Kyle","Mason",
    "Luis","Jorge","Carlos","Diego","Rafael","Pedro","Miguel","Antonio",
    "Victor","Eduardo","Fernando","Alex","Sean","Derek","Marcus","Adrian",
    "Akira","Takeshi","Kenji","Satoshi","Yuki","Hiroshi","Jun","Hyun",
    "Sung","Min","Jin","Dae","Woo","Tyrone","Jamel","Darnell","DeShawn",
    "Tevin","Terrell","Kendrick","DaMarcus","Israel","Ivan","Dmitri",
    "Sergei","Alexei","Nikolai","Vladimir","Mikhail","Pavel","Conor","Liam",
    "Declan","Rory","Finn","Cian","Mateusz","Jakub","Krzysztof","Tomasz",
    "Piotr","Przemek","Anderson","Josef","Hector","Marco","Andres",
    "Ricardo","Alejandro","Francisco","Erik","Igor","Khalil","Rashad",
    "Jamal","DeAndre","Jermaine","Kendall","Zion","Kai","Koji","Ryo",
    "Takeo","Hideo","Sho","Sora","Blake","Cole","Brett","Chad","Dustin",
    "Kurt","Ross","Drew","Jake","Max","Leo",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
    "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill",
    "Flores","Green","Adams","Nelson","Baker","Hall","Rivera","Campbell",
    "Mitchell","Carter","Roberts","Gomez","Phillips","Evans","Turner",
    "Diaz","Parker","Cruz","Edwards","Collins","Reyes","Stewart","Morris",
    "Morales","Murphy","Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper",
    "Peterson","Bailey","Reed","Kelly","Howard","Ramos","Kim","Cox",
    "Ward","Richardson","Watson","Brooks","Chavez","Wood","James","Bennett",
    "Gray","Mendoza","Ruiz","Hughes","Price","Alvarez","Castillo","Sanders",
    "Patel","Myers","Long","Ross","Foster","Jimenez","Powell","Jenkins",
    "Perry","Russell","Sullivan","Bell","Coleman","Butler","Henderson",
    "Barnes","Fisher","Vasquez","Simmons","Romero","Jordan","Patterson",
    "Alexander","Hamilton","Graham","Reynolds","Griffin","Wallace",
    "Moreno","West","Cole","Hayes","Bryant","Herrera","Gibson","Ellis",
    "Medina","Owens","Silva","Santos","Oliveira","Souza","Lima","Pereira",
    "Costa","Ferreira","Rodrigues","Almeida","Nascimento","Araujo","Barbosa",
    "Carvalho","Yamamoto","Tanaka","Nakamura","Sato","Takahashi","Suzuki",
    "Ito","Watanabe","Kobayashi","Kimura","Shimizu","Yoshida","Matsumoto",
    "Hasegawa","Park","Choi","Jung","Kim","Cho","Yoon","Shin",
    "Nowak","Kowalski","Wisniewski","Zielinski","Jankowski","Kaminski",
    "Lewandowski","Zajac","Kowalczyk","O'Brien","Ryan","Kelly","Walsh",
    "McCarthy","Sullivan","Flynn","Gallagher","O'Neill","Doyle","Kennedy",
    "Volkov","Ivanov","Petrov","Sokolov","Kuznetsov","Popov","Vasiliev",
    "Fedorov","Morozov","Novikov","Kozlov","Lebedev","Khalil","Abdul",
    "Okonkwo","Nnamdi","Okafor","Abebe","Mensah","Owusu","Kamau",
]

NATIONALITIES = [
    "American", "Brazilian", "Russian", "Japanese", "British", "Canadian",
    "French", "Dutch", "Australian", "Polish", "Korean", "Mexican",
    "Chinese", "Swedish", "Irish", "Nigerian", "New Zealander", "German",
    "Italian", "Spanish", "Ukrainian", "Cuban", "Jamaican", "South African",
    "Swiss", "Belgian", "Norwegian", "Finnish", "Danish", "Icelandic"
]

REGIONS = {
    "American": ["California", "Texas", "New York", "Florida", "Ohio", "Colorado", "Nevada", "Arizona"],
    "Brazilian": ["Rio de Janeiro", "Sao Paulo", "Bahia", "Minas Gerais", "Ceara"],
    "Russian": ["Moscow", "St. Petersburg", "Dagestan", "Chechnya", "Siberia"],
    "Japanese": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Okinawa"],
    "British": ["London", "Manchester", "Liverpool", "Birmingham", "Scotland"],
    "Canadian": ["Ontario", "Quebec", "British Columbia", "Alberta", "Nova Scotia"],
    "French": ["Paris", "Lyon", "Marseille", "Bordeaux", "Toulouse"],
    "Dutch": ["Amsterdam", "Rotterdam", "Utrecht", "The Hague", "Eindhoven"],
    "Australian": ["Sydney", "Melbourne", "Brisbane", "Perth", "Gold Coast"],
    "Polish": ["Warsaw", "Krakow", "Gdansk", "Wroclaw", "Poznan"],
    "Korean": ["Seoul", "Busan", "Incheon", "Daegu", "Ulsan"],
    "Mexican": ["Mexico City", "Guadalajara", "Monterrey", "Tijuana", "Puebla"],
    "Chinese": ["Beijing", "Shanghai", "Shenzhen", "Guangzhou", "Chengdu"],
    "Swedish": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Linkoping"],
    "Irish": ["Dublin", "Cork", "Galway", "Limerick", "Belfast"],
    "Nigerian": ["Lagos", "Abuja", "Port Harcourt", "Ibadan", "Kano"],
    "New Zealander": ["Auckland", "Wellington", "Christchurch", "Hamilton", "Tauranga"],
    "German": ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt"],
    "Italian": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "Spanish": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"],
    "Ukrainian": ["Kyiv", "Kharkiv", "Odessa", "Dnipro", "Lviv"],
    "Cuban": ["Havana", "Santiago", "Camaguey", "Holguin", "Santa Clara"],
    "Jamaican": ["Kingston", "Montego Bay", "Ocho Rios", "Negril", "Spanish Town"],
    "South African": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth"],
    "Swiss": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne"],
    "Belgian": ["Brussels", "Antwerp", "Ghent", "Bruges", "Liege"],
    "Norwegian": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Tromso"],
    "Finnish": ["Helsinki", "Espoo", "Tampere", "Turku", "Oulu"],
    "Danish": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg"],
    "Icelandic": ["Reykjavik", "Kopavogur", "Hafnarfjordur", "Akureyri", "Gardabaer"]
}

TRAITS = [
    {"id": "heavy_hands", "name": "Heavy Hands", "description": "+5 striking power", "effects": {"striking_power": 5}},
    {"id": "iron_chin", "name": "Iron Chin", "description": "+5 durability", "effects": {"durability": 5}},
    {"id": "cardio_king", "name": "Cardio King", "description": "+5 cardio", "effects": {"cardio": 5}},
    {"id": "mat_wizard", "name": "Mat Wizard", "description": "+5 wrestling defense", "effects": {"wrestling_defense": 5}},
    {"id": "sniper", "name": "Sniper", "description": "+5 striking accuracy", "effects": {"striking_accuracy": 5}},
    {"id": "natural_athlete", "name": "Natural Athlete", "description": "+3 all physical attributes", "effects": {attr: 3 for attr in ["athleticism", "hand_speed", "cardio", "durability", "striking_power", "striking_accuracy", "takedown_power", "takedown_accuracy"]}},
    {"id": "iron_will", "name": "Iron Will", "description": "+5 mental toughness & composure", "effects": {"mental_toughness": 5, "composure": 5}},
    {"id": "fast_hands", "name": "Fast Hands", "description": "+5 hand speed", "effects": {"hand_speed": 5}},
]

PERSONALITIES = [
    {"id": "charismatic", "name": "Charismatic", "description": "Natural charisma, fans love you", "effects": {"charisma": 10}},
    {"id": "intimidating", "name": "Intimidating", "description": "Strikes fear into opponents", "effects": {"aggression": 8, "charisma": -3}},
    {"id": "humble", "name": "Humble", "description": "Respected by fans and media", "effects": {"composure": 5, "charisma": 3}},
    {"id": "cocky", "name": "Cocky", "description": "Loves the spotlight", "effects": {"charisma": 5, "aggression": 3, "composure": -2}},
    {"id": "quiet", "name": "Quiet", "description": "Lets fighting do the talking", "effects": {"composure": 8, "charisma": -5}},
    {"id": "savage", "name": "Savage", "description": "No mercy in the cage", "effects": {"aggression": 10, "heart": 3}},
]


def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))


def random_roll(min_val: int = 0, max_val: int = 100) -> int:
    return random.randint(min_val, max_val)


def gaussian_random(mean: float = 50.0, std_dev: float = 15.0, min_val: int = 0, max_val: int = 100) -> int:
    val = random.gauss(mean, std_dev)
    return int(clamp(val, min_val, max_val))


def calculate_effective_attribute(base_attr: float, fatigue: float = 0.0, injury_penalty: float = 0.0) -> int:
    modifier = 1.0 - (fatigue * 0.3) - injury_penalty
    return int(clamp(base_attr * modifier, ATTR_MIN, ATTR_MAX))


def get_weight_class(weight_lbs: float) -> str:
    for wc in WEIGHT_CLASSES:
        if wc["min"] <= weight_lbs <= wc["max"]:
            return wc["name"]
    return "Catchweight"


def get_weight_class_index(weight_class: str) -> int:
    for i, wc in enumerate(WEIGHT_CLASSES):
        if wc["name"] == weight_class:
            return i
    return -1


def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


def weight_cut_penalty(weight_to_cut_lbs: float) -> Dict[str, float]:
    if weight_to_cut_lbs <= 0:
        return {"cardio_penalty": 0.0, "durability_penalty": 0.0, "strength_penalty": 0.0}
    excess_cut = max(0, weight_to_cut_lbs - 5)
    cardio_penalty = min(0.25, excess_cut * 0.06)
    durability_penalty = min(0.18, excess_cut * 0.045)
    strength_penalty = min(0.15, excess_cut * 0.035)
    return {"cardio_penalty": cardio_penalty, "durability_penalty": durability_penalty, "strength_penalty": strength_penalty}


def calculate_rating_from_attrs(attributes: Dict[str, float], physical_attrs: List[str], mental_attrs: List[str]) -> float:
    phys = sum(attributes.get(a, 50) for a in physical_attrs) / len(physical_attrs)
    ment = sum(attributes.get(a, 50) for a in mental_attrs) / len(mental_attrs)
    return phys * 0.7 + ment * 0.3


def generate_name() -> Tuple[str, str]:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last


def get_age_modifier(age: int) -> float:
    if age < 27:
        return age / 27
    elif age > 30:
        return max(0.7, 1.0 - (age - 30) * 0.02)
    return 1.0


def calculate_strength_of_schedule(wins: int, losses: int, opponent_ratings: List[float]) -> float:
    if not opponent_ratings:
        return 0.0
    avg_opp = sum(opponent_ratings) / len(opponent_ratings)
    return avg_opp / 100.0


PRO_TIERS = [
    {"name": "Regional", "base_pay": 2000, "win_bonus": 2000, "perf_bonus": 5000, "ranking_weight": 1.0},
    {"name": "National", "base_pay": 8000, "win_bonus": 8000, "perf_bonus": 15000, "ranking_weight": 2.0},
    {"name": "World", "base_pay": 25000, "win_bonus": 25000, "perf_bonus": 50000, "ranking_weight": 3.0},
]

AGENTS = [
    {"name": "Bob Arum Sr.", "cut": 0.05, "negotiation_bonus": 0.05, "perks": "Fair deals, great for rookies"},
    {"name": "Dana Mathews", "cut": 0.10, "negotiation_bonus": 0.10, "perks": "Gets you main event spots"},
    {"name": "Ali Kamal", "cut": 0.15, "negotiation_bonus": 0.15, "perks": "Elite negotiator, big contracts"},
    {"name": "Jenny Fields", "cut": 0.08, "negotiation_bonus": 0.08, "perks": "Good all-rounder management"},
    {"name": "Iron Mike Ross", "cut": 0.12, "negotiation_bonus": 0.05, "perks": "Gets you fights fast"},
    {"name": "Scarlett Cruz", "cut": 0.10, "negotiation_bonus": 0.12, "perks": "Brand-building focus"},
]

GYMS = [
    {"name": "Downtown Boxing & Fitness", "specialties": ["striking"], "coach_bonus": 0.10, "monthly_fee": 200},
    {"name": "Chute Box Academy", "specialties": ["striking", "clinch"], "coach_bonus": 0.25, "monthly_fee": 600},
    {"name": "Renzo's BJJ", "specialties": ["grappling"], "coach_bonus": 0.30, "monthly_fee": 500},
    {"name": "AKA Wrestling", "specialties": ["grappling", "clinch"], "coach_bonus": 0.25, "monthly_fee": 600},
    {"name": "Jackson-Wink MMA", "specialties": ["striking", "sparring"], "coach_bonus": 0.20, "monthly_fee": 700},
    {"name": "Tiger Muay Thai", "specialties": ["striking", "clinch"], "coach_bonus": 0.25, "monthly_fee": 400},
    {"name": "Straight Blast Gym", "specialties": ["striking", "grappling", "clinch", "sparring"], "coach_bonus": 0.15, "monthly_fee": 1000},
    {"name": "American Top Team", "specialties": ["striking", "grappling", "sparring"], "coach_bonus": 0.20, "monthly_fee": 900},
]


# ============= NEW REVPAMP FUNCTIONS =============

def calculate_defense_score(durability: float, composure: float, fight_iq: float, is_hurt: bool, is_stunned: bool) -> float:
    """
    Calculate a fighter's overall defensive capability.
    Returns 0-100 defense value.
    """
    base = durability * 0.40 + composure * 0.25 + fight_iq * 0.20
    if is_stunned:
        base *= 0.45
    elif is_hurt:
        base *= 0.65
    return clamp(base, 5.0, 95.0)


def determine_severity(accuracy: float, defense: float, power: float, composure: float, adrenaline: float) -> dict:
    """
    6-tier severity system.
    Returns dict with tier name, damage multiplier, knockdown chance, vision damage.
    """
    strike_value = (accuracy * 0.4 + power * 0.35 + composure * 0.15) * adrenaline
    defense_value = defense * 0.5 + random.gauss(0, 10)
    delta = strike_value - defense_value

    if delta < -20:
        tier_name = "Blocked"
    elif delta < -5:
        tier_name = "Glancing"
    elif delta < 8:
        tier_name = "Clean"
    elif delta < 22:
        tier_name = "Solid"
    elif delta < 38:
        tier_name = "Flush"
    else:
        tier_name = "Devastating"

    tier = SEVERITY_NAMES[tier_name]
    return tier


def check_critical_hit(accuracy: float, composure: float, adrenaline: float) -> bool:
    """
    Critical hit: perfect timing/placement. Double damage.
    Higher accuracy and composure = higher critical chance.
    """
    critical_chance = (accuracy / 200.0) * (1.0 + composure / 300.0) * adrenaline
    # Cap at ~18% base, can reach ~25% with high adrenaline
    return random.random() < min(critical_chance, 0.25)


def get_body_damage_level(body_accumulated: float) -> dict:
    """Return body damage level based on accumulated body damage."""
    for level in reversed(BODY_DAMAGE_LEVELS):
        if body_accumulated >= level["threshold"]:
            return level
    return BODY_DAMAGE_LEVELS[0]


def get_leg_damage_level(leg_damage: float) -> dict:
    """Return leg damage level based on leg damage."""
    for level in reversed(LEG_DAMAGE_LEVELS):
        if leg_damage >= level["threshold"]:
            return level
    return LEG_DAMAGE_LEVELS[0]


def format_round_time(elapsed_seconds: int, round_num: int) -> str:
    """Format elapsed time as 'R2 3:42' for commentary timestamps."""
    remaining = max(0, 300 - elapsed_seconds)
    mins = remaining // 60
    secs = remaining % 60
    return f"R{round_num} {mins}:{secs:02d}"


def calculate_knockout_resistance(fighter) -> float:
    """
    Composite chin/jaw resistance to KO.
    Based on durability, mental toughness, heart, and composure.
    Returns a threshold value — higher = harder to KO.
    """
    return (fighter.attributes.get("durability", 50) * 0.4
            + fighter.attributes.get("mental_toughness", 50) * 0.3
            + fighter.attributes.get("heart", 50) * 0.3)


def calculate_recovery_from_knockdown(fighter) -> float:
    """
    Chance to beat the ref's count after going down.
    Based on heart, durability, composure, and chin.
    Returns probability 0-1.
    """
    return clamp(
        (fighter.attributes.get("heart", 50) * 0.35
         + fighter.attributes.get("durability", 50) * 0.25
         + fighter.attributes.get("composure", 50) * 0.15
         + fighter.attributes.get("mental_toughness", 50) * 0.15) / 100.0,
        0.1, 0.95
    )


def calculate_combo_chance(fight_iq: float, fatigue: float) -> float:
    """
    Probability of throwing a combo instead of a single strike.
    Higher IQ and lower fatigue = more combos.
    """
    if fatigue > 0.8:
        return 0.0
    return min(0.45, (fight_iq / 100.0) * 0.5 * (1.0 - fatigue * 0.8))


def get_reach_advantage_modifier(attacker_reach: int, defender_reach: int) -> dict:
    """
    Returns dict with strike_bonus and takedown_bonus based on reach differential.
    """
    diff = attacker_reach - defender_reach
    return {
        "strike_bonus": clamp(diff * 0.008, -0.12, 0.12),
        "takedown_bonus": clamp(-diff * 0.006, -0.10, 0.10),
        "distance_penalty": clamp(diff * 0.004, -0.08, 0.08) if diff < 0 else 0,
    }


def get_body_level(body_accumulated_damage: float) -> str:
    """Get body damage level name."""
    for level in reversed(BODY_DAMAGE_LEVELS):
        if body_accumulated_damage >= level["threshold"]:
            return level["name"]
    return "healthy"


def get_leg_level(leg_damage: float) -> str:
    """Get leg damage level name."""
    levels = [
        {"name": "destroyed", "threshold": 90},
        {"name": "severe", "threshold": 75},
        {"name": "moderate", "threshold": 50},
        {"name": "minor", "threshold": 25},
        {"name": "healthy", "threshold": 0},
    ]
    for level in levels:
        if leg_damage >= level["threshold"]:
            return level["name"]
    return "healthy"


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


def weighted_random_choice(weights: Dict[str, float]) -> str:
    """Pick key from dict with probability proportional to values."""
    total = sum(weights.values())
    if total <= 0:
        return random.choice(list(weights.keys()))
    r = random.random() * total
    cumulative = 0
    for key, val in weights.items():
        cumulative += val
        if r <= cumulative:
            return key
    return list(weights.keys())[-1]


def calculate_damage_reduction(defender, fatigue: float) -> float:
    """
    Overall damage reduction factor for a defender.
    Returns 0.0-1.0 multiplier applied to incoming damage.
    Higher durability + composure + fight_iq = more damage reduction.
    """
    dur = defender.get_effective_attribute("durability", fatigue)
    comp = defender.get_effective_attribute("composure", fatigue)
    fiq = defender.get_effective_attribute("fight_iq", fatigue)
    return clamp((dur * 0.4 + comp * 0.25 + fiq * 0.15) / 200.0, 0.05, 0.85)


def calculate_critical_multiplier(attacker, defender, fatigue: float) -> float:
    """
    Determine if a critical hit lands and return multiplier.
    A critical doubles the severity tier multiplier.
    """
    acc = attacker.get_effective_attribute("striking_accuracy", fatigue)
    comp = attacker.get_effective_attribute("composure", fatigue)
    adrenaline = 1.0 + max(0, (1.0 - defender.get_effective_attribute("composure", fatigue) / 100.0))

    crit_chance = (acc / 250.0) * (1.0 + comp / 300.0)
    if attacker.attributes.get("heart", 50) > 70:
        crit_chance *= 1.15  # heartier fighters land criticals more under pressure
    if random.random() < min(crit_chance, 0.22):
        return 2.0
    return 1.0


STYLES = {
    "aggressive_striking": {"striking_power": 1.1, "hand_speed": 1.1, "striking_accuracy": 0.95,
                            "wrestling_defense": 0.9, "cardio_drain": 1.15},
    "defensive_striking": {"striking_accuracy": 1.15, "wrestling_defense": 1.1, "hand_speed": 0.9,
                           "striking_power": 0.9, "cardio_drain": 0.9, "parry_chance": 1.15},
    "wrestling_focus": {"takedown_power": 1.2, "takedown_accuracy": 1.15, "top_control": 1.1,
                        "striking_power": 0.85, "striking_accuracy": 0.85},
    "grappling_focus": {"submission_offense": 1.2, "submission_defense": 1.1, "bottom_control": 1.1,
                        "top_control": 1.05, "striking_power": 0.8, "escape_ability": 1.1},
    "clinch_dominance": {"clinch_control": 1.2, "clinch_strikes": 1.15, "clinch_throws": 1.15,
                         "striking_accuracy": 0.9, "takedown_accuracy": 0.9},
    "pressure_fighting": {"aggression": 1.2, "cardio_drain": 1.2, "striking_power": 1.05,
                          "composure": 0.9, "fight_iq": 0.95},
    "volume_striking": {"hand_speed": 1.2, "striking_accuracy": 1.1, "striking_power": 0.8,
                        "cardio_drain": 1.1, "combo_frequency": 1.15},
    "power_hunting": {"striking_power": 1.2, "hand_speed": 0.85, "striking_accuracy": 0.9,
                      "cardio_drain": 0.95, "counter_power": 1.25},
    "leg_kick_focus": {"kick_power": 1.2, "kick_accuracy": 1.1, "kick_speed": 1.05,
                       "cardio_drain": 1.1, "striking_power": 0.9},
    "body_shot_focus": {"striking_power": 1.15, "striking_accuracy": 1.1, "cardio_drain": 1.15,
                        "kick_power": 0.9, "body_damage_bonus": 1.25},
    "ground_and_pound": {"top_control": 1.2, "striking_power": 1.1, "takedown_accuracy": 1.1,
                         "submission_offense": 0.8, "ground_strike_damage": 1.2},
    "submission_hunting": {"submission_offense": 1.25, "bottom_control": 1.1, "top_control": 1.05,
                           "striking_power": 0.75, "submission_defense": 1.05},
    "boxing_focus": {"striking_power": 1.15, "hand_speed": 1.1, "striking_accuracy": 1.1,
                     "kick_power": 0.7, "kick_accuracy": 0.7, "clinch_control": 0.8},
    "kickboxing_focus": {"striking_power": 1.1, "kick_power": 1.1, "hand_speed": 1.05,
                         "clinch_control": 0.85, "takedown_accuracy": 0.85},
    "muay_thai_focus": {"clinch_control": 1.2, "clinch_strikes": 1.2, "kick_power": 1.1,
                        "wrestling_defense": 0.85, "takedown_accuracy": 0.85},
    "counter_striker": {"striking_accuracy": 1.2, "hand_speed": 1.05, "composure": 1.1,
                        "striking_power": 0.95, "counter_power": 1.3, "defensive_striking": 1.15},
    "brawler": {"striking_power": 1.25, "durability": 1.1, "aggression": 1.15,
                "striking_accuracy": 0.88, "cardio_drain": 1.2, "heart": 1.1},
}

STRATEGY_EFFECTIVENESS = {
    # attacker_strategy -> { defender_strategy -> effectiveness_modifier }
    "aggressive_striking": {"defensive_striking": 0.6, "wrestling_focus": 0.7, "clinch_dominance": 0.65, "pressure_fighting": 0.9},
    "defensive_striking": {"aggressive_striking": 1.3, "volume_striking": 0.8, "power_hunting": 1.1},
    "wrestling_focus": {"submission_hunting": 0.6, "clinch_dominance": 0.7, "grappling_focus": 0.8},
    "grappling_focus": {"ground_and_pound": 0.6, "wrestling_focus": 1.3, "submission_hunting": 0.9},
    "clinch_dominance": {"wrestling_focus": 1.2, "aggressive_striking": 0.7, "kickboxing_focus": 1.1},
    "pressure_fighting": {"defensive_striking": 0.7, "volume_striking": 1.1, "power_hunting": 0.8},
    "volume_striking": {"power_hunting": 0.5, "defensive_striking": 1.0, "counter_striker": 0.6},
    "power_hunting": {"volume_striking": 1.4, "pressure_fighting": 1.1, "brawler": 0.8},
    "leg_kick_focus": {"kickboxing_focus": 0.7, "clinch_dominance": 1.2, "boxing_focus": 1.3},
    "body_shot_focus": {"leg_kick_focus": 0.8, "pressure_fighting": 1.3, "brawler": 1.1},
    "ground_and_pound": {"submission_hunting": 0.6, "grappling_focus": 0.9, "wrestling_focus": 1.2},
    "submission_hunting": {"ground_and_pound": 0.75, "wrestling_focus": 1.1, "grappling_focus": 0.85},
    "boxing_focus": {"kickboxing_focus": 0.6, "leg_kick_focus": 0.5, "aggressive_striking": 0.95},
    "kickboxing_focus": {"boxing_focus": 1.3, "muay_thai_focus": 0.9, "leg_kick_focus": 0.8},
    "muay_thai_focus": {"kickboxing_focus": 1.0, "wrestling_focus": 0.9, "clinch_dominance": 0.85},
    "counter_striker": {"aggressive_striking": 1.2, "power_hunting": 1.3, "brawler": 0.9},
    "brawler": {"counter_striker": 0.5, "defensive_striking": 0.7, "pressure_fighting": 1.2},
}

ATTR_MIN = 0
ATTR_MAX = 100

ARCHETYPES = [
    "brawler", "counter_striker", "wrestler", "submission_artist",
    "kickboxer", "boxer", "muay_thai", "clinch_fighter", "balanced"
]

FIRST_NAMES = [
    "James","John","Robert","Michael","William","David","Richard","Joseph",
    "Thomas","Charles","Chris","Daniel","Matthew","Anthony","Mark","Donald",
    "Steven","Paul","Andrew","Joshua","Kenneth","Kevin","Brian","George",
    "Timothy","Ronald","Edward","Jason","Jeffrey","Ryan","Jacob","Gary",
    "Nicholas","Eric","Jonathan","Stephen","Larry","Justin","Scott","Brandon",
    "Benjamin","Samuel","Raymond","Gregory","Frank","Alexander","Patrick",
    "Jack","Dennis","Jerry","Tyler","Aaron","Jose","Nathan","Henry",
    "Douglas","Peter","Adam","Zachary","Walter","Andre","Kyle","Mason",
    "Luis","Jorge","Carlos","Diego","Rafael","Pedro","Miguel","Antonio",
    "Victor","Eduardo","Fernando","Alex","Sean","Derek","Marcus","Adrian",
    "Akira","Takeshi","Kenji","Satoshi","Yuki","Hiroshi","Jun","Hyun",
    "Sung","Min","Jin","Dae","Woo","Tyrone","Jamel","Darnell","DeShawn",
    "Tevin","Terrell","Kendrick","DaMarcus","Israel","Ivan","Dmitri",
    "Sergei","Alexei","Nikolai","Vladimir","Mikhail","Pavel","Conor","Liam",
    "Declan","Rory","Finn","Cian","Mateusz","Jakub","Krzysztof","Tomasz",
    "Piotr","Przemek","Anderson","Josef","Hector","Marco","Andres",
    "Ricardo","Alejandro","Francisco","Erik","Igor","Khalil","Rashad",
    "Jamal","DeAndre","Jermaine","Kendall","Zion","Kai","Koji","Ryo",
    "Takeo","Hideo","Sho","Sora","Blake","Cole","Brett","Chad","Dustin",
    "Kurt","Ross","Drew","Jake","Max","Leo",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson",
    "Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson",
    "White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker",
    "Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill",
    "Flores","Green","Adams","Nelson","Baker","Hall","Rivera","Campbell",
    "Mitchell","Carter","Roberts","Gomez","Phillips","Evans","Turner",
    "Diaz","Parker","Cruz","Edwards","Collins","Reyes","Stewart","Morris",
    "Morales","Murphy","Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper",
    "Peterson","Bailey","Reed","Kelly","Howard","Ramos","Kim","Cox",
    "Ward","Richardson","Watson","Brooks","Chavez","Wood","James","Bennett",
    "Gray","Mendoza","Ruiz","Hughes","Price","Alvarez","Castillo","Sanders",
    "Patel","Myers","Long","Ross","Foster","Jimenez","Powell","Jenkins",
    "Perry","Russell","Sullivan","Bell","Coleman","Butler","Henderson",
    "Barnes","Fisher","Vasquez","Simmons","Romero","Jordan","Patterson",
    "Alexander","Hamilton","Graham","Reynolds","Griffin","Wallace",
    "Moreno","West","Cole","Hayes","Bryant","Herrera","Gibson","Ellis",
    "Medina","Owens","Silva","Santos","Oliveira","Souza","Lima","Pereira",
    "Costa","Ferreira","Rodrigues","Almeida","Nascimento","Araujo","Barbosa",
    "Carvalho","Yamamoto","Tanaka","Nakamura","Sato","Takahashi","Suzuki",
    "Ito","Watanabe","Kobayashi","Kimura","Shimizu","Yoshida","Matsumoto",
    "Hasegawa","Park","Choi","Jung","Kim","Cho","Yoon","Shin",
    "Nowak","Kowalski","Wisniewski","Zielinski","Jankowski","Kaminski",
    "Lewandowski","Zajac","Kowalczyk","O'Brien","Ryan","Kelly","Walsh",
    "McCarthy","Sullivan","Flynn","Gallagher","O'Neill","Doyle","Kennedy",
    "Volkov","Ivanov","Petrov","Sokolov","Kuznetsov","Popov","Vasiliev",
    "Fedorov","Morozov","Novikov","Kozlov","Lebedev","Khalil","Abdul",
    "Okonkwo","Nnamdi","Okafor","Abebe","Mensah","Owusu","Kamau",
]

NATIONALITIES = [
    "American", "Brazilian", "Russian", "Japanese", "British", "Canadian",
    "French", "Dutch", "Australian", "Polish", "Korean", "Mexican",
    "Chinese", "Swedish", "Irish", "Nigerian", "New Zealander", "German",
    "Italian", "Spanish", "Ukrainian", "Cuban", "Jamaican", "South African",
    "Swiss", "Belgian", "Norwegian", "Finnish", "Danish", "Icelandic"
]

REGIONS = {
    "American": ["California", "Texas", "New York", "Florida", "Ohio", "Colorado", "Nevada", "Arizona"],
    "Brazilian": ["Rio de Janeiro", "Sao Paulo", "Bahia", "Minas Gerais", "Ceara"],
    "Russian": ["Moscow", "St. Petersburg", "Dagestan", "Chechnya", "Siberia"],
    "Japanese": ["Tokyo", "Osaka", "Yokohama", "Nagoya", "Okinawa"],
    "British": ["London", "Manchester", "Liverpool", "Birmingham", "Scotland"],
    "Canadian": ["Ontario", "Quebec", "British Columbia", "Alberta", "Nova Scotia"],
    "French": ["Paris", "Lyon", "Marseille", "Bordeaux", "Toulouse"],
    "Dutch": ["Amsterdam", "Rotterdam", "Utrecht", "The Hague", "Eindhoven"],
    "Australian": ["Sydney", "Melbourne", "Brisbane", "Perth", "Gold Coast"],
    "Polish": ["Warsaw", "Krakow", "Gdansk", "Wroclaw", "Poznan"],
    "Korean": ["Seoul", "Busan", "Incheon", "Daegu", "Ulsan"],
    "Mexican": ["Mexico City", "Guadalajara", "Monterrey", "Tijuana", "Puebla"],
    "Chinese": ["Beijing", "Shanghai", "Shenzhen", "Guangzhou", "Chengdu"],
    "Swedish": ["Stockholm", "Gothenburg", "Malmo", "Uppsala", "Linkoping"],
    "Irish": ["Dublin", "Cork", "Galway", "Limerick", "Belfast"],
    "Nigerian": ["Lagos", "Abuja", "Port Harcourt", "Ibadan", "Kano"],
    "New Zealander": ["Auckland", "Wellington", "Christchurch", "Hamilton", "Tauranga"],
    "German": ["Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt"],
    "Italian": ["Rome", "Milan", "Naples", "Turin", "Florence"],
    "Spanish": ["Madrid", "Barcelona", "Valencia", "Seville", "Bilbao"],
    "Ukrainian": ["Kyiv", "Kharkiv", "Odessa", "Dnipro", "Lviv"],
    "Cuban": ["Havana", "Santiago", "Camaguey", "Holguin", "Santa Clara"],
    "Jamaican": ["Kingston", "Montego Bay", "Ocho Rios", "Negril", "Spanish Town"],
    "South African": ["Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth"],
    "Swiss": ["Zurich", "Geneva", "Basel", "Bern", "Lausanne"],
    "Belgian": ["Brussels", "Antwerp", "Ghent", "Bruges", "Liege"],
    "Norwegian": ["Oslo", "Bergen", "Trondheim", "Stavanger", "Tromso"],
    "Finnish": ["Helsinki", "Espoo", "Tampere", "Turku", "Oulu"],
    "Danish": ["Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg"],
    "Icelandic": ["Reykjavik", "Kopavogur", "Hafnarfjordur", "Akureyri", "Gardabaer"]
}

TRAITS = [
    {"id": "heavy_hands", "name": "Heavy Hands", "description": "+5 striking power", "effects": {"striking_power": 5}},
    {"id": "iron_chin", "name": "Iron Chin", "description": "+5 durability", "effects": {"durability": 5}},
    {"id": "cardio_king", "name": "Cardio King", "description": "+5 cardio", "effects": {"cardio": 5}},
    {"id": "mat_wizard", "name": "Mat Wizard", "description": "+5 wrestling defense", "effects": {"wrestling_defense": 5}},
    {"id": "sniper", "name": "Sniper", "description": "+5 striking accuracy", "effects": {"striking_accuracy": 5}},
    {"id": "natural_athlete", "name": "Natural Athlete", "description": "+3 all physical attributes", "effects": {attr: 3 for attr in ["athleticism", "hand_speed", "cardio", "durability", "striking_power", "striking_accuracy", "takedown_power", "takedown_accuracy"]}},
    {"id": "iron_will", "name": "Iron Will", "description": "+5 mental toughness & composure", "effects": {"mental_toughness": 5, "composure": 5}},
    {"id": "fast_hands", "name": "Fast Hands", "description": "+5 hand speed", "effects": {"hand_speed": 5}},
]

PERSONALITIES = [
    {"id": "charismatic", "name": "Charismatic", "description": "Natural charisma, fans love you", "effects": {"charisma": 10}},
    {"id": "intimidating", "name": "Intimidating", "description": "Strikes fear into opponents", "effects": {"aggression": 8, "charisma": -3}},
    {"id": "humble", "name": "Humble", "description": "Respected by fans and media", "effects": {"composure": 5, "charisma": 3}},
    {"id": "cocky", "name": "Cocky", "description": "Loves the spotlight", "effects": {"charisma": 5, "aggression": 3, "composure": -2}},
    {"id": "quiet", "name": "Quiet", "description": "Lets fighting do the talking", "effects": {"composure": 8, "charisma": -5}},
    {"id": "savage", "name": "Savage", "description": "No mercy in the cage", "effects": {"aggression": 10, "heart": 3}},
]

def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(value, max_val))

def random_roll(min_val: int = 0, max_val: int = 100) -> int:
    return random.randint(min_val, max_val)

def calculate_effective_attribute(base_attr: float, fatigue: float = 0.0, injury_penalty: float = 0.0) -> int:
    modifier = 1.0 - (fatigue * 0.3) - injury_penalty
    return int(clamp(base_attr * modifier, ATTR_MIN, ATTR_MAX))

def get_weight_class(weight_lbs: float) -> str:
    for wc in WEIGHT_CLASSES:
        if wc["min"] <= weight_lbs <= wc["max"]:
            return wc["name"]
    return "Catchweight"

def get_weight_class_index(weight_class: str) -> int:
    for i, wc in enumerate(WEIGHT_CLASSES):
        if wc["name"] == weight_class:
            return i
    return -1

def format_currency(amount: float) -> str:
    return f"${amount:,.2f}"


def gaussian_random(mean: float = 50.0, std_dev: float = 15.0, min_val: int = 0, max_val: int = 100) -> int:
    val = random.gauss(mean, std_dev)
    return int(clamp(val, min_val, max_val))

def calculate_rating_from_attrs(attributes: Dict[str, float], physical_attrs: List[str], mental_attrs: List[str]) -> float:
    phys = sum(attributes.get(a, 50) for a in physical_attrs) / len(physical_attrs)
    ment = sum(attributes.get(a, 50) for a in mental_attrs) / len(mental_attrs)
    return phys * 0.7 + ment * 0.3

def generate_name() -> Tuple[str, str]:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    return first, last

def get_age_modifier(age: int) -> float:
    if age < 27:
        return age / 27
    elif age > 30:
        return max(0.7, 1.0 - (age - 30) * 0.02)
    return 1.0

def calculate_strength_of_schedule(wins: int, losses: int, opponent_ratings: List[float]) -> float:
    if not opponent_ratings:
        return 0.0
    avg_opp = sum(opponent_ratings) / len(opponent_ratings)
    return avg_opp / 100.0

PRO_TIERS = [
    {"name": "Regional", "base_pay": 2000, "win_bonus": 2000, "perf_bonus": 5000, "ranking_weight": 1.0},
    {"name": "National", "base_pay": 8000, "win_bonus": 8000, "perf_bonus": 15000, "ranking_weight": 2.0},
    {"name": "World", "base_pay": 25000, "win_bonus": 25000, "perf_bonus": 50000, "ranking_weight": 3.0},
]

AGENTS = [
    {"name": "Bob Arum Sr.", "cut": 0.05, "negotiation_bonus": 0.05, "perks": "Fair deals, great for rookies"},
    {"name": "Dana Mathews", "cut": 0.10, "negotiation_bonus": 0.10, "perks": "Gets you main event spots"},
    {"name": "Ali Kamal", "cut": 0.15, "negotiation_bonus": 0.15, "perks": "Elite negotiator, big contracts"},
    {"name": "Jenny Fields", "cut": 0.08, "negotiation_bonus": 0.08, "perks": "Good all-rounder management"},
    {"name": "Iron Mike Ross", "cut": 0.12, "negotiation_bonus": 0.05, "perks": "Gets you fights fast"},
    {"name": "Scarlett Cruz", "cut": 0.10, "negotiation_bonus": 0.12, "perks": "Brand-building focus"},
]

GYMS = [
    {"name": "Downtown Boxing & Fitness", "specialties": ["striking"], "coach_bonus": 0.10, "monthly_fee": 200},
    {"name": "Chute Box Academy", "specialties": ["striking", "clinch"], "coach_bonus": 0.25, "monthly_fee": 600},
    {"name": "Renzo's BJJ", "specialties": ["grappling"], "coach_bonus": 0.30, "monthly_fee": 500},
    {"name": "AKA Wrestling", "specialties": ["grappling", "clinch"], "coach_bonus": 0.25, "monthly_fee": 600},
    {"name": "Jackson-Wink MMA", "specialties": ["striking", "sparring"], "coach_bonus": 0.20, "monthly_fee": 700},
    {"name": "Tiger Muay Thai", "specialties": ["striking", "clinch"], "coach_bonus": 0.25, "monthly_fee": 400},
    {"name": "Straight Blast Gym", "specialties": ["striking", "grappling", "clinch", "sparring"], "coach_bonus": 0.15, "monthly_fee": 1000},
    {"name": "American Top Team", "specialties": ["striking", "grappling", "sparring"], "coach_bonus": 0.20, "monthly_fee": 900},
]
