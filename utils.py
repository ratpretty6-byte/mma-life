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

def weight_cut_penalty(weight_to_cut_lbs: float) -> Dict[str, float]:
    if weight_to_cut_lbs <= 0:
        return {"cardio_penalty": 0.0, "durability_penalty": 0.0}
    excess_cut = max(0, weight_to_cut_lbs - 5)
    cardio_penalty = min(0.2, excess_cut * 0.05)
    durability_penalty = min(0.15, excess_cut * 0.0375)
    return {"cardio_penalty": cardio_penalty, "durability_penalty": durability_penalty}

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
