from typing import Dict, List, Optional, Tuple
import random
import math
import json
import os
import numpy as np

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
_config_cache: Dict[str, dict] = {}

def load_config(name: str) -> dict:
    if name in _config_cache:
        return _config_cache[name]
    path = os.path.join(CONFIG_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)
        _config_cache[name] = cfg
        return cfg
    return {}

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

# Realistic height/reach ranges per weight class (inches)
HEIGHT_REACH_RANGES = {
    "Flyweight":       {"height_min": 60, "height_max": 66, "reach_min": 62, "reach_max": 69},
    "Bantamweight":    {"height_min": 62, "height_max": 68, "reach_min": 64, "reach_max": 71},
    "Featherweight":   {"height_min": 63, "height_max": 70, "reach_min": 65, "reach_max": 73},
    "Lightweight":     {"height_min": 65, "height_max": 72, "reach_min": 67, "reach_max": 75},
    "Welterweight":    {"height_min": 66, "height_max": 74, "reach_min": 68, "reach_max": 77},
    "Middleweight":    {"height_min": 68, "height_max": 76, "reach_min": 70, "reach_max": 79},
    "Light Heavyweight": {"height_min": 70, "height_max": 78, "reach_min": 72, "reach_max": 81},
    "Heavyweight":     {"height_min": 71, "height_max": 80, "reach_min": 74, "reach_max": 84},
}

def get_height_reach_range(weight_class: str) -> dict:
    return HEIGHT_REACH_RANGES.get(weight_class, {"height_min": 64, "height_max": 74, "reach_min": 66, "reach_max": 78})

ATTR_MIN = 0
ATTR_MAX = 100

