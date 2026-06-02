#!/usr/bin/env python3
import json
import os
import random
import secrets
import time
import traceback
import urllib.parse
from collections import deque
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from threading import Event, Lock, Thread

from diskcache import Cache

APP_DIR = os.path.dirname(os.path.abspath(__file__))

import utils
from career import CareerSystem
from events import EventSystem
from fight import Fight
from fighter import Fighter
from finance import FinancialSystem
from generator import generate_fighter_pool
from health import HealthSystem
from media import MediaSystem
from news import format_news_items
from persistence import (
    SaveIncompatibleError,
    cleanup_stale_sessions,
    delete_save,
    export_save,
    import_save,
    init_db,
    list_saves,
    load_from_slot,
    load_session,
    load_world_state,
    save_session,
    save_to_slot,
    save_world_state,
)
from promotion import create_promotions
from strategy import STRATEGIES
from training import DAYS_OF_WEEK, TrainingSystem
from world_sim import WorldSimulator

init_lock = Lock()
gs = {"initialized": False}
_gs_lock = Lock()

_session_cache = Cache(os.path.join(APP_DIR, ".session_cache"), size_limit=2**30, cull_limit=0)
_session_cache.clear()  # Clear stale session cache on startup; world state persists via SQLite
_fight_streams = {}
_fight_streams_lock = Lock()

def _gs_set(key, value):
    with _gs_lock:
        gs[key] = value

def _gs_get(key, default=None):
    with _gs_lock:
        return gs.get(key, default)

def ensure_initialized():
    if _gs_get("initialized"):
        return
    with init_lock:
        if _gs_get("initialized"):
            return
        try:
            init_db()
            existing = load_world_state()
            if existing:
                promotions, all_fighters, world_sim, world_news = existing
                print(f"Loaded existing world: {len(all_fighters)} fighters, {len(promotions)} promotions")
            else:
                print("Generating new game world...")
                weight_classes = [wc["name"] for wc in utils.WEIGHT_CLASSES]
                promotions = create_promotions(weight_classes)
                all_fighters = generate_fighter_pool(promotions, 8000)
                world_news = []
                save_world_state(promotions, all_fighters)
                world_sim = WorldSimulator(promotions, all_fighters)
            with _gs_lock:
                gs["promotions"] = promotions
                gs["all_fighters"] = all_fighters
                gs["world_sim"] = world_sim or WorldSimulator(promotions, gs.get("all_fighters"))
                gs["world_news"] = world_news or []
                gs["initialized"] = True
            print("Game world ready!")
        except Exception as e:
            print(f"INIT FAILED: {e}")
            import traceback
            traceback.print_exc()
            raise

def get_promotions_by_tier(tier_name=None):
    promos = _gs_get("promotions") or []
    if tier_name:
        return [p for p in promos if p.tier_name == tier_name]
    return promos


def get_promotion_by_name(name):
    if not name:
        return None
    for p in get_promotions_by_tier():
        if p.name == name:
            return p
    return None


def get_session_promotion(session):
    name = session.get("current_promotion_name")
    if name:
        return get_promotion_by_name(name)
    return None


def set_session_promotion(session, promo):
    session["current_promotion_name"] = promo.name if promo else None


def get_or_create_session(session_id):
    if session_id not in _session_cache:
        session = load_session(session_id) or {"_created": time.time()}
        _session_cache[session_id] = session
        _session_cache.expire(session_id, timedelta(hours=48))
        if session.get("fighter") and _gs_get("initialized"):
            _relink_session_fighter(session)
    return _session_cache[session_id]


def _relink_session_fighter(session):
    loaded_f = session.get("fighter")
    if not loaded_f:
        return
    promotions = _gs_get("promotions", [])
    all_fighters = _gs_get("all_fighters", [])
    db_id = getattr(loaded_f, '_db_id', None)
    found = None
    for af in all_fighters:
        af_id = getattr(af, '_db_id', None)
        if db_id and af_id and af_id == db_id:
            found = af
            break
    if not found:
        for af in all_fighters:
            if af.name == loaded_f.name and af.age == loaded_f.age:
                found = af
                break
    if not found:
        for promo in promotions:
            for fighters in promo.rankings.values():
                for pf in fighters:
                    if pf.name == loaded_f.name and pf.age == loaded_f.age:
                        found = pf
                        break
                if found:
                    break
            if found:
                break
    if not found:
        promo_name = session.get("current_promotion_name")
        if promo_name:
            for promo in promotions:
                if promo.name == promo_name:
                    wc = loaded_f.weight_class
                    if wc not in promo.rankings:
                        promo.rankings[wc] = []
                    loaded_f.rank = len(promo.rankings[wc]) + 1
                    promo.rankings[wc].append(loaded_f)
                    promo.fighters.append(loaded_f)
                    promo.update_rankings()
                    if all_fighters is not None and loaded_f not in all_fighters:
                        all_fighters.append(loaded_f)
                    found = loaded_f
                    break
    if found:
        session["fighter"] = found
        for key in ["career", "training", "finance", "health", "media"]:
            obj = session.get(key)
            if obj:
                obj.fighter = found

_world_sim_running = False
_world_sim_lock = Lock()

