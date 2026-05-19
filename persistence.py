import json
import os
import pickle
import random
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional

from fighter import Fighter
from promotion import Promotion

SAVE_FORMAT_VERSION = 1

class SaveIncompatibleError(Exception):
    pass

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None

def _get_db_path() -> str:
    return os.environ.get("MMALIFE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "mma_life.db"))


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        try:
            _conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as e:
            raise RuntimeError(f"Cannot open database: {e}") from e
    return _conn


def init_db():
    with _lock:
        conn = _get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS fighters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                weight_class TEXT NOT NULL,
                height REAL,
                reach REAL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                knockouts INTEGER DEFAULT 0,
                submissions INTEGER DEFAULT 0,
                win_streak INTEGER DEFAULT 0,
                loss_streak INTEGER DEFAULT 0,
                confidence REAL DEFAULT 50,
                rank INTEGER DEFAULT 999,
                peak_rank INTEGER DEFAULT 999,
                base_weight_lbs REAL,
                retired INTEGER DEFAULT 0,
                nationality TEXT,
                home_region TEXT,
                archetype TEXT,
                background TEXT,
                stance TEXT DEFAULT 'orthodox',
                months_inactive INTEGER DEFAULT 0,
                career_damage_taken REAL DEFAULT 0,
                net_worth REAL DEFAULT 0,
                attributes TEXT NOT NULL,
                injuries TEXT DEFAULT '[]',
                contract TEXT,
                promotion_name TEXT,
                trait_id TEXT,
                personality_id TEXT,
                signature_strikes TEXT DEFAULT '{}',
                style_evolution TEXT DEFAULT '{}',
                created_at REAL DEFAULT (julianday('now'))
            );

            CREATE TABLE IF NOT EXISTS promotions (
                name TEXT PRIMARY KEY,
                tier_name TEXT NOT NULL,
                weight_classes TEXT NOT NULL,
                champions TEXT DEFAULT '{}',
                fighter_ids TEXT DEFAULT '[]',
                ranking_data TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS sessions (
                sid TEXT PRIMARY KEY,
                data BLOB,
                created_at REAL DEFAULT (julianday('now')),
                updated_at REAL DEFAULT (julianday('now'))
            );

            CREATE TABLE IF NOT EXISTS fight_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fighter1_id TEXT,
                fighter2_id TEXT,
                fighter1_name TEXT,
                fighter2_name TEXT,
                winner_id TEXT,
                winner_name TEXT,
                method TEXT,
                round_num INTEGER,
                time_seconds INTEGER,
                promotion_name TEXT,
                event_name TEXT,
                is_title INTEGER DEFAULT 0,
                weight_class TEXT,
                fight_date TEXT,
                fighter1_rank INTEGER,
                fighter2_rank INTEGER
            );

            CREATE TABLE IF NOT EXISTS player_saves (
                save_id TEXT PRIMARY KEY,
                slot_index INTEGER NOT NULL,
                display_name TEXT,
                fighter_name TEXT,
                record TEXT,
                promotion_name TEXT,
                game_date TEXT,
                in_fight INTEGER DEFAULT 0,
                save_format_version INTEGER DEFAULT 1,
                player_state BLOB NOT NULL,
                world_snapshot BLOB NOT NULL,
                created_at REAL DEFAULT (julianday('now')),
                updated_at REAL DEFAULT (julianday('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_saves_slot ON player_saves(slot_index);

            CREATE INDEX IF NOT EXISTS idx_fighters_weight_class ON fighters(weight_class);
            CREATE INDEX IF NOT EXISTS idx_fighters_promotion ON fighters(promotion_name);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);
        """)
        conn.commit()


FIGHTER_COLUMNS = [
    "id","name","age","weight_class","height","reach",
    "wins","losses","draws","knockouts","submissions",
    "win_streak","loss_streak","confidence","rank","peak_rank",
    "base_weight_lbs","retired","nationality","home_region",
    "archetype","background","stance","months_inactive",
    "career_damage_taken","net_worth","attributes","injuries",
    "contract","promotion_name","trait_id","personality_id",
    "signature_strikes","style_evolution",
]

def _fighter_to_dict(f: Fighter) -> Dict:
    existing_id = getattr(f, '_db_id', None)
    if existing_id:
        _id = existing_id
    else:
        base_id = f.name.replace(" ", "_").lower()[:50]
        _id = f"{base_id}_{random.randint(10000, 99999)}"
        f._db_id = _id
    return {
        "id": _id,
        "name": f.name,
        "age": f.age,
        "weight_class": f.weight_class,
        "height": getattr(f, 'height', None),
        "reach": getattr(f, 'reach', None),
        "wins": f.wins,
        "losses": f.losses,
        "draws": f.draws,
        "knockouts": f.knockouts,
        "submissions": f.submissions,
        "win_streak": f.win_streak,
        "loss_streak": f.loss_streak,
        "confidence": f.confidence,
        "rank": f.rank,
        "peak_rank": f.peak_rank,
        "base_weight_lbs": getattr(f, 'base_weight_lbs', None),
        "retired": 1 if f.retired else 0,
        "nationality": getattr(f, 'nationality', None),
        "home_region": getattr(f, 'home_region', None),
        "archetype": getattr(f, 'archetype', None),
        "background": getattr(f, 'background', None),
        "stance": getattr(f, 'stance', 'orthodox'),
        "months_inactive": getattr(f, 'months_inactive', 0),
        "career_damage_taken": getattr(f, 'career_damage_taken', 0),
        "net_worth": getattr(f, 'net_worth', 0),
        "attributes": json.dumps(f.attributes),
        "injuries": json.dumps(f.injuries, default=str),
        "contract": None,
        "promotion_name": None,
        "trait_id": getattr(f, 'trait_id', None),
        "personality_id": getattr(f, 'personality_id', None),
        "signature_strikes": json.dumps(getattr(f, 'signature_strikes', {}), default=str),
        "style_evolution": json.dumps(getattr(f, '_style_evolution_tracker', {}), default=str),
    }


def _dict_to_fighter(d: Dict) -> Fighter:
    base_wl = d.get("base_weight_lbs")
    if base_wl is None:
        base_wl = 155
    f = Fighter(
        d["name"], d["age"], base_wl,
        d.get("background") or "",
        d.get("archetype") or "balanced",
        nationality=d.get("nationality"),
        home_region=d.get("home_region"),
        trait_id=d.get("trait_id"),
        personality_id=d.get("personality_id"),
    )
    f._db_id = d["id"]
    if d.get("height") is not None:
        f.height = d["height"]
    if d.get("reach") is not None:
        f.reach = d["reach"]
    f.wins = d["wins"]
    f.losses = d["losses"]
    f.draws = d["draws"]
    f.knockouts = d["knockouts"]
    f.submissions = d["submissions"]
    f.win_streak = d["win_streak"]
    f.loss_streak = d["loss_streak"]
    f.confidence = d["confidence"]
    f.rank = d["rank"]
    f.peak_rank = d["peak_rank"]
    f.retired = bool(d["retired"])
    f.months_inactive = d.get("months_inactive") or 0
    f.career_damage_taken = d.get("career_damage_taken") or 0
    f.net_worth = d.get("net_worth") or 0
    f.stance = d.get("stance") or "orthodox"
    f.attributes = json.loads(d["attributes"])
    f.injuries = json.loads(d.get("injuries") or "[]")
    setattr(f, 'signature_strikes', json.loads(d.get("signature_strikes") or "{}"))
    tracker = json.loads(d.get("style_evolution") or "{}")
    f._style_evolution_tracker = tracker
    return f


def save_fighters(fighters: List[Fighter]):
    with _lock:
        conn = _get_conn()
        rows = []
        for f in fighters:
            d = _fighter_to_dict(f)
            rows.append(tuple(d[k] for k in FIGHTER_COLUMNS))
        placeholders = ",".join(["?" for _ in FIGHTER_COLUMNS])
        cols = ",".join(FIGHTER_COLUMNS)
        conn.executemany(
            f"INSERT OR REPLACE INTO fighters ({cols}) VALUES ({placeholders})",
            rows
        )
        conn.commit()


def load_fighters() -> List[Fighter]:
    with _lock:
        conn = _get_conn()
        cursor = conn.execute("SELECT * FROM fighters")
        columns = [desc[0] for desc in cursor.description]
        fighters = []
        for row in cursor.fetchall():
            d = dict(zip(columns, row))
            fighters.append(_dict_to_fighter(d))
        return fighters


def save_promotions(promotions: List[Promotion]):
    with _lock:
        conn = _get_conn()
        for p in promotions:
            wc_json = json.dumps(p.weight_classes)
            champs = {}
            for wc, champ in p.champions.items():
                if champ:
                    champs[wc] = {"name": champ.name, "db_id": getattr(champ, '_db_id', None)}
                else:
                    champs[wc] = None
            champion_json = json.dumps(champs)
            all_fighters = []
            for wc_fighters in p.rankings.values():
                all_fighters.extend(f.name for f in wc_fighters)
            fighter_ids_json = json.dumps(all_fighters)
            rank_data = {}
            for wc, fighters in p.rankings.items():
                rank_data[wc] = [
                    {"name": f.name, "rank": f.rank, "rating": f.get_overall_rating(),
                     "db_id": getattr(f, '_db_id', None), "age": f.age}
                    for f in fighters
                ]
            ranking_json = json.dumps(rank_data)
            conn.execute(
                "INSERT OR REPLACE INTO promotions VALUES (?,?,?,?,?,?)",
                (p.name, p.tier_name, wc_json, champion_json, fighter_ids_json, ranking_json)
            )
        conn.commit()


def load_promotions(all_fighters: List[Fighter]) -> List[Promotion]:
    import utils
    with _lock:
        conn = _get_conn()
        cursor = conn.execute("SELECT * FROM promotions")
        rows = cursor.fetchall()
        if not rows:
            from promotion import create_promotions
            return create_promotions([wc["name"] for wc in utils.WEIGHT_CLASSES])
        columns = [desc[0] for desc in cursor.description]
        by_id = {getattr(f, '_db_id', None): f for f in all_fighters if getattr(f, '_db_id', None) is not None}
        by_name_age = {(f.name, f.age): f for f in all_fighters}
        tier_map = {t["name"]: t for t in utils.PRO_TIERS}
        promotions = []
        for row in rows:
            d = dict(zip(columns, row))
            wc_list = json.loads(d["weight_classes"])
            tier = tier_map.get(d["tier_name"], utils.PRO_TIERS[-1])
            p = Promotion(d["name"], tier, wc_list)
            champs = json.loads(d["champions"])
            for wc, champ_data in champs.items():
                if not champ_data:
                    continue
                if isinstance(champ_data, dict):
                    champ_db_id = champ_data.get("db_id")
                    f = by_id.get(champ_db_id) if champ_db_id else None
                    if f is None:
                        f = by_name_age.get((champ_data.get("name"), 0))
                    if f is None:
                        champ_name = champ_data.get("name")
                        f = next((ff for ff in all_fighters if ff.name == champ_name), None)
                else:
                    champ_name = champ_data
                    f = next((ff for ff in all_fighters if ff.name == champ_name), None)
                if f:
                    p.champions[wc] = f
            p.rankings = {}
            rank_data = json.loads(d["ranking_data"])
            for wc, fighter_list in rank_data.items():
                p.rankings[wc] = []
                for entry in fighter_list:
                    db_id = entry.get("db_id")
                    f = by_id.get(db_id) if db_id else None
                    if f is None:
                        entry_age = entry.get("age", 0)
                        f = by_name_age.get((entry["name"], entry_age))
                    if f is None:
                        f = next((ff for ff in all_fighters if ff.name == entry["name"]), None)
                    if f:
                        p.rankings[wc].append(f)
            promotions.append(p)
        return promotions


def save_session(sid: str, session_data: Dict):
    with _lock:
        conn = _get_conn()
        blob = pickle.dumps(session_data)
        conn.execute(
            "INSERT OR REPLACE INTO sessions (sid, data, updated_at) VALUES (?,?, julianday('now'))",
            (sid, blob)
        )
        conn.commit()


def load_session(sid: str) -> Optional[Dict]:
    with _lock:
        conn = _get_conn()
        cursor = conn.execute("SELECT data FROM sessions WHERE sid = ?", (sid,))
        row = cursor.fetchone()
        if row:
            return pickle.loads(row[0])
        return None


def delete_session(sid: str):
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM sessions WHERE sid = ?", (sid,))
        conn.commit()


def record_fight_history(fight_data: List[Dict]):
    if not fight_data:
        return
    with _lock:
        conn = _get_conn()
        for fd in fight_data:
            conn.execute("""
                INSERT OR REPLACE INTO fight_history
                (fighter1_id, fighter2_id, fighter1_name, fighter2_name,
                 winner_id, winner_name, method, round_num, time_seconds,
                 promotion_name, event_name, is_title, weight_class,
                 fight_date, fighter1_rank, fighter2_rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fd.get("fighter1_id", ""), fd.get("fighter2_id", ""),
                fd.get("fighter1_name", ""), fd.get("fighter2_name", ""),
                fd.get("winner_id", ""), fd.get("winner_name", ""),
                fd.get("method", ""), fd.get("round", 0), fd.get("time_seconds", 0),
                fd.get("promotion", ""), fd.get("event_name", ""),
                1 if fd.get("is_title_fight") else 0,
                fd.get("weight_class", ""),
                str(fd.get("fight_date", "")),
                fd.get("fighter1_rank", 0), fd.get("fighter2_rank", 0),
            ))
        conn.commit()

def save_world_state(promotions, all_fighters, world_sim=None, world_news=None):
    save_fighters(all_fighters)
    save_promotions(promotions)
    if world_sim:
        with _lock:
            conn = _get_conn()
            sim_data = pickle.dumps(world_sim)
            conn.execute(
                "INSERT OR REPLACE INTO sessions (sid, data, updated_at) VALUES ('__world_sim__', ?, julianday('now'))",
                (sim_data,)
            )
            if world_news:
                news_data = json.dumps(world_news[:200])
                conn.execute(
                    "INSERT OR REPLACE INTO sessions (sid, data, updated_at) VALUES ('__world_news__', ?, julianday('now'))",
                    (news_data.encode(),)
                )
            conn.commit()


def load_world_state():
    with _lock:
        conn = _get_conn()
        cursor = conn.execute("SELECT COUNT(*) FROM fighters")
        count = cursor.fetchone()[0]
        if count == 0:
            return None
        all_fighters = load_fighters()
        promotions = load_promotions(all_fighters)
        sim_cursor = conn.execute("SELECT data FROM sessions WHERE sid = '__world_sim__'")
        sim_row = sim_cursor.fetchone()
        world_sim = pickle.loads(sim_row[0]) if sim_row else None
        news_cursor = conn.execute("SELECT data FROM sessions WHERE sid = '__world_news__'")
        news_row = news_cursor.fetchone()
        world_news = json.loads(news_row[0]) if news_row else []
        return promotions, all_fighters, world_sim, world_news


def cleanup_stale_sessions(max_age_hours: float = 24):
    with _lock:
        conn = _get_conn()
        conn.execute(
            "DELETE FROM sessions WHERE sid NOT LIKE '__%' AND updated_at < julianday('now') - ?",
            (max_age_hours / 24.0,)
        )
        conn.commit()


def save_to_slot(sid: str, slot_index: int, display_name: str,
                 session_data: dict, world_data: tuple) -> str:
    save_id = f"{sid}_slot_{slot_index}"
    f = session_data.get("fighter")
    career = session_data.get("career")
    promo_name = session_data.get("current_promotion_name")
    game_date = session_data.get("game_date")

    fighter_name = f.name if f else "Unknown"
    record = f.get_record_string() if f else "0-0-0"
    promo_name = promo_name or "Free Agent"
    date_str = game_date.strftime("%Y-%m-%d") if game_date else "Unknown"
    in_fight = 1 if (session_data.get("current_fight") or session_data.get("fight_started")) else 0

    player_blob = pickle.dumps({"v": SAVE_FORMAT_VERSION, "data": session_data})
    world_blob = pickle.dumps({"v": SAVE_FORMAT_VERSION, "data": world_data})

    with _lock:
        conn = _get_conn()
        conn.execute("""
            INSERT OR REPLACE INTO player_saves
            (save_id, slot_index, display_name, fighter_name, record, promotion_name,
             game_date, in_fight, save_format_version, player_state, world_snapshot,
             created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?, julianday('now'), julianday('now'))
        """, (save_id, slot_index, display_name, fighter_name, record, promo_name,
              date_str, in_fight, SAVE_FORMAT_VERSION, player_blob, world_blob))
        conn.commit()
    return save_id


def load_from_slot(sid: str, slot_index: int):
    save_id = f"{sid}_slot_{slot_index}"
    with _lock:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT player_state, world_snapshot, save_format_version FROM player_saves WHERE save_id = ?",
            (save_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        player_blob, world_blob, version = row
        if version != SAVE_FORMAT_VERSION:
            raise SaveIncompatibleError(
                f"Save format v{version} incompatible with current v{SAVE_FORMAT_VERSION}"
            )
        player_data = pickle.loads(player_blob)
        world_data = pickle.loads(world_blob)
        return player_data["data"], world_data["data"]


def list_saves(sid: str):
    with _lock:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT slot_index, display_name, fighter_name, record, promotion_name,"
            " game_date, in_fight, updated_at FROM player_saves"
            " WHERE save_id LIKE ? ORDER BY slot_index",
            (f"{sid}_slot_%",)
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def delete_save(sid: str, slot_index: int):
    save_id = f"{sid}_slot_{slot_index}"
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM player_saves WHERE save_id = ?", (save_id,))
        conn.commit()


def export_save(sid: str, slot_index: int):
    import base64
    result = load_from_slot(sid, slot_index)
    if not result:
        return None
    session_data, world_data = result
    player_b64 = base64.b64encode(pickle.dumps(session_data)).decode()
    world_b64 = base64.b64encode(pickle.dumps(world_data)).decode()
    f = session_data.get("fighter")
    return {
        "format_version": SAVE_FORMAT_VERSION,
        "exported_at": datetime.now().isoformat(),
        "fighter_name": f.name if f else "Unknown",
        "player_data_b64": player_b64,
        "world_data_b64": world_b64,
    }


def import_save(sid: str, slot_index: int, data: dict):
    import base64
    if data.get("format_version", 0) != SAVE_FORMAT_VERSION:
        raise SaveIncompatibleError(
            f"Export format v{data.get('format_version')} incompatible with current v{SAVE_FORMAT_VERSION}"
        )
    player_bytes = base64.b64decode(data["player_data_b64"])
    world_bytes = base64.b64decode(data["world_data_b64"])
    session_data = pickle.loads(player_bytes)
    world_data = pickle.loads(world_bytes)
    display_name = data.get("fighter_name", "Imported")
    save_to_slot(sid, slot_index, display_name, session_data, world_data)