# --- Severity Tiers (6-tier strike grading) ---
SEVERITY_TIERS = [
    {"name": "Blocked",     "mult": 0.06, "score": 0.1,  "knockdown_chance": 0.0,   "vision_damage": 0.0},
    {"name": "Glancing",    "mult": 0.32, "score": 0.3,  "knockdown_chance": 0.0,   "vision_damage": 0.01},
    {"name": "Clean",       "mult": 0.75, "score": 0.7,  "knockdown_chance": 0.015, "vision_damage": 0.025},
    {"name": "Solid",       "mult": 1.08, "score": 1.0,  "knockdown_chance": 0.035, "vision_damage": 0.045},
    {"name": "Flush",       "mult": 1.60, "score": 1.3,  "knockdown_chance": 0.08,  "vision_damage": 0.09},
    {"name": "Devastating", "mult": 2.35, "score": 1.8,  "knockdown_chance": 0.14,  "vision_damage": 0.13},
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
    {"id": "heavy_hands", "name": "Heavy Hands", "description": "+8 striking power, -3 hand speed", "effects": {"striking_power": 8, "hand_speed": -3}},
    {"id": "iron_chin", "name": "Iron Chin", "description": "+6 durability, +4 danger_recognition", "effects": {"durability": 6, "danger_recognition": 4}},
    {"id": "cardio_king", "name": "Cardio King", "description": "+6 cardio, +3 pace_management", "effects": {"cardio": 6, "pace_management": 3}},
    {"id": "mat_wizard", "name": "Mat Wizard", "description": "+5 wrestling_defense, +5 guard_retention, +5 chain_wrestling", "effects": {"wrestling_defense": 5, "guard_retention": 5, "chain_wrestling": 5}},
    {"id": "sniper", "name": "Sniper", "description": "+6 striking accuracy, +4 counter_timing", "effects": {"striking_accuracy": 6, "counter_timing": 4}},
    {"id": "natural_athlete", "name": "Natural Athlete", "description": "+4 athleticism, hand_speed, cardio, durability, explosiveness, flexibility", "effects": {attr: 4 for attr in ["athleticism", "hand_speed", "cardio", "durability", "striking_power", "striking_accuracy", "takedown_power", "takedown_accuracy", "explosiveness", "flexibility"]}},
    {"id": "iron_will", "name": "Iron Will", "description": "+5 mental_toughness, +5 composure", "effects": {"mental_toughness": 5, "composure": 5}},
    {"id": "fast_hands", "name": "Fast Hands", "description": "+6 hand_speed, +3 parrying", "effects": {"hand_speed": 6, "parrying": 3}},
    {"id": "elusive", "name": "Elusive", "description": "+6 head_movement, +4 footwork_defense", "effects": {"head_movement": 6, "footwork_defense": 4}},
    {"id": "scrappy", "name": "Scrappy", "description": "+4 scrambling, +4 chain_wrestling, +4 heart", "effects": {"scrambling": 4, "chain_wrestling": 4, "heart": 4}},
    {"id": "submission_ace", "name": "Submission Ace", "description": "+5 submission_offense, +5 submission_awareness, +4 flexibility", "effects": {"submission_offense": 5, "submission_awareness": 5, "flexibility": 4}},
    {"id": "granite_jaw", "name": "Granite Jaw", "description": "+6 durability, +3 mental_toughness, -2 head_movement", "effects": {"durability": 6, "mental_toughness": 3, "head_movement": -2}},
    {"id": "precision_striker", "name": "Precision Striker", "description": "+5 striking_accuracy, +3 counter_timing, +3 head_movement", "effects": {"striking_accuracy": 5, "counter_timing": 3, "head_movement": 3}},
    {"id": "dirty_fighter", "name": "Dirty Fighter", "description": "+4 clinch_strikes, +4 clinch_throws, +4 aggression", "effects": {"clinch_strikes": 4, "clinch_throws": 4, "aggression": 4}},
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


def weight_cut_penalty(weight_to_cut_lbs: float, hydration_level: float = 80.0) -> Dict[str, float]:
    """
    Full weight cut penalty system with small-cut bonuses and large-cut penalties.
    hydration_level (0-100) modulates the penalties post-rehydration.
    """
    if weight_to_cut_lbs <= 0:
        return {"cardio_penalty": 0.0, "durability_penalty": 0.0, "strength_penalty": 0.0,
                "speed_penalty": 0.0, "chin_penalty": 0.0}

    hydration_factor = hydration_level / 80.0  # <80 = worse, >80 = better

    if weight_to_cut_lbs <= 5:
        # Small cut gives bonuses (fighter is tight/lean)
        return {"cardio_penalty": -0.03 * hydration_factor,
                "durability_penalty": -0.01,
                "strength_penalty": -0.02,
                "speed_penalty": -0.02,
                "chin_penalty": 0.0}

    excess_cut = weight_to_cut_lbs - 5
    cardio_penalty = min(0.35, excess_cut * 0.045 * (2.0 - hydration_factor))
    durability_penalty = min(0.28, excess_cut * 0.035 * (2.0 - hydration_factor))
    strength_penalty = min(0.22, excess_cut * 0.030 * (2.0 - hydration_factor))
    speed_penalty = min(0.18, excess_cut * 0.025 * (2.0 - hydration_factor))
    chin_penalty = min(0.20, excess_cut * 0.035 * (2.0 - hydration_factor))

    return {"cardio_penalty": cardio_penalty, "durability_penalty": durability_penalty,
            "strength_penalty": strength_penalty, "speed_penalty": speed_penalty,
            "chin_penalty": chin_penalty}


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


def calculate_strength_of_schedule(opponent_ratings: List[float]) -> float:
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


# ============= STANCE CONSTANTS =============

STANCES = ["orthodox", "southpaw"]

def get_stance_for_background(background: str) -> str:
    southpaw_high = ["taekwondo", "karate", "muay_thai", "capoeira"]
    orthodox_high = ["boxing", "wrestling", "judo"]
    if background in southpaw_high:
        return "southpaw" if random.random() < 0.55 else "orthodox"
    elif background in orthodox_high:
        return "orthodox" if random.random() < 0.65 else "southpaw"
    else:
        return random.choice(STANCES)

def get_stance_modifiers(attacker_stance: str, defender_stance: str) -> dict:
    if attacker_stance == defender_stance:
        return {"power_mod": 1.0, "speed_mod": 1.0, "accuracy_mod": 1.02, "clinch_mod": 1.1}
    else:
        return {"power_mod": 1.06, "speed_mod": 0.98, "accuracy_mod": 0.97, "clinch_mod": 0.95}

# ============= FEINT SYSTEM =============

FEINT_BASE_CHANCE = 0.05
FEINT_MAX_CHANCE = 0.15

def calculate_feint_chance(fight_iq: float, strategy_modifiers: dict, counter_timing: float = 50) -> float:
    base = FEINT_BASE_CHANCE + (fight_iq / 1000.0)
    strat_bonus = strategy_modifiers.get("feint_chance", 0.0)
    ct_bonus = counter_timing / 800.0
    return min(FEINT_MAX_CHANCE, base + strat_bonus + ct_bonus)

def calculate_feint_recognition(fight_iq: float, adaptability: float,
                                 parrying: float = 50, footwork_defense: float = 50) -> float:
    return min(0.45, (fight_iq + adaptability + parrying + footwork_defense) / 500.0)

# ============= BREATHING SYSTEM =============

BREATHING_THRESHOLDS = {
    "normal": {"min": 70, "cardio_recovery_mod": 1.0, "body_damage_mod": 1.0},
    "impaired": {"min": 50, "cardio_recovery_mod": 0.90, "body_damage_mod": 1.1},
    "struggling": {"min": 30, "cardio_recovery_mod": 0.75, "body_damage_mod": 1.2},
    "critical": {"min": 0, "cardio_recovery_mod": 0.55, "body_damage_mod": 1.35},
}
BREATHING_RECOVERY_BETWEEN_ROUNDS = 15

def get_breathing_level(breathing_capacity: float) -> str:
    for level in ["normal", "impaired", "struggling", "critical"]:
        if breathing_capacity >= BREATHING_THRESHOLDS[level]["min"]:
            return level
    return "critical"

def get_breathing_recovery_modifier(breathing_capacity: float) -> float:
    level = get_breathing_level(breathing_capacity)
    return BREATHING_THRESHOLDS[level]["cardio_recovery_mod"]

# ============= ENHANCED COMBO SYSTEM =============

COMBOS = [
    {"id": "1-2", "strikes": ["jab", "cross"], "power_bonus": 0.15, "stamina_mult": 1.1, "iq_req": 15, "type": "striking"},
    {"id": "1-2-3", "strikes": ["jab", "cross", "hook"], "power_bonus": 0.25, "stamina_mult": 1.3, "iq_req": 30, "type": "striking"},
    {"id": "jab-hook", "strikes": ["jab", "hook"], "power_bonus": 0.20, "stamina_mult": 1.15, "iq_req": 20, "type": "striking"},
    {"id": "double-jab-cross", "strikes": ["jab", "jab", "cross"], "power_bonus": 0.20, "stamina_mult": 1.25, "iq_req": 25, "type": "striking"},
    {"id": "uppercut-hook", "strikes": ["uppercut", "hook"], "power_bonus": 0.35, "stamina_mult": 1.4, "iq_req": 35, "type": "striking"},
    {"id": "3-2-body", "strikes": ["jab", "cross", "body_shot"], "power_bonus": 0.20, "stamina_mult": 1.2, "iq_req": 25, "type": "striking"},
    {"id": "jab-cross-hook", "strikes": ["jab", "cross", "hook"], "power_bonus": 0.28, "stamina_mult": 1.35, "iq_req": 32, "type": "striking"},
    {"id": "hook-uppercut-hook", "strikes": ["hook", "uppercut", "hook"], "power_bonus": 0.40, "stamina_mult": 1.5, "iq_req": 42, "type": "striking"},
    {"id": "jab-cross-kick", "strikes": ["jab", "cross", "kick"], "power_bonus": 0.30, "stamina_mult": 1.45, "iq_req": 35, "type": "striking"},
    {"id": "cross-hook-kick", "strikes": ["cross", "hook", "kick"], "power_bonus": 0.35, "stamina_mult": 1.5, "iq_req": 40, "type": "striking"},
    {"id": "knee-elbow-knee", "strikes": ["knee", "elbow", "knee"], "power_bonus": 0.40, "stamina_mult": 1.5, "iq_req": 38, "type": "clinch"},
    {"id": "elbow-elbow-knee", "strikes": ["elbow", "elbow", "knee"], "power_bonus": 0.35, "stamina_mult": 1.4, "iq_req": 35, "type": "clinch"},
    {"id": "ground-hammer-punch", "strikes": ["hammerfist", "punch", "hammerfist"], "power_bonus": 0.25, "stamina_mult": 1.3, "iq_req": 20, "type": "ground"},
    {"id": "ground-elbow-hammer", "strikes": ["elbow", "hammerfist", "punch"], "power_bonus": 0.30, "stamina_mult": 1.35, "iq_req": 25, "type": "ground"},
]

def get_combos_for_position(position: str) -> list:
    type_map = {"standing": "striking", "clinch": "clinch", "ground": "ground"}
    pos_type = type_map.get(position, "striking")
    return [c for c in COMBOS if c.get("type") == pos_type]

# ============= REBUILT SEVERITY & DEFENSE (uses new multi-stat system) =============

def calculate_defense_score(durability: float, composure: float, fight_iq: float,
                            is_hurt: bool, is_stunned: bool,
                            head_movement: float = 50, blocking: float = 50) -> float:
    """
    Calculate a fighter's overall defensive capability (standing defense).
    Returns 0-100 defense value.
    """
    base = durability * 0.25 + composure * 0.20 + fight_iq * 0.15 + head_movement * 0.20 + blocking * 0.20
    if is_stunned:
        base *= 0.45
    elif is_hurt:
        base *= 0.65
    return clamp(base, 5.0, 95.0)


def determine_severity(accuracy: float, defense: float, power: float, composure: float,
                       adrenaline: float, attacker_stats: dict = None,
                       defender_stats: dict = None, target: str = "head") -> dict:
    """
    6-tier severity system.
    Offense vs Defense with numpy-based noise for realistic distributions.
    defense * 0.5 scaling keeps offense/defense comparable (accuracy composite
    in _perform_strike is typically 27-50 for even-stat fighters, while
    defense is 30-70, so halving aligns both sides).
    """
    off_val = (accuracy * 0.40 + power * 0.35 + composure * 0.15) * adrenaline
    off_val += float(np.random.normal(0, 5))

    def_val = defense * 0.50
    def_val += float(np.random.normal(0, 4))

    delta = off_val - def_val

    # Tier thresholds — tuned so same-stat avg-vs-avg centers on Clean/Solid
    # With off_val ≈ 40, def_val ≈ 22, delta ≈ 18 → Solid threshold
    if delta < -10:
        tier_name = "Blocked"
    elif delta < 4:
        tier_name = "Glancing"
    elif delta < 20:
        tier_name = "Clean"
    elif delta < 38:
        tier_name = "Solid"
    elif delta < 56:
        tier_name = "Flush"
    else:
        tier_name = "Devastating"

    tier = dict(SEVERITY_NAMES.get(tier_name, SEVERITY_NAMES["Clean"]))

    # Blocking skill can downgrade severity by one tier
    if defender_stats:
        blocking = defender_stats.get("blocking", 50)
        if blocking > 70 and tier_name in ("Flush", "Devastating") and random.random() < 0.25:
            tier = SEVERITY_NAMES.get({"Flush": "Solid", "Devastating": "Flush"}.get(tier_name, tier_name), tier)

    return tier


def check_critical_hit(accuracy: float, composure: float, adrenaline: float,
                       counter_timing: float = 50, opponent_head_movement: float = 50,
                       opponent_danger_recognition: float = 50) -> bool:
    """
    Critical hit: perfect timing/placement. Double damage.
    Uses accuracy, composure, counter_timing (for creating openings),
    vs opponent's head_movement and danger_recognition.
    """
    base_chance = (accuracy / 200.0) * (1.0 + composure / 300.0) * adrenaline
    # Counter timing bonus — good counter-strikers create openings
    ct_bonus = counter_timing / 500.0
    # Defender's defensive abilities reduce crit chance
    def_reduction = (opponent_head_movement + opponent_danger_recognition) / 800.0
    critical_chance = (base_chance + ct_bonus) * (1.0 - def_reduction)
    return random.random() < min(critical_chance, 0.22)


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
    Uses more stats for depth: durability, mental toughness, heart, composure,
    danger_recognition (sensing when to cover up), and neck strength (not a separate stat,
    but derived from durability + athleticism).
    Returns a threshold value — higher = harder to KO.
    """
    dur = fighter.attributes.get("durability", 50)
    mt = fighter.attributes.get("mental_toughness", 50)
    heart = fighter.attributes.get("heart", 50)
    comp = fighter.attributes.get("composure", 50)
    dr = fighter.attributes.get("danger_recognition", 50)
    ath = fighter.attributes.get("athleticism", 50)
    return (dur * 0.30 + mt * 0.20 + heart * 0.15 + comp * 0.15 + dr * 0.10 + ath * 0.10)


def calculate_recovery_from_knockdown(fighter) -> float:
    """
    Chance to beat the ref's count after going down.
    Uses heart, durability, composure, mental toughness, fighting spirit.
    Returns probability 0-1.
    """
    return clamp(
        (fighter.attributes.get("heart", 50) * 0.30
         + fighter.attributes.get("durability", 50) * 0.20
         + fighter.attributes.get("composure", 50) * 0.15
         + fighter.attributes.get("mental_toughness", 50) * 0.15
         + fighter.attributes.get("danger_recognition", 50) * 0.10
         + fighter.attributes.get("adaptability", 50) * 0.10) / 100.0,
        0.05, 0.95
    )


def calculate_combo_chance(fight_iq: float, fatigue: float, pace_management: float = 50) -> float:
    """
    Probability of throwing a combo instead of a single strike.
    Higher IQ, pace_management, and lower fatigue = more combos.
    """
    if fatigue > 0.85:
        return 0.0
    pm_bonus = (pace_management / 100.0) * 0.15
    return min(0.50, (fight_iq / 100.0) * 0.5 * (1.0 - fatigue * 0.8) + pm_bonus)


def get_reach_advantage_modifier(attacker_reach: int, defender_reach: int,
                                 attacker_height: int = 0, defender_height: int = 0) -> dict:
    """
    Returns dict with strike_bonus and takedown_bonus based on reach differential,
    and height differential for takedown/clinch.
    """
    reach_diff = attacker_reach - defender_reach
    height_diff = attacker_height - defender_height
    return {
        "strike_bonus": clamp(reach_diff * 0.008, -0.15, 0.15),
        "takedown_bonus": clamp(-reach_diff * 0.006 - height_diff * 0.003, -0.15, 0.15),
        "clinch_bonus": clamp(-reach_diff * 0.004 + height_diff * 0.002, -0.10, 0.10),
        "kick_bonus": clamp(reach_diff * 0.005 + height_diff * 0.004, -0.10, 0.12),
        "defense_bonus": clamp(reach_diff * -0.003, -0.08, 0.08),
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
        "counter_striker": phys.get("counter_timing", 50) + phys.get("head_movement", 50) + phys.get("striking_accuracy", 50) + phys.get("composure", 50),
        "wrestler": phys.get("takedown_power", 50) + phys.get("takedown_accuracy", 50) + phys.get("top_control", 50) + phys.get("chain_wrestling", 50),
        "submission_artist": phys.get("submission_offense", 50) + phys.get("submission_defense", 50) + phys.get("submission_awareness", 50) + phys.get("bottom_control", 50),
        "kickboxer": phys.get("kick_power", 50) + phys.get("kick_accuracy", 50) + phys.get("kick_speed", 50) + phys.get("footwork_defense", 50),
        "boxer": phys.get("striking_power", 50) + phys.get("hand_speed", 50) + phys.get("striking_accuracy", 50) + phys.get("head_movement", 50),
        "muay_thai": phys.get("clinch_control", 50) + phys.get("clinch_strikes", 50) + phys.get("kick_power", 50) + phys.get("blocking", 50),
        "clinch_fighter": phys.get("clinch_control", 50) + phys.get("clinch_throws", 50) + phys.get("takedown_power", 50) + phys.get("explosiveness", 50),
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


def calculate_damage_reduction(defender, fatigue: float, strike_type: str = "punch") -> float:
    """
    Overall damage reduction factor for a defender.
    Uses specific defensive stats based on strike type.
    """
    dur = defender.get_effective_attribute("durability", fatigue)
    comp = defender.get_effective_attribute("composure", fatigue)
    fiq = defender.get_effective_attribute("fight_iq", fatigue)
    blocking = defender.get_effective_attribute("blocking", fatigue)
    gsd = defender.get_effective_attribute("ground_striking_defense", fatigue)

    is_ground = "ground" in strike_type.lower()
    if is_ground:
        return clamp((dur * 0.30 + gsd * 0.25 + blocking * 0.20 + comp * 0.15 + fiq * 0.10) / 200.0, 0.05, 0.85)
    return clamp((dur * 0.30 + blocking * 0.25 + comp * 0.20 + fiq * 0.15) / 200.0, 0.05, 0.85)


def calculate_striking_defense(defender, fatigue: float, target: str) -> float:
    """
    Calculate defense against a strike based on target zone.
    Returns 0-100 defense value.
    """
    head_movement = defender.get_effective_attribute("head_movement", fatigue)
    footwork = defender.get_effective_attribute("footwork_defense", fatigue)
    blocking = defender.get_effective_attribute("blocking", fatigue)
    parrying = defender.get_effective_attribute("parrying", fatigue)
    fiq = defender.get_effective_attribute("fight_iq", fatigue)
    durability = defender.get_effective_attribute("durability", fatigue)
    composure = defender.get_effective_attribute("composure", fatigue)
    athleticism = defender.get_effective_attribute("athleticism", fatigue)

    if target in ("head", "jaw", "temple", "nose", "left_eye", "right_eye"):
        val = (head_movement * 0.30 + blocking * 0.25 + footwork * 0.20 +
               parrying * 0.15 + fiq * 0.10)
    elif target in ("body", "solar_plexus", "liver", "ribs", "chest"):
        val = (blocking * 0.35 + footwork * 0.20 + durability * 0.20 +
               parrying * 0.15 + fiq * 0.10)
    elif target in ("legs", "lead_leg", "rear_leg"):
        val = (footwork * 0.35 + durability * 0.20 + athleticism * 0.20 +
               blocking * 0.25)
    else:
        val = (durability * 0.30 + footwork * 0.25 + blocking * 0.20 +
               composure * 0.15 + fiq * 0.10)
    return clamp(val, 5, 95)


def calculate_critical_multiplier(attacker, defender, fatigue: float) -> float:
    """
    Determine if a critical hit lands and return multiplier.
    Uses striking_accuracy, composure, counter_timing, heart vs defender's
    danger_recognition and head_movement.
    """
    acc = attacker.get_effective_attribute("striking_accuracy", fatigue)
    comp = attacker.get_effective_attribute("composure", fatigue)
    ct = attacker.get_effective_attribute("counter_timing", fatigue)
    heart = attacker.get_effective_attribute("heart", fatigue)
    dr = defender.get_effective_attribute("danger_recognition", fatigue)
    hm = defender.get_effective_attribute("head_movement", fatigue)

    # Base crit chance with more factors
    crit_chance = (acc / 250.0) * (1.0 + comp / 300.0) * (1.0 + ct / 500.0)

    # Heart bonus
    if heart > 70:
        crit_chance *= 1.15

    # Defender danger_recognition reduces crit chance (they sense and cover)
    crit_chance *= (1.0 - dr / 600.0)

    # Defender head_movement reduces crits
    crit_chance *= (1.0 - hm / 500.0)

    if random.random() < min(crit_chance, 0.20):
        return 2.0
    return 1.0


# Strategy effectiveness matrix moved to strategy.py to avoid duplication
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