def run_world_sim(game_date, es):
    global _world_sim_running
    if not _gs_get("initialized"):
        return
    with _world_sim_lock:
        if _world_sim_running:
            return
        _world_sim_running = True
    try:
        ws = _gs_get("world_sim")
        if ws and game_date:
            results = ws.simulate_month(game_date, es)
            if results:
                news_list = _gs_get("world_news") or []
                news_list.extend(results)
                if len(news_list) > 200:
                    news_list[:] = news_list[-200:]
                with _gs_lock:
                    gs["world_news"] = news_list
    except Exception as e:
        print(f"World sim error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _persist_world()
        with _world_sim_lock:
            _world_sim_running = False

def run_world_sim_async(game_date, es):
    Thread(target=run_world_sim, args=(game_date, es), daemon=True).start()

def _session_cleanup_loop():
    while True:
        time.sleep(3600)
        try:
            cleanup_stale_sessions(48)
            _session_cache.cull()
        except Exception as e:
            print(f"Session cleanup error: {e}")

Thread(target=_session_cleanup_loop, daemon=True).start()

def _persist_session(sid, session):
    try:
        save_session(sid, session)
        if sid in _session_cache:
            _session_cache[sid] = session
            _session_cache.expire(sid, timedelta(hours=48))
    except Exception as e:
        print(f"Failed to save session {sid}: {e}")

def _persist_world():
    try:
        promotions = _gs_get("promotions")
        fighters = _gs_get("all_fighters")
        if promotions is None or fighters is None:
            return
        save_world_state(promotions, fighters, _gs_get("world_sim"), _gs_get("world_news"))
    except Exception as e:
        print(f"Failed to save world state: {e}")

def _auto_save(sid, session):
    """Auto-save to slot 0 on key game events."""
    if not _gs_get("initialized"):
        return
    try:
        if not session or not session.get("fighter"):
            return
        if session.get("current_fight") or session.get("fight_started"):
            return
        promotions_tuple = tuple(get_promotions_by_tier())
        world_data = (
            promotions_tuple,
            _gs_get("all_fighters", []),
            _gs_get("world_sim"),
            _gs_get("world_news", []),
        )
        f = session.get("fighter")
        name = f"{f.name} (Auto)"

        # Only auto-save to slot 0 if it doesn't exist or game_date moved forward
        existing = list_saves(sid)
        slot_0 = [s for s in existing if s["slot_index"] == 0]
        if slot_0:
            old_date = slot_0[0].get("game_date", "")
            new_date = session.get("game_date")
            if new_date:
                new_date_str = new_date.strftime("%Y-%m-%d")
                if new_date_str == old_date:
                    # Try to avoid duplicate saves on same day
                    # Still save on fight completion and promotion change always
                    return
        save_to_slot(sid, 0, name, session, world_data)
    except Exception as e:
        print(f"Auto-save failed: {e}")

def ensure_regional_opponents(session):
    f = session.get("fighter")
    promo = get_session_promotion(session)
    if not f or not promo or promo.tier_name != "Regional":
        return
    wc = f.weight_class
    available = [opp for opp in promo.rankings.get(wc, [])
                 if opp != f and opp.is_available()]
    if len(available) >= 5:
        return
    to_create = 8 - len(available)
    from generator import generate_single_fighter
    wc_data = next((wc_item for wc_item in utils.WEIGHT_CLASSES if wc_item["name"] == wc), None)
    if not wc_data:
        return
    for i in range(to_create):
        fighter = generate_single_fighter(
            random.randint(wc_data["min"], wc_data["max"]),
            skill_mean=utils.gaussian_random(40, 8, 25, 55),
            skill_std=utils.gaussian_random(12, 3, 6, 18)
        )
        fighter.nationality = f.nationality
        fighter.home_region = f.home_region
        promo._add_fighter_batch(fighter)
        all_fighters = gs.get("all_fighters")
        if all_fighters is not None:
            all_fighters.append(fighter)
    promo.update_rankings()

def ensure_available_opponents(session):
    """Replenish opponent pool for the player's current promotion tier."""
    f = session.get("fighter")
    promo = get_session_promotion(session)
    if not f or not promo:
        return
    wc = f.weight_class

    if promo.tier_name == "Regional":
        ensure_regional_opponents(session)
        return

    available = [opp for opp in promo.rankings.get(wc, [])
                 if opp != f and opp.is_available()]
    if len(available) >= 3:
        return

    from generator import generate_single_fighter
    wc_data = next((wc_item for wc_item in utils.WEIGHT_CLASSES if wc_item["name"] == wc), None)
    if not wc_data:
        return

    to_create = 6 - len(available)
    for i in range(to_create):
        fighter = generate_single_fighter(
            random.randint(wc_data["min"], wc_data["max"]),
            skill_mean=utils.gaussian_random(50, 10, 30, 70),
            skill_std=utils.gaussian_random(12, 3, 6, 18)
        )
        fighter.nationality = f.nationality
        fighter.home_region = f.home_region
        promo._add_fighter_batch(fighter)
        all_fighters = gs.get("all_fighters")
        if all_fighters is not None:
            all_fighters.append(fighter)
    promo.update_rankings()


def seed_regional_division(nationality: str, home_region: str, weight_class: str, count: int = 8):
    """Pre-seed the regional promotion with fighters matching a nationality."""
    from generator import generate_single_fighter
    regionals = get_promotions_by_tier("Regional")
    regional_promo = regionals[0] if regionals else None
    if not regional_promo:
        return
    existing = [f for f in regional_promo.rankings.get(weight_class, [])
                if f.nationality == nationality and f.is_available()]
    to_create = max(0, count - len(existing))
    if to_create <= 0:
        return
    wc_data = None
    for wc in utils.WEIGHT_CLASSES:
        if wc["name"] == weight_class:
            wc_data = wc
            break
    if not wc_data:
        return
    for _ in range(to_create):
        fighter = generate_single_fighter(
            random.randint(wc_data["min"], wc_data["max"]),
            skill_mean=utils.gaussian_random(40, 8, 25, 55),
            skill_std=utils.gaussian_random(12, 3, 6, 18)
        )
        fighter.nationality = nationality
        fighter.home_region = home_region
        regional_promo._add_fighter_batch(fighter)
    regional_promo.update_rankings()

def get_state_dict(session):
    f = session.get("fighter")
    if not f:
        return {
            "fighter": None,
            "strategies": [{"id": s["id"], "name": s["name"], "description": s["description"]} for s in STRATEGIES],
            "traits": utils.TRAITS,
            "personalities": utils.PERSONALITIES,
            "nationalities": utils.NATIONALITIES,
            "regions": utils.REGIONS,
        }
    promo = get_session_promotion(session)
    game_date = session.get("game_date", datetime.now())
    return {
        "free_agent": promo is None,
        "fighter": {
            "name": f.name,
            "age": f.age,
            "weight_class": f.weight_class,
            "weight": f.current_weight_lbs,
            "height": f.height,
            "reach": f.reach,
            "nationality": f.nationality,
            "home_region": f.home_region,
            "archetype": f.archetype,
            "background": f.background,
            "trait_id": f.trait_id,
            "personality_id": f.personality_id,
            "wins": f.wins,
            "losses": f.losses,
            "draws": f.draws,
            "rank": f.rank,
            "peak_rank": f.peak_rank,
            "record": f.get_record_string(),
            "rating": round(f.get_overall_rating(), 1),
            "win_streak": f.win_streak,
            "loss_streak": f.loss_streak,
            "confidence": round(f.confidence),
            "knockouts": f.knockouts,
            "submissions": f.submissions,
            "net_worth": session.get("finance", {}).net_worth if session.get("finance") else f.net_worth,
            "attributes": {k: round(v, 1) for k, v in f.attributes.items()},
            "physical_attrs": Fighter.PHYSICAL_ATTRS,
            "mental_attrs": Fighter.MENTAL_ATTRS,
            "stat_groups": {
                "offense": ["striking_power", "striking_accuracy", "hand_speed",
                            "kick_power", "kick_accuracy", "kick_speed",
                            "takedown_power", "takedown_accuracy", "submission_offense",
                            "clinch_strikes", "clinch_throws"],
                "defense": ["wrestling_defense", "head_movement", "footwork_defense",
                            "blocking", "parrying", "counter_timing",
                            "sprawl_technique", "guard_retention", "scrambling",
                            "ground_striking_defense", "submission_awareness",
                            "submission_defense", "clinch_escapes"],
                "physical": ["cardio", "durability", "athleticism",
                             "explosiveness", "flexibility",
                             "top_control", "bottom_control", "clinch_control"],
                "mental": Fighter.MENTAL_ATTRS,
            },
            "stat_key": ["striking_power", "striking_accuracy", "hand_speed",
                         "cardio", "durability", "wrestling_defense",
                         "submission_defense", "head_movement",
                         "fight_iq", "mental_toughness", "heart", "composure"],
            "injuries": [{"type": i["type"], "severity": round(i["severity"], 2)} for i in f.injuries],
            "suspension": max(0, (f.medical_suspension_end - game_date).days) if f.medical_suspension_end else 0,
            "retired": f.retired,
            "stance": f.stance,
            "signature_strike": f.get_signature_strike(),
            "career_damage": round(f.career_damage_taken, 1),
            "career_fights": f.career_total_fights,
            "ko_losses": f.career_ko_losses,
            "prime_status": "prime" if f.PRIME_START <= f.age <= f.PRIME_END else ("developing" if f.age < f.PRIME_START else "declining"),
            "scouting_level": getattr(f, 'times_scouted', 0),
            "signature_strikes": f.signature_strikes,
            "popularity": round(getattr(f, "popularity", 10), 1),
        },
        "promotion": {
            "name": promo.name if promo else "Free Agent",
            "tier": promo.tier_name if promo else "None",
            "rankings": [{"name": o.name, "rank": r+1, "record": o.get_record_string(), "rating": round(o.get_overall_rating(), 1)}
                         for r, o in enumerate((promo.rankings.get(f.weight_class) or [])[:15])] if promo else [],
            "champion": (promo.champions.get(f.weight_class).name if promo.champions.get(f.weight_class) else "N/A") if promo else "N/A",
            "undisputed": promo.is_undisputed_champion(f, get_promotions_by_tier()) if promo else False,
            "personality": promo.personality.get("description", "") if promo and hasattr(promo, "personality") else "",
            "mandatory": promo._mandatory_challenges.get(f.weight_class).name if promo and promo._mandatory_challenges.get(f.weight_class) else None,
        } if promo else None,
        "contract": _get_contract_state(session),
        "training": _get_training_state(session),
        "gym_atmosphere": _get_gym_atmosphere(session),
        "finance": _get_finance_state(session),
        "health": _get_health_state(session),
        "media": _get_media_state(session),
        "career": _get_career_state(session, game_date),
        "has_fight": session.get("current_fight_booking") is not None,
        "game_date": game_date.strftime("%Y-%m-%d") if game_date else None,
        "fight_booking": _get_fight_booking_state(session),
        "fight_state": _get_fight_state(session),
        "strategies": [{"id": s["id"], "name": s["name"], "description": s["description"]} for s in STRATEGIES],
        "traits": utils.TRAITS,
        "personalities": utils.PERSONALITIES,
        "nationalities": utils.NATIONALITIES,
        "regions": utils.REGIONS,
    }

def _get_contract_state(session):
    c = session.get("career")
    if not c or not c.contract:
        return None
    return {
        "base_pay": c.contract.base_pay,
        "win_bonus": c.contract.win_bonus,
        "perf_bonus": c.contract.performance_bonus,
        "fights_remaining": c.contract.fights_remaining,
        "is_champion": c.contract.champion if hasattr(c.contract, 'champion') else False,
    }

FIGHT_WEEK_EVENTS = {
    5: "press_conference",
    4: "open_workout",
    3: "weigh_in",
    2: "faceoff",
    1: "rest_day",
}

def _trigger_fight_week_event(session, days_until):
    f = session.get("fighter")
    media = session.get("media")
    fb = session.get("current_fight_booking")
    event_name = FIGHT_WEEK_EVENTS.get(days_until, "rest")
    if not f or not fb:
        return {"event": "rest", "text": "Rest day."}
    opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1

    if event_name == "press_conference":
        if media:
            result = media.do_press_conference(opponent)
        else:
            result = {"text": f"Press conference: {f.name} and {opponent.name} face the media.", "popularity_gain": 1.0}
        result["event"] = "press_conference"

    elif event_name == "open_workout":
        if media:
            result = media.do_open_workout()
        else:
            result = {"text": f"Open workouts: {f.name} drills for the media.", "popularity_gain": 0.5}
        result["event"] = "open_workout"

    elif event_name == "weigh_in":
        result = {
            "event": "weigh_in",
            "text": f"Weigh-in day! {f.name} needs to make weight.",
            "needs_action": True,
        }

    elif event_name == "faceoff":
        charisma = f.attributes.get("charisma", 50)
        oppose_composure = opponent.attributes.get("composure", 50)
        score = charisma - oppose_composure + random.uniform(-10, 10)
        if score > 5:
            text = f"{f.name} wins the staredown! {opponent.name} looks rattled."
            f.attributes["composure"] = min(100, f.attributes.get("composure", 50) + 3)
        elif score < -5:
            text = f"{opponent.name} gets into {f.name}'s head during the faceoff."
            f.attributes["composure"] = max(0, f.attributes.get("composure", 50) - 3)
        else:
            text = "Both fighters hold their ground during the faceoff."
        result = {"event": "faceoff", "text": text}

    elif event_name == "rest_day":
        f.months_inactive = max(0, f.months_inactive - 1)
        text = f"Rest day. {f.name} conserves energy for tomorrow."
        result = {"event": "rest_day", "text": text}

    else:
        result = {"event": "rest", "text": "A quiet day."}

    if fb and hasattr(fb, 'advance_phase'):
        fb.advance_phase()
    return result

def _get_fight_booking_state(session):
    fb = session.get("current_fight_booking")
    if not fb:
        return None
    f = session.get("fighter")
    if not f:
        return None
    opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
    if not opponent:
        return None
    game_date = session.get("game_date", datetime.now())
    days_until = max(0, (fb.date - game_date).days) if fb.date else 0
    fight_week_day = None
    if 0 <= days_until <= 5:
        fight_week_events = ["Press Conference", "Open Workout", "Weigh-In", "Faceoff", "Rest Day", "Fight Night"]
        fight_week_day = fight_week_events[5 - days_until] if 0 <= days_until <= 5 else None
    return {
        "opponent": {
            "name": opponent.name,
            "record": opponent.get_record_string(),
            "rank": opponent.rank,
            "archetype": opponent.archetype,
            "background": opponent.background,
            "stance": opponent.stance,
            "nationality": opponent.nationality,
            "age": opponent.age,
            "height": opponent.height,
            "reach": opponent.reach,
            "rating": round(opponent.get_overall_rating(), 1),
            "win_streak": opponent.win_streak,
            "loss_streak": opponent.loss_streak,
            "knockouts": opponent.knockouts,
            "submissions": opponent.submissions,
            "attributes": {k: round(v, 1) for k, v in opponent.attributes.items()},
        },
        "is_title": fb.is_title_fight,
        "days_until": days_until,
        "fight_week_day": fight_week_day,
        "fight_week_progress": session.get("fight_week_progress", {}),
    }

def _get_fight_state(session):
    """Return current fight state if a fight is active."""
    fight = session.get("current_fight")
    if not fight:
        return None
    return {
        "status": "active",
        "round": fight.current_round,
        "total_rounds": fight.rounds,
        "winner": fight.winner.name if fight.winner else None,
        "win_method": fight.win_method,
        "win_round": fight.win_round,
        "f1_name": fight.fighter1.name,
        "f2_name": fight.fighter2.name,
        "f1_health": fight._get_display_health(fight.fighter1),
        "f2_health": fight._get_display_health(fight.fighter2),
        "f1_total_score": fight._get_total_score_for(1),
        "f2_total_score": fight._get_total_score_for(2),
        "f1_state": fight.f1_machine.get_state(),
        "f2_state": fight.f2_machine.get_state(),
        "scores": [[j.scores[r][0] for j in fight.judges] for r in range(len(fight.judges[0].scores))] if fight.judges[0].scores else [],
        "fight_log_length": len(fight.fight_log),
        "f1_momentum": fight.f1_momentum,
        "f2_momentum": fight.f2_momentum,
        "crowd_excitement": fight.crowd_excitement,
        "referee_style": getattr(fight, 'referee_style', 'protective'),
    }

def _get_training_state(session):
    t = session.get("training")
    if not t:
        return None
    from training import DRILL_CATEGORIES, DRILLS as ALL_DRILLS
    available_drills = []
    for d in ALL_DRILLS:
        gym_bonus = t.get_gym_bonus_for_drill(d.name)
        available_drills.append({
            "name": d.name, "duration": d.duration_days, "type": d.drill_type,
            "attrs": d.affected_attrs, "gym_bonus": round(gym_bonus * 100),
        })
    return {
        "in_training": t.in_training,
        "drill_name": t.current_drill.name if t.current_drill else None,
        "intensity": t.intensity,
        "days_trained": t.days_trained,
        "fatigue": round(t.fatigue * 100),
        "schedule": t.get_schedule_state(),
        "available_drills": available_drills,
        "drill_categories": {k: v for k, v in DRILL_CATEGORIES.items()},
        "film_study_available": t.film_study_sessions < 2,
        "recovery_active": t.recovery_active,
        "recovery_type": t.recovery_type,
        "weigh_in_pass": t.fighter.weigh_in_pass if hasattr(t.fighter, 'weigh_in_pass') else True,
        "weight_cut_lbs": getattr(t.fighter, 'weight_cut_lbs', 0),
        "hydration_level": getattr(t.fighter, 'hydration_level', 80),
    }

def _get_gym_atmosphere(session):
    f = session.get("fighter")
    if not f or not f.gym:
        return None
    gym_name = f.gym
    gym_fighters = []
    for prom in get_promotions_by_tier():
        if prom:
            for fighter in prom.fighters:
                if fighter.gym == gym_name and fighter.name != f.name and not fighter.retired:
                    gym_fighters.append({
                        "name": fighter.name,
                        "record": fighter.get_record_string(),
                        "rank": fighter.rank if fighter.rank != 1000 else "NR",
                        "rating": round(fighter.get_overall_rating(), 1),
                        "weight_class": fighter.weight_class,
                    })
    gym_fighters.sort(key=lambda x: x["rating"], reverse=True)
    return {"gym": gym_name, "fighters": gym_fighters[:20], "count": len(gym_fighters)}

def _get_finance_state(session):
    f = session.get("finance")
    if not f:
        return None
    # Read gym from session fighter directly to avoid pickle reference breakage
    session_fighter = session.get("fighter")
    gym_name = session_fighter.gym if session_fighter else None
    gym_fee = 0
    if gym_name:
        for g in utils.GYMS:
            if g["name"] == gym_name:
                gym_fee = g["monthly_fee"]
                break
    return {
        "net_worth": f.net_worth,
        "agent": f.fighter.agent or "None",
        "agent_name": f.fighter.agent_name or "None",
        "gym": gym_name or "None",
        "gym_fee": gym_fee,
        "sponsorship": f.sponsorship_deal["monthly_income"] if f.sponsorship_deal else 0,
        "broke_months": f.consecutive_broke_months,
    }

def _get_health_state(session):
    f = session.get("fighter")
    if not f:
        return None
    return {
        "ring_rust": round(f.get_ring_rust_penalty() * 100),
        "career_damage": round(f.career_damage_taken, 1),
        "career_fights": f.career_total_fights,
        "ko_losses": f.career_ko_losses,
        "age_mod": round(f.get_prime_age_modifier(), 3),
    }

def _get_media_state(session):
    m = session.get("media")
    if not m:
        return None
    return {
        "popularity": round(m.popularity),
        "image": m.public_image,
        "followers": m.social_followers,
        "engagement": round(m.fan_engagement * 100),
    }

def _get_career_state(session, game_date=None):
    c = session.get("career")
    if not c:
        return None
    offer = None
    if hasattr(c, 'check_promotion_offer'):
        promotions = get_promotions_by_tier()
        offer = c.check_promotion_offer(promotions)
        if offer:
            offer = {"name": offer.name, "tier": offer.tier_name}
    return {
        "title_defenses": c.title_defenses,
        "earnings": c.career_earnings,
        "rivalries": len(c.rivalries),
        "retired": c.fighter.retired if c.fighter else False,
        "promotion_offer": offer,
        "awards": getattr(c, '_awards', {}),
        "season_months": getattr(c, 'season_months', 0),
        "yearly_wins": getattr(c, '_yearly_wins', 0),
        "yearly_kos": getattr(c, '_yearly_kos', 0),
        "yearly_subs": getattr(c, '_yearly_subs', 0),
    }



# ============================================================
# FIGHT STREAMING — background thread with event polling
# ============================================================

class FightStream:
    """Runs a fight in a background thread, buffering events for polling."""

    def __init__(self, sid, fight, strategy, opponent_name):
        self.sid = sid
        self.fight = fight
        self.initial_strategy = strategy
        self.opponent_name = opponent_name
        self.events = deque()
        self.done = False
        self.result = None
        self.pause_event = Event()
        self.waiting_for_input = False
        self._thread = None

    def start(self):
        print(f"[FightStream] Starting for {self.sid}", flush=True)
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        try:
            self.fight.strategy1.set_pre_fight_strategy(self.initial_strategy)
            ai_map = {
                "brawler": "aggressive_striking", "counter_striker": "defensive_striking",
                "wrestler": "wrestling_focus", "submission_artist": "submission_hunting",
                "kickboxer": "kickboxing_focus", "boxer": "boxing_focus",
                "muay_thai": "muay_thai_focus", "clinch_fighter": "clinch_dominance",
            }
            ai_s = ai_map.get(self.fight.fighter2.archetype, "balanced")
            if ai_s == "balanced":
                import random as rmod

                from strategy import STRATEGIES as STRS
                ai_s = rmod.choice([s["id"] for s in STRS])
            self.fight.strategy2.set_pre_fight_strategy(ai_s)
            gen = self.fight.simulate_fight_gen()
            for event in gen:
                if event.get("type") == "strategy_prompt":
                    self.events.append(event)
                    self.waiting_for_input = True
                    self.pause_event.clear()
                    self.pause_event.wait()
                    self.waiting_for_input = False
                elif event.get("type") == "complete":
                    self.events.append(event)
                    self.result = event
                else:
                    self.events.append(event)
            self.done = True
        except Exception as e:
            import traceback as tbmod
            tbmod.print_exc()
            self.events.append({"type": "error", "text": f"Fight error: {e}"})
            self.done = True

    def submit_strategy(self, strategy):
        if strategy is not None:
            from strategy import find_strategy_by_id
            strat = find_strategy_by_id(strategy)
            if strat:
                self.fight.strategy1.set_mid_fight_strategy(strat)
        self.pause_event.set()

    def get_new_events(self, from_index=0):
        events_list = list(self.events)
        return events_list[from_index:]

    @property
    def event_count(self):
        return len(self.events)


def get_fight_stream(sid):
    with _fight_streams_lock:
        return _fight_streams.get(sid)


def set_fight_stream(sid, fs):
    with _fight_streams_lock:
        _fight_streams[sid] = fs


def clear_fight_stream(sid):
    with _fight_streams_lock:
        _fight_streams.pop(sid, None)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)

            if path in ["/", "/index.html"]:
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(os.path.join(APP_DIR, "templates", "index.html"), "rb") as f:
                    self.wfile.write(f.read())

            elif path == "/debug.html":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(os.path.join(APP_DIR, "templates", "debug.html"), "rb") as f:
                    self.wfile.write(f.read())

            elif path == "/balance.html":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(os.path.join(APP_DIR, "templates", "balance.html"), "rb") as f:
                    self.wfile.write(f.read())

            elif path == "/api/state":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                self.json_resp(get_state_dict(session))

            elif path == "/api/init":
                initialized = gs.get("initialized", False)
                if not initialized:
                    Thread(target=ensure_initialized, daemon=True).start()
                self.json_resp({"ready": True, "initialized": initialized})

            elif path == "/api/has_save":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                if not sid:
                    self.json_resp({"has_save": False, "saves": []})
                    return
                saves = list_saves(sid)
                self.json_resp({
                    "has_save": len(saves) > 0,
                    "saves": saves,
                    "latest_slot": max(s["slot_index"] for s in saves) if saves else None,
                })

            elif path == "/api/list_saves":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                if not sid:
                    self.json_resp({"saves": []})
                    return
                saves = list_saves(sid)
                self.json_resp({"saves": saves})

            elif path == "/create":
                ensure_initialized()
                import html
                raw_name = params.get("name", [""])[0]
                if not raw_name or raw_name.strip() == "":
                    first, last = utils.generate_name()
                    name = f"{first} {last}"
                else:
                    name = html.escape(raw_name.strip()[:64])
                try:
                    age = int(params.get("age", ["25"])[0])
                except (ValueError, TypeError, IndexError):
                    age = 25
                try:
                    wc = int(params.get("weight_class", ["3"])[0])
                except (ValueError, TypeError, IndexError):
                    wc = 3
                bg = params.get("background", ["mma"])[0]
                nationality = params.get("nationality", ["American"])[0]
                region = params.get("region", ["California"])[0]
                trait_id = params.get("trait_id", [None])[0]
                if trait_id in (None, 'None', ''):
                    trait_id = None
                personality_id = params.get("personality_id", ["humble"])[0]

                wc_data = utils.WEIGHT_CLASSES[wc]
                weight = random.randint(wc_data["min"], wc_data["max"])

                game_date = datetime(2025, 1, 6)
                stance = utils.get_stance_for_background(bg)
                f = Fighter(name, age, weight, bg, "balanced", nationality, region, trait_id, personality_id, stance=stance, game_date=game_date)
                f.is_player = True
                regionals = get_promotions_by_tier("Regional")
                regional = regionals[0] if regionals else None
                career = CareerSystem(f)
                if regional:
                    career.sign_with_promotion(regional, 4, game_date)
                training = TrainingSystem(f)
                finance = FinancialSystem(f)
                health = HealthSystem(f)
                media = MediaSystem(f)
                event_sys = EventSystem()
                f.gym = None
                f.net_worth = 5000
                finance.net_worth = 5000
                sid = "sess_" + str(random.randint(10000, 99999))
                session = get_or_create_session(sid)
                session["fighter"] = f
                session["career"] = career
                session["training"] = training
                session["finance"] = finance
                session["health"] = health
                session["media"] = media
                session["event_sys"] = event_sys
                set_session_promotion(session, regional)
                session["current_event"] = None
                session["current_fight_booking"] = None
                session["current_fight"] = None
                session["game_date"] = game_date

                self.send_response(302)
                self.send_header("Location", f"/?sid={sid}")
                self.end_headers()

            elif path == "/api/camps":
                self.json_resp({"camps": get_available_camps_data()})

            elif path == "/api/fight_offers":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                f = session.get("fighter")
                promo = get_session_promotion(session)
                if not f or not promo:
                    self.json_resp({"offers": []})
                    return
                ensure_available_opponents(session)
                offers = promo.generate_fight_offers(f, count=3)
                offers_data = []
                for o in offers:
                    opp = o["opponent"]
                    offers_data.append({
                        "opponent": {
                            "name": opp.name, "record": opp.get_record_string(),
                            "rank": opp.rank, "rating": round(opp.get_overall_rating(), 1),
                            "height": opp.height, "reach": opp.reach,
                            "age": opp.age, "nationality": opp.nationality,
                            "archetype": opp.archetype, "weight_class": opp.weight_class,
                            "background": opp.background,
                            "win_streak": opp.win_streak, "loss_streak": opp.loss_streak,
                            "knockouts": opp.knockouts, "submissions": opp.submissions,
                            "attributes": {k: round(v, 1) for k, v in opp.attributes.items()},
                        },
                        "risk": o["risk"],
                        "purse_bonus": o["purse_bonus"],
                        "popularity_gain": o["popularity_gain"],
                        "card_position": o["card_position"],
                        "base_purse": o["base_purse"],
                        "win_bonus": o["win_bonus"],
                    })
                rel = promo.check_contract_relationship(f)
                self.json_resp({"offers": offers_data, "relationship": rel})

            elif path == "/api/fight_offer":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                f = session.get("fighter")
                career = session.get("career")
                promo = get_session_promotion(session)
                opp_name = params.get("opponent", [""])[0]
                if not f or not promo:
                    self.json_resp({"success": False, "error": "Not signed"})
                    return
                offers = promo.generate_fight_offers(f, count=3)
                target = None
                offer_data = None
                for o in offers:
                    if o["opponent"].name == opp_name:
                        target = o["opponent"]
                        offer_data = o
                        break
                if not target:
                    self.json_resp({"success": False, "error": "Offer no longer available"})
                    return
                contract_pay = {
                    "base_pay": offer_data["base_purse"],
                    "win_bonus": offer_data["win_bonus"],
                    "total": offer_data["base_purse"] + offer_data["win_bonus"],
                }
                rivalry = None
                if career:
                    for r in career.rivalries:
                        if target in (r.fighter1, r.fighter2):
                            other = r.fighter2 if r.fighter1 == target else r.fighter1
                            rivalry = {
                                "intensity": r.intensity,
                                "fights": len(r.fights),
                                "trilogy": r.trilogy,
                                "opponent": other.name,
                                "record": r.get_record(f),
                            }
                            break
                fight_history = []
                for fighter in (f, target):
                    recent = []
                    w = fighter.win_streak or 0
                    ls = fighter.loss_streak or 0
                    if w > 0:
                        recent = [f"W"] * min(w, 5)
                    elif ls > 0:
                        recent = [f"L"] * min(ls, 5)
                    else:
                        recent = ["W", "L", "W"]
                    fight_history.append({"name": fighter.name, "recent": recent})
                self.json_resp({
                    "success": True,
                    "offer": {
                        "contract_pay": contract_pay,
                        "rivalry": rivalry,
                        "fight_history": fight_history,
                    }
                })

            elif path == "/api/free_agent_offers":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                f = session.get("fighter")
                tier_filter = params.get("tier", [""])[0]
                promos = []
                for p in gs["promotions"]:
                    if tier_filter and p.tier_name.lower() != tier_filter.lower():
                        continue
                    # Only show Regional promotions for new fighters (0 career fights)
                    if f and (f.career_total_fights or 0) == 0 and p.tier_name != "Regional":
                        continue
                    if f and f.wins < 3 and p.tier_name == "National":
                        continue
                    if f and f.wins < 5 and p.tier_name == "World":
                        continue
                    personality = getattr(p, "personality", {})
                    promos.append({
                        "name": p.name, "tier": p.tier_name,
                        "base_pay": p.base_pay, "win_bonus": p.win_bonus,
                        "perf_bonus": p.perf_bonus,
                        "num_fighters": len(p.fighters),
                        "personality": personality.get("description", ""),
                        "matchmaking": personality.get("matchmaking_style", "balanced"),
                        "marketing": personality.get("marketing_power", 1.0),
                        "prestige": personality.get("prestige", 1),
                    })
                self.json_resp({"promotions": promos})

            elif path == "/api/fight_state":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                fs = _get_fight_state(session)
                if fs:
                    self.json_resp({"success": True, "fight_state": fs})
                else:
                    self.json_resp({"success": False, "error": "No active fight"})

            elif path == "/api/agents":
                self.json_resp({"agents": utils.AGENTS})

            elif path == "/api/gyms":
                self.json_resp({"gyms": utils.GYMS})

            elif path == "/api/news":
                ensure_initialized()
                self.json_resp({"news": format_news_items(gs.get("world_news", []))})

            elif path == "/api/health":
                self.json_resp({
                    "status": "ok",
                    "initialized": gs.get("initialized", False),
                    "uptime": time.time() - gs.get("start_time", time.time()),
                    "sessions": len(gs.get("sessions", {})),
                })

            elif path == "/api/weight_classes":
                data = []
                for wc in utils.WEIGHT_CLASSES:
                    hr = utils.get_height_reach_range(wc["name"])
                    data.append({
                        "name": wc["name"],
                        "min_weight": wc["min"],
                        "max_weight": wc["max"],
                        "height_min": hr["height_min"],
                        "height_max": hr["height_max"],
                        "reach_min": hr["reach_min"],
                        "reach_max": hr["reach_max"],
                    })
                self.json_resp({"weight_classes": data})

            else:
                self.send_error(404)

        except Exception as e:
            self.json_resp({"error": str(e), "traceback": traceback.format_exc()})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-length", 0))
            content_type = self.headers.get("Content-Type", "")
            raw_body = self.rfile.read(length) if length else b""

            # Handle both JSON and form-encoded data
            if "application/json" in content_type:
                body = json.loads(raw_body) if raw_body else {}
            elif "application/x-www-form-urlencoded" in content_type:
                body = urllib.parse.parse_qs(raw_body.decode("utf-8"))
                # Convert lists to single values
                body = {k: v[0] if len(v) == 1 else v for k, v in body.items()}
            else:
                body = {}

            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/create_fighter":
                ensure_initialized()
                import html
                raw_name = body.get("name", "")
                name = html.escape(raw_name.strip()[:64]) if raw_name.strip() else ""
                if not name or not all(c.isalnum() or c in " -.'" for c in name):
                    first, last = utils.generate_name()
                    name = f"{first} {last}"
                try:
                    age = int(body.get("age", 25))
                except (ValueError, TypeError):
                    age = 25
                bg = body.get("background", "mma")
                wc_param = body.get("weight_class", 3)

                # Handle both string weight class names and integer indices
                if isinstance(wc_param, str):
                    # Find the weight class index by name
                    wc_idx = 3  # Default to lightweight
                    for i, wc in enumerate(utils.WEIGHT_CLASSES):
                        if wc_param.lower().replace(" ", "_") in wc["name"].lower().replace(" ", "_"):
                            wc_idx = i
                            break
                    wc = utils.WEIGHT_CLASSES[wc_idx]
                else:
                    wc_idx = wc_param
                    wc = utils.WEIGHT_CLASSES[wc_param]
                weight = random.randint(wc["min"], wc["max"])
                sid = body.get("sid", "") or secrets.token_urlsafe(16)
                nationality = body.get("nationality", "American")
                region = body.get("region", "California")
                trait_id = body.get("trait_id")
                personality_id = body.get("personality_id", "humble")
                stance = body.get("stance", None)
                game_date = datetime(2025, 1, 6)

                # Height and reach from request or weight-class defaults
                wc_name = utils.WEIGHT_CLASSES[wc_idx]["name"]
                hr_range = utils.get_height_reach_range(wc_name)
                height = body.get("height")
                reach = body.get("reach")
                if height is not None:
                    try:
                        height = int(height)
                    except (ValueError, TypeError):
                        height = None
                if reach is not None:
                    try:
                        reach = int(reach)
                    except (ValueError, TypeError):
                        reach = None
                # Clamp to weight-class range
                if height is not None:
                    height = utils.clamp(height, hr_range["height_min"], hr_range["height_max"])
                if reach is not None:
                    reach = utils.clamp(reach, hr_range["reach_min"], hr_range["reach_max"])

                f = Fighter(name, age, weight, bg, "balanced", nationality, region, trait_id, personality_id,
                            stance=stance, game_date=game_date, height=height, reach=reach)
                f.is_player = True

                # Age-scaled starting stats: 18yo starts ~25% below base, 35yo starts at base+5%
                age_min = 18
                age_max = 35
                age_range = age_max - age_min
                age_pct = (age - age_min) / max(1, age_range)
                stat_mod = -15 + (age_pct * 20)  # -15 at 18, +5 at 35
                for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
                    f.attributes[attr] = utils.clamp(f.attributes[attr] + stat_mod, utils.ATTR_MIN, utils.ATTR_MAX)

                regionals = get_promotions_by_tier("Regional")
                nationals = get_promotions_by_tier("National")
                worlds = get_promotions_by_tier("World")
                regional = regionals[0] if regionals else None
                national = nationals[0] if nationals else None
                world = worlds[0] if worlds else None

                career = CareerSystem(f)
                training = TrainingSystem(f)
                finance = FinancialSystem(f)
                health = HealthSystem(f)
                media = MediaSystem(f)
                event_sys = EventSystem()

                f.gym = None
                f.net_worth = 5000
                finance.net_worth = 5000

                session = get_or_create_session(sid)
                session["fighter"] = f
                session["career"] = career
                session["training"] = training
                session["finance"] = finance
                session["health"] = health
                session["media"] = media
                session["event_sys"] = event_sys
                set_session_promotion(session, None)
                session["current_event"] = None
                session["current_fight_booking"] = None
                session["current_fight"] = None
                session["game_date"] = game_date

                seed_regional_division(nationality, region, f.weight_class, 10)

                _persist_session(sid, session)

                _auto_save(sid, session)

                # Check if this is a form submission (not AJAX)
                if "application/x-www-form-urlencoded" in content_type:
                    state_json = json.dumps(get_state_dict(session))
                    self.json_resp({"success": True, "state": state_json, "sid": sid})
                else:
                    self.json_resp({"success": True, "state": get_state_dict(session), "sid": sid})

            elif path == "/api/advance_day":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                training = session.get("training")
                f = session.get("fighter")
                finance = session.get("finance")
                es = session.get("event_sys")
                fb = session.get("current_fight_booking")

                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return

                # Fight week handling — advance normally, block training, auto-trigger events
                fight_week_event = None
                if fb:
                    fb_age_days = max(0, (fb.date - session.get("game_date", datetime.now())).days) if fb.date else None
                    if fb_age_days is not None and 0 < fb_age_days <= 5:
                        fight_week_event = _trigger_fight_week_event(session, fb_age_days)

                game_date = session.get("game_date")

                if fight_week_event:
                    result = {
                        "day": DAYS_OF_WEEK[datetime.now().weekday()],
                        "is_rest": True,
                        "fight_week_event": fight_week_event,
                        "status": "fight_week",
                        "gains": {},
                        "fatigue": 0,
                        "injury": None,
                        "drill_over": False,
                    }
                    session["_last_fight_week_event"] = fight_week_event
                    progress = session.setdefault("fight_week_progress", {})
                    if fight_week_event.get("event"):
                        progress[fight_week_event["event"]] = fight_week_event
                else:
                    result = training.advance_day(game_date)

                if game_date:
                    game_date += timedelta(days=1)
                    session["game_date"] = game_date

                if f:
                    f.recover_injuries(game_date)

                if es and game_date:
                    es.advance_time(game_date)

                if game_date and game_date.day == 1:
                    if f:
                        f.monthly_aging(game_date)
                    if finance:
                        finance.process_monthly(game_date)
                    run_world_sim_async(game_date, es)

                fight_today = False
                if fb and fb.date and game_date and game_date >= fb.date:
                    if not session.get("fight_completed"):
                        fight_today = True

                _persist_session(sid, session)
                if game_date and game_date.day == 1:
                    _persist_world()
                    _auto_save(sid, session)

                self.json_resp({
                    "success": True,
                    "state": get_state_dict(session),
                    "day_result": result,
                    "fight_today": fight_today,
                })

            elif path == "/api/set_schedule":
                sid = body.get("sid", "")
                day_idx = int(body.get("day_idx", 0))
                drill_name = body.get("drill_name", None)
                session = get_or_create_session(sid)
                training = session.get("training")
                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return
                if not training.week_started:
                    training.week_started = True
                training.set_day_drill(day_idx, drill_name)
                _persist_session(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/stop_training":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                training = session.get("training")
                if training:
                    training.stop_training()
                _persist_session(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/start_training":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                training = session.get("training")
                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return
                from training import DRILLS
                drill_idx = body.get("drill_idx", 0)
                intensity = body.get("intensity", "moderate")
                if not isinstance(drill_idx, int) or drill_idx < 0 or drill_idx >= len(DRILLS):
                    self.json_resp({"error": "Invalid drill index"})
                    return
                drill = DRILLS[drill_idx]
                success = training.start_training(drill, intensity)
                if not success:
                    self.json_resp({"error": "Already in training"})
                    return
                _persist_session(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/event_card":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                event = session.get("current_event")
                if not event:
                    self.json_resp({"fights": []})
                    return
                fights_data = []
                for fb in event.get_sorted_fights():
                    fights_data.append({
                        "fighter1": fb.fighter1.name, "fighter2": fb.fighter2.name,
                        "position": fb.fight_position, "status": fb.status,
                        "is_title": fb.is_title_fight, "risk": fb.risk_level,
                        "winner": fb.winner.name if fb.winner else None,
                        "method": fb.method, "round": fb.round,
                        "is_player_fight": fb.fighter1 == session.get("fighter") or fb.fighter2 == session.get("fighter"),
                    })
                self.json_resp({"success": True, "event_name": event.name, "fights": fights_data})

            elif path == "/api/start_fight":
                sid = body.get("sid", "")
                strat_id = body.get("strategy", "aggressive_striking")
                session = get_or_create_session(sid)
                fb = session.get("current_fight_booking")
                f = session.get("fighter")
                if not fb or not f:
                    self.json_resp({"error": "No fight booked"})
                    return
                game_date = session.get("game_date")
                if game_date and fb.date and game_date < fb.date:
                    self.json_resp({"error": f"Fight day hasn't arrived yet! (Fight is in {(fb.date - game_date).days} days)"})
                    return
                if session.get("fight_completed"):
                    self.json_resp({"error": "This fight has already been completed"})
                    return
                opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
                is_title = fb.is_title_fight
                rounds = 5 if is_title else 3

                rivalry_info = None
                career = session.get("career")
                if career:
                    rivalry = career.get_or_create_rivalry(opponent)
                    if len(rivalry.fights) > 0:
                        last = rivalry.fights[-1]
                        detail = f"{last.winner.name} defeated {last.loser.name} by {last.method}"
                        if len(rivalry.fights) >= 2:
                            detail += f". In their second meeting, {detail}"
                        if rivalry.trilogy:
                            detail += " This is the rubber match!"
                        rivalry_info = {"has_history": True, "detail": detail, "intensity": rivalry.intensity}

                fight_context = {
                    "show_streaks": True,
                    "show_matchup": True,
                    "rivalry_info": rivalry_info,
                }
                try:
                    fight = Fight(f, opponent, rounds=rounds, is_title_fight=is_title, context=fight_context)
                except Exception as ex:
                    print(f"FIGHT INIT ERROR: {ex}")
                    traceback.print_exc()
                    self.json_resp({"error": f"Fight init failed: {str(ex)[:100]}"})
                    return
                session["current_fight"] = fight
                session["fight_started"] = True
                fs = FightStream(sid, fight, strat_id, opponent.name)
                set_fight_stream(sid, fs)
                fs.start()
                _persist_session(sid, session)
                self.json_resp({"success": True, "fight_streaming": True, "opponent": opponent.name})

            elif path == "/api/fight_events":
                sid = body.get("sid", "")
                from_index = int(body.get("from", 0))
                session = get_or_create_session(sid)
                fs = get_fight_stream(sid)
                if not fs:
                    self.json_resp({"error": "No active fight stream"})
                    return
                new_events = fs.get_new_events(from_index)
                self.json_resp({
                    "success": True,
                    "events": new_events,
                    "done": fs.done,
                    "total": fs.event_count,
                    "waiting": fs.waiting_for_input,
                })

            elif path == "/api/fight_action":
                sid = body.get("sid", "")
                strategy = body.get("strategy")
                session = get_or_create_session(sid)
                fs = get_fight_stream(sid)
                if not fs:
                    self.json_resp({"error": "No active fight stream"})
                    return
                fs.submit_strategy(strategy)
                self.json_resp({"success": True})

            elif path == "/api/scout_opponent":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                if not f:
                    self.json_resp({"error": "Not initialized"})
                    return
                f.times_scouted = getattr(f, 'times_scouted', 0) + 1
                fb = session.get("current_fight_booking")
                opponent = fb.fighter2 if fb and fb.fighter1 == f else None
                if not opponent and fb:
                    opponent = fb.fighter1
                if not opponent:
                    self.json_resp({"error": "No opponent to scout"})
                    return
                scouted = f.times_scouted
                opponent_attrs = opponent.attributes if scouted >= 3 else (
                    {k: round(v, -1) for k, v in opponent.attributes.items()} if scouted >= 1 else {})
                preferred_strats = opponent.preferred_strategies if hasattr(opponent, 'preferred_strategies') else []
                attrs = opponent.attributes
                comp_strike_def = (attrs.get("head_movement", 50) + attrs.get("blocking", 50) +
                                   attrs.get("parrying", 50) + attrs.get("footwork_defense", 50) +
                                   attrs.get("counter_timing", 50)) / 5
                comp_td_def = (attrs.get("sprawl_technique", 50) + attrs.get("wrestling_defense", 50) * 2) / 3
                comp_ground_def = (attrs.get("guard_retention", 50) + attrs.get("scrambling", 50) +
                                   attrs.get("ground_striking_defense", 50) + attrs.get("submission_awareness", 50)) / 4
                height_diff = (f.height or 0) - (opponent.height or 0)
                reach_diff = (f.reach or 0) - (opponent.reach or 0)

                def describe_comp(val, high, mid, low):
                    if val >= 70:
                        return high
                    if val >= 50:
                        return mid
                    return low

                comp_notes = []
                comp_notes.append(f"Striking D: {describe_comp(comp_strike_def, 'excellent footwork & defense', 'solid fundamentals', 'porous striking defense')}")
                comp_notes.append(f"Takedown D: {describe_comp(comp_td_def, 'strong anti-wrestling', 'decent sprawl', 'vulnerable to takedowns')}")
                comp_notes.append(f"Ground D: {describe_comp(comp_ground_def, 'dangerous off the back', 'competent on the mat', 'weakness on the ground')}")
                if height_diff > 2:
                    comp_notes.append(f"You have a height advantage (+{height_diff}\")")
                elif height_diff < -2:
                    comp_notes.append(f"They have a height advantage ({height_diff}\")")
                if reach_diff > 2:
                    comp_notes.append(f"You have a reach advantage (+{reach_diff}\")")
                elif reach_diff < -2:
                    comp_notes.append(f"They have a reach advantage ({reach_diff}\")")

                scouting_report = {
                    "level": "full" if scouted >= 3 else ("partial" if scouted >= 1 else "none"),
                    "sessions": scouted,
                    "opponent_archetype": opponent.archetype,
                    "opponent_background": opponent.background,
                    "opponent_attrs_visible": scouted >= 1,
                    "opponent_preferred_strategies": preferred_strats if scouted >= 3 else [],
                    "composites": {
                        "striking_defense": round(comp_strike_def),
                        "takedown_defense": round(comp_td_def),
                        "ground_defense": round(comp_ground_def),
                        "height_diff": height_diff,
                        "reach_diff": reach_diff,
                    },
                    "composite_notes": comp_notes,
                }
                self.json_resp({"success": True, "scouting": scouting_report})

            elif path == "/api/fight_offer":
                ensure_initialized()
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                career = session.get("career")
                promo = get_session_promotion(session)
                opp_name = body.get("opponent", "")
                if not f or not promo:
                    self.json_resp({"success": False, "error": "Not signed"})
                    return
                offers = promo.generate_fight_offers(f, count=3)
                target = None
                offer_data = None
                for o in offers:
                    if o["opponent"].name == opp_name:
                        target = o["opponent"]
                        offer_data = o
                        break
                if not target:
                    self.json_resp({"success": False, "error": "Offer no longer available"})
                    return
                contract_pay = {
                    "base_pay": offer_data["base_purse"],
                    "win_bonus": offer_data["win_bonus"],
                    "total": offer_data["base_purse"] + offer_data["win_bonus"],
                }
                rivalry = None
                if career:
                    for r in career.rivalries:
                        if target in (r.fighter1, r.fighter2):
                            other = r.fighter2 if r.fighter1 == target else r.fighter1
                            rivalry = {
                                "intensity": r.intensity,
                                "fights": len(r.fights),
                                "trilogy": r.trilogy,
                                "opponent": other.name,
                                "record": r.get_record(f),
                            }
                            break
                fight_history = []
                for fighter in (f, target):
                    recent = []
                    w = fighter.win_streak or 0
                    ls = fighter.loss_streak or 0
                    if w > 0:
                        recent = [f"W"] * min(w, 5)
                    elif ls > 0:
                        recent = [f"L"] * min(ls, 5)
                    else:
                        recent = ["W", "L", "W"]
                    fight_history.append({"name": fighter.name, "recent": recent})
                self.json_resp({
                    "success": True,
                    "offer": {
                        "contract_pay": contract_pay,
                        "rivalry": rivalry,
                        "fight_history": fight_history,
                    }
                })

            elif path == "/api/fight_bonuses":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                fb = session.get("current_fight_booking")
                event = session.get("current_event")
                if fb and event:
                    bonuses = event.determine_bonuses()
                    self.json_resp({"success": True, "bonuses": bonuses})
                else:
                    self.json_resp({"bonuses": None})

            elif path == "/api/complete_fight":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                fb = session.get("current_fight_booking")
                fight = session.get("current_fight")
                career = session.get("career")
                finance = session.get("finance")
                game_date = session.get("game_date", datetime.now())
                if not fight or not fb or not f:
                    self.json_resp({"error": "No fight to complete"})
                    return
                # Wait for fight stream to finish if active
                fs = get_fight_stream(sid)
                if fs and not fs.done:
                    fs.pause_event.set()  # Unpause if waiting
                    for _ in range(100):
                        if fs.done:
                            break
                        time.sleep(0.1)
                    clear_fight_stream(sid)
                opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
                winner = fight.winner
                won = winner == f if winner else False
                is_draw = winner is None
                method = fight.win_method or "Decision"
                fb.complete(winner, method, fight.win_round)
                original_opp = session.get("_opponent_original")
                if original_opp:
                    original_opp.wins = opponent.wins
                    original_opp.losses = opponent.losses
                    original_opp.draws = opponent.draws
                    original_opp.knockouts = opponent.knockouts
                    original_opp.submissions = opponent.submissions
                    original_opp.win_streak = opponent.win_streak
                    original_opp.loss_streak = opponent.loss_streak
                if winner:
                    f.shake_ring_rust()
                    opponent.shake_ring_rust()
                if not is_draw:
                    if career and career.contract:
                        pi = finance.add_fight_pay(
                            career.contract.base_pay,
                            career.contract.win_bonus if won else 0,
                            perf_bonus=0,
                            game_date=game_date
                        )
                        career.contract.complete_fight(won, False)
                        career.career_earnings += pi["net"]
                    if won and fb.is_title_fight:
                        if career.current_promotion.champions.get(f.weight_class) != f:
                            career.win_title()
                        else:
                            career.defend_title()
                else:
                    # Draw: still get base pay, contract fight still counts
                    if career and career.contract:
                        pi = finance.add_fight_pay(
                            career.contract.base_pay,
                            0,
                            perf_bonus=0,
                            game_date=game_date
                        )
                        career.contract.complete_fight(False, False)
                        career.career_earnings += pi["net"]
                milestones = []
                if career:
                    milestones = career.check_milestones(won, method, fight.win_round or 0)

                bonuses = None
                event = session.get("current_event")
                if event:
                    bonuses_data = event.determine_bonuses()
                    if bonuses_data:
                        bonuses = bonuses_data

                # Apply popularity changes
                pop_gain = 0
                fb_state = session.get("current_fight_booking")
                if fb_state:
                    pos = fb_state.fight_position
                    pop_by_pos = {"prelim": 2 if won else -1, "main_card": 5 if won else -2,
                                  "co_main": 10 if won else -5, "main_event": 15 if won else -8}
                    pop_gain = pop_by_pos.get(pos, 0) if won else pop_by_pos.get(pos, 0)
                    if "KO" in method or "TKO" in method:
                        pop_gain += 5
                    if fb_state.is_title_fight:
                        pop_gain += 10 if won else -3
                f.popularity = utils.clamp(getattr(f, "popularity", 10) + pop_gain, 0, 100)

                # Record career damage after fight
                if fight.fight_log:
                    f.record_fight_damage(fight.f1_head_damage if f == fight.fighter1 else fight.f2_head_damage,
                                           was_ko="KO" in method)

                # Record season fight data
                if career:
                    career.record_season_fight(won, method, fight.win_round or 0, opponent, fb.is_title_fight)

                # Advance season and check for year-end awards
                season_award = None
                if career:
                    season_award = career.advance_season(game_date)
                    if season_award:
                        news_list = gs.setdefault("world_news", [])
                        news_list.append(season_award)

                session["current_event"] = None
                session["current_fight_booking"] = None
                session["current_fight"] = None
                session["fight_started"] = False
                fight_details = None
                if fight:
                    def ds(state):
                        return {
                            "sig_strikes": state.get("significant_strikes_landed", 0),
                            "strikes_thrown": state.get("strikes_thrown", 0),
                            "takedowns": state.get("takedowns_landed", 0),
                            "takedowns_attempted": state.get("takedowns_attempted", 0),
                            "submissions": state.get("submissions_attempted", 0),
                            "knockdowns": state.get("knockdown_count", 0),
                            "guard_passes": state.get("guard_passes", 0),
                        }
                    fight_details = {
                        "f1_details": ds(fight.f1_state),
                        "f2_details": ds(fight.f2_state),
                        "method": fight.win_method,
                        "round": fight.win_round,
                    }

                session["fight_completed"] = True
                ensure_regional_opponents(session)
                _persist_session(sid, session)
                _persist_world()
                _auto_save(sid, session)
                self.json_resp({
                    "success": True, "won": won,
                    "state": get_state_dict(session),
                    "milestones": milestones,
                    "bonuses": bonuses,
                    "season_award": season_award,
                    "fight_details": fight_details,
                })

            elif path == "/api/sign_free_agent":
                ensure_initialized()
                sid = body.get("sid", "")
                promo_name = body.get("name", "")
                tier_name = body.get("tier", "Regional")
                session = get_or_create_session(sid)
                career = session.get("career")
                f = session.get("fighter")
                game_date = session.get("game_date")
                promo = get_promotion_by_name(promo_name)
                if not promo:
                    for p in gs["promotions"]:
                        if p.tier_name == tier_name:
                            promo = p
                            break
                if not career or not promo or not f:
                    self.json_resp({"error": "Cannot sign"})
                    return
                career.sign_with_promotion(promo, 4, game_date)
                set_session_promotion(session, promo)
                all_fighters = gs.get("all_fighters")
                if all_fighters is not None and f not in all_fighters:
                    all_fighters.append(f)
                ensure_regional_opponents(session)
                _persist_session(sid, session)
                _persist_world()
                _auto_save(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/accept_promotion":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                career = session.get("career")
                game_date = session.get("game_date")
                if not career:
                    self.json_resp({"error": "No career system"})
                    return
                promotions = get_promotions_by_tier()
                offer = career.check_promotion_offer(promotions)
                if not offer:
                    self.json_resp({"error": "No promotion offer available"})
                    return
                career.sign_with_promotion(offer, 4, game_date)
                set_session_promotion(session, offer)
                ensure_regional_opponents(session)
                _persist_session(sid, session)
                _persist_world()
                _auto_save(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/advance_time":
                ensure_initialized()
                sid = body.get("sid", "")
                days = int(body.get("days", 7))
                session = get_or_create_session(sid)
                training = session.get("training")
                f = session.get("fighter")
                finance = session.get("finance")
                es = session.get("event_sys")
                fb = session.get("current_fight_booking")

                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return

                # Block advancing during fight week
                if fb:
                    fb_age_days = max(0, (fb.date - session.get("game_date", datetime.now())).days) if fb.date else None
                    if fb_age_days is not None and 0 < fb_age_days <= 5:
                        self.json_resp({"error": f"Fight week in progress! {fb_age_days} days until the fight — cannot skip."})
                        return

                game_date = session.get("game_date")
                fight_today = False

                for _ in range(days):
                    training.advance_day(game_date)

                    if game_date:
                        game_date += timedelta(days=1)

                    if f:
                        f.recover_injuries(game_date)

                    if es and game_date:
                        es.advance_time(game_date)

                    if game_date and game_date.day == 1:
                        if f:
                            f.monthly_aging(game_date)
                        if finance:
                            finance.process_monthly(game_date)
                        run_world_sim_async(game_date, es)

                    if fb and fb.date and game_date and game_date >= fb.date:
                        if not session.get("fight_completed"):
                            fight_today = True

                session["game_date"] = game_date

                _persist_session(sid, session)
                if game_date and game_date.day == 1:
                    _persist_world()
                    _auto_save(sid, session)

                self.json_resp({
                    "success": True,
                    "state": get_state_dict(session),
                    "fight_today": fight_today,
                })

            elif path == "/api/accept_offer":
                sid = body.get("sid", "")
                opp_name = body.get("opponent", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                promo = get_session_promotion(session)
                career = session.get("career")
                game_date = session.get("game_date")
                if not f or not promo:
                    self.json_resp({"error": "Not signed"})
                    return
                offers = promo.generate_fight_offers(f, count=3)
                target = None
                offer_data = None
                for o in offers:
                    if o["opponent"].name == opp_name:
                        target = o["opponent"]
                        offer_data = o
                        break
                if not target:
                    self.json_resp({"error": "Offer no longer available"})
                    return
                # Reset declined counter on accept
                f.declined_offers_count = getattr(f, "declined_offers_count", 0)
                f.declined_offers_count = max(0, f.declined_offers_count - 1)
                # Deep copy opponent for booking
                import copy
                target = copy.deepcopy(target)
                session["_opponent_original"] = target
                # Create event and booking
                weeks_out = int(body.get("weeks", 8))
                fight_date = (game_date or datetime.now()) + timedelta(weeks=weeks_out)
                is_title = (promo.champions.get(f.weight_class) is not None
                            and target.name == promo.champions[f.weight_class].name)
                es = session.get("event_sys") or EventSystem()
                event = es.create_event(f"Fight Night: {f.name} vs {target.name}", fight_date, promo)
                risk = offer_data.get("risk", "50-50") if offer_data else "50-50"
                fb = es.book_fight(event, f, target, is_title_fight=is_title, risk_level=risk)
                if fb:
                    fb.set_fight_position(offer_data.get("card_position", "main_card") if offer_data else "main_card")
                es.generate_card(event, fb, promo, f)
                session["event_sys"] = es
                session["current_event"] = event
                session["current_fight_booking"] = fb
                session["fight_completed"] = False
                if career:
                    career.add_rivalry(target)
                _persist_session(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/decline_offer":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                promo = get_session_promotion(session)
                if not f or not promo:
                    self.json_resp({"error": "Not signed"})
                    return
                f.declined_offers_count = getattr(f, "declined_offers_count", 0) + 1
                rel = promo.check_contract_relationship(f)
                _persist_session(sid, session)
                self.json_resp({"success": True, "relationship": rel})

            elif path == "/api/hire_agent":
                sid = body.get("sid", "")
                agent_name = body.get("agent", "")
                session = get_or_create_session(sid)
                finance = session.get("finance")
                game_date = session.get("game_date")
                if not finance:
                    self.json_resp({"error": "No finance system"})
                    return
                if finance.hire_agent(agent_name, game_date):
                    self.json_resp({"success": True, "state": get_state_dict(session)})
                else:
                    self.json_resp({"error": "Failed to hire agent"})

            elif path == "/api/fire_agent":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                finance = session.get("finance")
                game_date = session.get("game_date")
                if finance:
                    finance.fire_agent(game_date)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/cut_weight":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                fb = session.get("current_fight_booking")
                if not f or not fb:
                    self.json_resp({"error": "No fight booked"})
                    return
                target = f.natural_weight_lbs
                for wc in utils.WEIGHT_CLASSES:
                    if wc["name"] == f.weight_class:
                        target = wc["max"]
                        break
                intensity = body.get("intensity", "standard")
                if intensity not in ("safe", "standard", "aggressive"):
                    intensity = "standard"
                passed = f.cut_weight(target, fb.is_title_fight, intensity)
                _persist_session(sid, session)

                wc_result = {
                    "event": "weigh_in",
                    "text": f"Weigh-in: {'PASSED' if passed else 'FAILED'}. Cut {f.weight_cut_lbs:.1f} lbs. Hydration: {f.hydration_level:.0f}%",
                    "passed": passed,
                    "cut_lbs": f.weight_cut_lbs,
                    "hydration": f.hydration_level,
                }
                progress = session.setdefault("fight_week_progress", {})
                progress["weigh_in"] = wc_result

                self.json_resp({
                    "success": True, "passed": passed,
                    "cut_lbs": f.weight_cut_lbs, "hydration": f.hydration_level,
                    "weigh_in_pass": f.weigh_in_pass,
                    "state": get_state_dict(session),
                })

            elif path == "/api/press_conference":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                media = session.get("media")
                fb = session.get("current_fight_booking")
                choice = body.get("choice", "staredown")
                if not f or not fb:
                    self.json_resp({"error": "No fight booked"})
                    return
                if choice not in ("respectful", "trash_talk", "staredown"):
                    choice = "staredown"
                opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
                if media and hasattr(media, 'do_press_conference'):
                    result = media.do_press_conference(opponent)
                else:
                    result = {"text": f"Press conference: {f.name} and {opponent.name} face the media.", "popularity_gain": 1.0}
                if choice == "respectful":
                    result["text"] = f"Respectful press conference from {f.name}, praising {opponent.name}."
                    result["popularity_gain"] = 1.5
                    if f.attributes.get("composure"):
                        f.attributes["composure"] = min(100, f.attributes["composure"] + 2)
                elif choice == "trash_talk":
                    result["text"] = f"WAR OF WORDS! {f.name} unloads on {opponent.name} at the press conference!"
                    result["popularity_gain"] = 3.0
                    if opponent.attributes.get("composure"):
                        opponent.attributes["composure"] = max(0, opponent.attributes["composure"] - 3)
                    if f.attributes.get("composure"):
                        f.attributes["composure"] = max(0, f.attributes["composure"] - 2)
                else:
                    result["text"] = f"Intense staredown! {f.name} and {opponent.name} face off at the press conference."
                    result["popularity_gain"] = 2.0
                progress = session.setdefault("fight_week_progress", {})
                progress["press_conference"] = result
                _persist_session(sid, session)
                self.json_resp({"success": True, "event_result": result, "state": get_state_dict(session)})

            elif path == "/api/open_workout":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                media = session.get("media")
                choice = body.get("choice", "technical")
                if not f:
                    self.json_resp({"error": "Not initialized"})
                    return
                result = {"text": f"Open workouts: {f.name} shows skills.", "popularity_gain": 1.0}
                if choice == "power":
                    result["text"] = f"{f.name} unleashes POWER strikes at open workouts! The crowd roars!"
                    result["popularity_gain"] = 2.0
                    for attr in ["striking_power", "kick_power"]:
                        f.attributes[attr] = min(100, f.attributes.get(attr, 50) + 0.5)
                elif choice == "showboat":
                    result["text"] = f"{f.name} puts on a SHOW at open workouts! Flashy moves and charisma."
                    result["popularity_gain"] = 2.5
                    f.attributes["charisma"] = min(100, f.attributes.get("charisma", 50) + 1)
                else:
                    result["text"] = f"{f.name} looks sharp and technical at open workouts."
                    result["popularity_gain"] = 1.5
                    for attr in ["hand_speed", "striking_accuracy", "footwork_defense"]:
                        f.attributes[attr] = min(100, f.attributes.get(attr, 50) + 0.5)
                if media:
                    media.update_popularity(result["popularity_gain"])
                progress = session.setdefault("fight_week_progress", {})
                progress["open_workout"] = result
                _persist_session(sid, session)
                self.json_resp({"success": True, "event_result": result, "state": get_state_dict(session)})

            elif path == "/api/faceoff":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                fb = session.get("current_fight_booking")
                choice = body.get("choice", "calm")
                if not f or not fb:
                    self.json_resp({"error": "No fight booked"})
                    return
                opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
                charisma = f.attributes.get("charisma", 50)
                mental_toughness = f.attributes.get("mental_toughness", 50)
                opp_composure = opponent.attributes.get("composure", 50)
                score_mod = {"intense": 5, "calm": 0, "dismissive": 3}
                score = charisma + mental_toughness - opp_composure + score_mod.get(choice, 0) + random.uniform(-8, 8)
                if score > 10:
                    text = f"{f.name} dominates the faceoff! {opponent.name} looks visibly shaken."
                    f.attributes["composure"] = min(100, f.attributes.get("composure", 50) + 4)
                    opponent.attributes["composure"] = max(0, opponent.attributes["composure"] - 4)
                elif score > 0:
                    text = f"{f.name} gets the better of the faceoff exchange."
                    f.attributes["composure"] = min(100, f.attributes.get("composure", 50) + 2)
                    opponent.attributes["composure"] = max(0, opponent.attributes["composure"] - 1)
                elif score > -10:
                    text = f"Neither fighter backs down. The faceoff is intense!"
                else:
                    text = f"{opponent.name} gets into {f.name}'s head during the faceoff."
                    f.attributes["composure"] = max(0, f.attributes.get("composure", 50) - 4)
                    opponent.attributes["composure"] = min(100, opponent.attributes.get("composure", 50) + 2)
                result = {"text": text, "score": score}
                progress = session.setdefault("fight_week_progress", {})
                progress["faceoff"] = result
                _persist_session(sid, session)
                self.json_resp({"success": True, "event_result": result, "state": get_state_dict(session)})

            elif path == "/api/rest_day":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                training = session.get("training")
                choice = body.get("choice", "ice_bath")
                if not f:
                    self.json_resp({"error": "Not initialized"})
                    return
                result = {"text": f"{f.name} takes it easy on rest day.", "fatigue_recovery": 0.15}
                if choice == "massage":
                    result["text"] = f"{f.name} gets a deep tissue massage. Muscles feel loose and ready."
                    result["fatigue_recovery"] = 0.25
                    for inj in f.injuries:
                        inj["severity"] = max(0, inj["severity"] - 0.2)
                elif choice == "meditation":
                    result["text"] = f"{f.name} meditates and visualizes victory. Mental focus sharpens."
                    result["fatigue_recovery"] = 0.15
                    for attr in ["mental_toughness", "composure", "fight_iq"]:
                        f.attributes[attr] = min(100, f.attributes.get(attr, 50) + 1)
                elif choice == "light_spar":
                    result["text"] = f"{f.name} does light sparring to keep the edge."
                    result["fatigue_recovery"] = 0.05
                    for attr in ["hand_speed", "striking_accuracy", "footwork_defense"]:
                        f.attributes[attr] = min(100, f.attributes.get(attr, 50) + 0.5)
                else:
                    result["text"] = f"{f.name} rests with ice baths. Body recovers."
                    result["fatigue_recovery"] = 0.25
                if training:
                    training.fatigue = max(0.0, training.fatigue - result.get("fatigue_recovery", 0.15))
                result["fatigue"] = round(training.fatigue * 100) if training else 0
                progress = session.setdefault("fight_week_progress", {})
                progress["rest_day"] = result
                _persist_session(sid, session)
                self.json_resp({"success": True, "event_result": result, "state": get_state_dict(session)})

            elif path == "/api/join_gym":
                sid = body.get("sid", "")
                gym_name = body.get("gym", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                finance = session.get("finance")
                if not f or not finance:
                    self.json_resp({"error": "Not initialized"})
                    return
                for g in utils.GYMS:
                    if g["name"] == gym_name:
                        if not finance.can_afford(g["monthly_fee"]):
                            self.json_resp({"error": "Cannot afford membership"})
                            return
                        f.gym = gym_name
                        _persist_session(sid, session)
                        self.json_resp({"success": True, "state": get_state_dict(session)})
                        return
                self.json_resp({"error": "Gym not found"})

            elif path == "/api/film_study":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                training = session.get("training")
                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return
                success = training.start_film_study()
                _persist_session(sid, session)
                self.json_resp({"success": success, "state": get_state_dict(session)})

            elif path == "/api/migrate_weight":
                sid = body.get("sid", "")
                direction = body.get("direction", "up")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                if not f:
                    self.json_resp({"error": "Not initialized"})
                    return
                current_idx = utils.get_weight_class_index(f.weight_class)
                target_idx = current_idx + (1 if direction == "up" else -1)
                if target_idx < 0 or target_idx >= len(utils.WEIGHT_CLASSES):
                    self.json_resp({"error": "No weight class available in that direction"})
                    return
                target_wc = utils.WEIGHT_CLASSES[target_idx]
                target_weight = random.randint(target_wc["min"], target_wc["max"])
                if direction == "up":
                    success = f.migrate_weight_class_up(target_weight)
                else:
                    success = f.migrate_weight_class_down(target_weight)
                self.json_resp({"success": success, "state": get_state_dict(session)})

            elif path == "/api/start_recovery":
                sid = body.get("sid", "")
                recovery_type = body.get("type", "ice_bath")
                session = get_or_create_session(sid)
                training = session.get("training")
                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return
                success = training.start_recovery(recovery_type)
                _persist_session(sid, session)
                self.json_resp({"success": success, "state": get_state_dict(session)})

            elif path == "/api/leave_gym":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                if f:
                    f.gym = None
                _persist_session(sid, session)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/balance_test":
                """Run multiple simulated fights and return aggregate stats."""
                from copy import deepcopy

                from generator import generate_single_fighter
                sid = body.get("sid", "")
                iterations = int(body.get("iterations", 100))
                session = get_or_create_session(sid)
                f = session.get("fighter")
                if not f:
                    self.json_resp({"error": "No fighter in session"})
                    return
                wc_data = next((wc_item for wc_item in utils.WEIGHT_CLASSES if wc_item["name"] == f.weight_class), None)
                if not wc_data:
                    self.json_resp({"error": "Unknown weight class"})
                    return
                # Generate a generic opponent of same weight class
                opponent = generate_single_fighter(
                    random.randint(wc_data["min"], wc_data["max"]),
                    skill_mean=utils.gaussian_random(50, 10, 25, 65),
                    skill_std=utils.gaussian_random(15, 3, 8, 20)
                )
                opponent.weight_class = f.weight_class
                results = {"f1_wins": 0, "f2_wins": 0, "draws": 0, "kos": 0, "tkos": 0,
                           "submissions": 0, "decisions": 0, "total_rounds": [], "avg_duration": 0}
                strats = [s["id"] for s in STRATEGIES]
                for _ in range(iterations):
                    f_copy = deepcopy(f)
                    opp_copy = deepcopy(opponent)
                    a_strat = random.choice(strats)
                    d_strat = random.choice(strats)
                    fight = Fight(f_copy, opp_copy, rounds=3, is_title_fight=False)
                    fight.strategy1.set_pre_fight_strategy(a_strat)
                    fight.strategy2.set_pre_fight_strategy(d_strat)
                    for event in fight.simulate_fight_gen():
                        if event["type"] == "complete":
                            break
                    if fight.winner and fight.winner.name == f.name:
                        results["f1_wins"] += 1
                    elif fight.winner and fight.winner.name == opponent.name:
                        results["f2_wins"] += 1
                    else:
                        results["draws"] += 1
                    if fight.win_method:
                        if "KO" in fight.win_method and "TKO" not in fight.win_method:
                            results["kos"] += 1
                        elif "TKO" in fight.win_method:
                            results["tkos"] += 1
                        elif "Submission" in fight.win_method:
                            results["submissions"] += 1
                        else:
                            results["decisions"] += 1
                    results["total_rounds"].append(fight.win_round or 3)
                results["avg_rounds"] = sum(results["total_rounds"]) / max(1, len(results["total_rounds"]))
                results["total"] = iterations
                del results["total_rounds"]
                self.json_resp({"success": True, "results": results})

            elif path == "/api/bulk_simulate":
                """Advanced bulk simulation with configurable fighters."""
                from generator import generate_single_fighter
                iterations = int(body.get("iterations", 100))
                f1_mean = int(body.get("f1_mean", 50))
                f1_std = int(body.get("f1_std", 8))
                f2_mean = int(body.get("f2_mean", 50))
                f2_std = int(body.get("f2_std", 8))
                wc_idx = int(body.get("weight_class", 3))
                wc_data = utils.WEIGHT_CLASSES[wc_idx]

                detailed = body.get("detailed", False)
                results = {"f1_wins": 0, "f2_wins": 0, "draws": 0,
                           "ko_tko_pct": 0, "sub_pct": 0, "dec_pct": 0,
                           "avg_rounds": 0, "by_method": {}}
                round_data = []

                for i in range(iterations):
                    f1 = generate_single_fighter(
                        random.randint(wc_data["min"], wc_data["max"]),
                        skill_mean=utils.gaussian_random(f1_mean, f1_std, 35, 80),
                        skill_std=utils.gaussian_random(10, 3, 5, 18)
                    )
                    f2 = generate_single_fighter(
                        random.randint(wc_data["min"], wc_data["max"]),
                        skill_mean=utils.gaussian_random(f2_mean, f2_std, 35, 80),
                        skill_std=utils.gaussian_random(10, 3, 5, 18)
                    )
                    f1.weight_class = wc_data["name"]
                    f2.weight_class = wc_data["name"]

                    a_strat = random.choice([s["id"] for s in STRATEGIES])
                    d_strat = random.choice([s["id"] for s in STRATEGIES])
                    fight = Fight(f1, f2, rounds=3, is_title_fight=False)
                    fight.strategy1.set_pre_fight_strategy(a_strat)
                    fight.strategy2.set_pre_fight_strategy(d_strat)
                    for event in fight.simulate_fight_gen():
                        if event["type"] == "complete":
                            break
                    if fight.winner == f1:
                        results["f1_wins"] += 1
                    elif fight.winner == f2:
                        results["f2_wins"] += 1
                    else:
                        results["draws"] += 1

                    method_cat = "Decision"
                    if fight.win_method:
                        if "Submission" in fight.win_method:
                            method_cat = "Submission"
                        elif "KO" in fight.win_method and "TKO" not in fight.win_method:
                            method_cat = "KO"
                        elif "TKO" in fight.win_method:
                            method_cat = "TKO"
                    results["by_method"][method_cat] = results["by_method"].get(method_cat, 0) + 1
                    round_data.append(fight.win_round or 3)

                total = max(1, iterations)
                results["ko_tko_pct"] = (results["by_method"].get("KO", 0) + results["by_method"].get("TKO", 0)) / total * 100
                results["sub_pct"] = results["by_method"].get("Submission", 0) / total * 100
                results["dec_pct"] = results["by_method"].get("Decision", 0) / total * 100
                results["avg_rounds"] = sum(round_data) / total
                results["total"] = iterations

                if detailed:
                    # Also capture archetype matchup breakdowns
                    results["f1_win_pct"] = round(results["f1_wins"] / total * 100, 1)
                    results["f2_win_pct"] = round(results["f2_wins"] / total * 100, 1)
                    results["draw_pct"] = round(results["draws"] / total * 100, 1)
                    results["avg_rounds"] = round(results["avg_rounds"], 1)

                self.json_resp({"success": True, "results": results})

            elif path == "/api/save_game":
                ensure_initialized()
                sid = body.get("sid", "")
                slot_index = int(body.get("slot", 0))
                display_name = body.get("name", "Save")
                if not sid:
                    self.json_resp({"error": "No session id"})
                    return
                session = get_or_create_session(sid)
                if session.get("current_fight") or session.get("fight_started"):
                    self.json_resp({"error": "Cannot save during an active fight"})
                    return
                if not session.get("fighter"):
                    self.json_resp({"error": "No fighter to save"})
                    return
                promotions_tuple = get_promotions_by_tier()
                world_data = (
                    promotions_tuple,
                    gs.get("all_fighters", []),
                    gs.get("world_sim"),
                    gs.get("world_news", []),
                )
                try:
                    save_id = save_to_slot(sid, slot_index, display_name, session, world_data)
                    self.json_resp({"success": True, "save_id": save_id})
                except Exception as e:
                    self.json_resp({"error": f"Save failed: {e}"})

            elif path == "/api/load_game":
                ensure_initialized()
                sid = body.get("sid", "")
                slot_index = int(body.get("slot", 0))
                if not sid:
                    self.json_resp({"error": "No session id"})
                    return
                try:
                    result = load_from_slot(sid, slot_index)
                    if not result:
                        self.json_resp({"error": "Save not found"})
                        return
                    loaded_session, world_data = result
                    promotions, all_fighters, world_sim, world_news = world_data

                    # Match session fighter with loaded world fighters
                    loaded_f = loaded_session.get("fighter")
                    if loaded_f:
                        db_id = getattr(loaded_f, '_db_id', None)
                        found = None
                        for af in all_fighters:
                            af_id = getattr(af, '_db_id', None)
                            if db_id and af_id and af_id == db_id:
                                found = af
                                break
                        if not found:
                            for af in all_fighters:
                                if af.name == loaded_f.name and af.age == loaded_f.age:
                                    found = af
                                    break
                        if found:
                            loaded_session["fighter"] = found
                            for key in ["career", "training", "finance", "health", "media"]:
                                obj = loaded_session.get(key)
                                if obj:
                                    obj.fighter = found

                    # Replace global world state with snapshot
                    with _gs_lock:
                        gs["promotions"] = promotions
                        gs["all_fighters"] = all_fighters
                        gs["world_sim"] = world_sim
                        gs["world_news"] = world_news or []

                    # Replace session data — now via diskcache
                    _session_cache[sid] = loaded_session
                    _session_cache.expire(sid, timedelta(hours=48))

                    self.json_resp({
                        "success": True,
                        "state": get_state_dict(loaded_session),
                    })
                except SaveIncompatibleError as e:
                    self.json_resp({"error": str(e)})
                except Exception as e:
                    self.json_resp({"error": f"Load failed: {e}", "traceback": traceback.format_exc()})

            elif path == "/api/delete_save":
                sid = body.get("sid", "")
                slot_index = int(body.get("slot", 0))
                if not sid:
                    self.json_resp({"error": "No session id"})
                    return
                delete_save(sid, slot_index)
                self.json_resp({"success": True})

            elif path == "/api/export_save":
                sid = body.get("sid", "")
                slot_index = int(body.get("slot", 0))
                if not sid:
                    self.json_resp({"error": "No session id"})
                    return
                data = export_save(sid, slot_index)
                if not data:
                    self.json_resp({"error": "Save not found"})
                    return
                self.json_resp({"success": True, "export": data})

            elif path == "/api/import_save":
                sid = body.get("sid", "")
                slot_index = int(body.get("slot", 0))
                import_data = body.get("data")
                if not sid or not import_data:
                    self.json_resp({"error": "Missing sid or import data"})
                    return
                try:
                    import_save(sid, slot_index, import_data)
                    self.json_resp({"success": True})
                except SaveIncompatibleError as e:
                    self.json_resp({"error": str(e)})
                except Exception as e:
                    self.json_resp({"error": f"Import failed: {e}"})

            else:
                self.json_resp({"error": "Unknown endpoint"})

        except Exception as e:
            self.json_resp({"error": str(e), "traceback": traceback.format_exc()})

    def json_resp(self, data):
        try:
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except BrokenPipeError:
            pass

if __name__ == "__main__":
    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        """Handle each request in a new thread"""
        daemon_threads = True

    PORT = int(os.environ.get("PORT", 8000))
    HOST = "0.0.0.0"

    gs["start_time"] = time.time()

    Thread(target=_session_cleanup_loop, daemon=True).start()

    print(f"Server starting on port {PORT}...")
    server = ThreadedHTTPServer((HOST, PORT), Handler)
    server.allow_reuse_address = True
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print("Server listening, initializing game world in background...")
    Thread(target=lambda: [ensure_initialized(), print("Game world ready!")], daemon=True).start()
    server_thread.join()
