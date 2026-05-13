#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json
import os
import urllib.parse
import traceback
import random
import copy
from datetime import datetime, timedelta
from threading import Lock, Thread
import time

APP_DIR = os.path.dirname(os.path.abspath(__file__))

from fighter import Fighter
from training import TrainingSystem, TrainingCamp, DAYS_OF_WEEK
from promotion import Promotion, create_promotions
from career import CareerSystem
from finance import FinancialSystem
from health import HealthSystem
from media import MediaSystem
from events import EventSystem
from fight import Fight
from strategy import StrategySystem, STRATEGIES
from generator import generate_fighter_pool
from world_sim import WorldSimulator
from news import format_news_items
import utils

init_lock = Lock()
gs = {"initialized": False}

def ensure_initialized():
    if gs.get("initialized"):
        return
    with init_lock:
        if gs.get("initialized"):
            return
        print("Initializing game world with 500 fighters...")
        weight_classes = [wc["name"] for wc in utils.WEIGHT_CLASSES]
        promotions = create_promotions(weight_classes)
        world, national, regional = promotions
        all_fighters = generate_fighter_pool(promotions, 8000)
        gs["sessions"] = {}
        gs["sessions_lock"] = Lock()
        gs["promotions"] = promotions
        gs["world"] = world
        gs["national"] = national
        gs["regional"] = regional
        gs["all_fighters"] = all_fighters
        gs["world_sim"] = WorldSimulator(promotions)
        gs["world_news"] = []
        MAX_NEWS = 200
        gs["initialized"] = True
        print("Game world ready!")

def get_or_create_session(session_id):
    sl = gs.get("sessions_lock")
    with sl:
        if session_id not in gs["sessions"]:
            gs["sessions"][session_id] = {"_created": time.time()}
        return gs["sessions"][session_id]

_world_sim_running = False
_world_sim_lock = Lock()

def run_world_sim(game_date, es):
    global _world_sim_running
    with _world_sim_lock:
        if _world_sim_running:
            return
        _world_sim_running = True
    try:
        ws = gs.get("world_sim")
        if ws and game_date:
            results = ws.simulate_month(game_date, es)
            if results:
                news_list = gs.setdefault("world_news", [])
                news_list.extend(results)
                if len(news_list) > 200:
                    news_list[:] = news_list[-200:]
    finally:
        with _world_sim_lock:
            _world_sim_running = False

def run_world_sim_async(game_date, es):
    Thread(target=run_world_sim, args=(game_date, es), daemon=True).start()

def ensure_regional_opponents(session):
    f = session.get("fighter")
    promo = session.get("current_promotion")
    if not f or not promo or promo.tier_name != "Regional":
        return
    wc = f.weight_class
    available = [opp for opp in promo.rankings.get(wc, [])
                 if opp != f and opp.nationality == f.nationality and opp.is_available()]
    if len(available) >= 5:
        return
    to_create = 8 - len(available)
    from generator import generate_single_fighter
    wc_data = utils.get_weight_class(wc)
    for i in range(to_create):
        fighter = generate_single_fighter(
            random.randint(wc_data["min"], wc_data["max"]),
            skill_mean=utils.gaussian_random(40, 8, 25, 55),
            skill_std=utils.gaussian_random(12, 3, 6, 18)
        )
        fighter.nationality = f.nationality
        fighter.home_region = f.home_region
        promo.sign_fighter(fighter)
    promo.update_rankings()

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
    promo = session.get("current_promotion")
    training = session.get("training")
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
            "injuries": [{"type": i["type"], "severity": round(i["severity"], 2)} for i in f.injuries],
            "suspension": max(0, (f.medical_suspension_end - game_date).days) if f.medical_suspension_end else 0,
            "retired": f.retired,
            "stance": f.stance,
        "signature_strike": f.get_signature_strike(),
            "career_damage": round(f.career_damage_taken, 1),
            "career_fights": f.career_total_fights,
            "ko_losses": f.career_ko_losses,
            "prime_status": "prime" if f.PRIME_START <= f.age <= f.PRIME_END else ("developing" if f.age < f.PRIME_START else "declining"),
            "peak_rank": f.peak_rank,
            "scouting_level": getattr(f, 'times_scouted', 0),
            "signature_strikes": f.signature_strikes,
        },
        "promotion": {
            "name": promo.name if promo else "Free Agent",
            "tier": promo.tier_name if promo else "None",
            "rankings": [{"name": o.name, "rank": r+1, "record": o.get_record_string(), "rating": round(o.get_overall_rating(), 1)}
                         for r, o in enumerate((promo.rankings.get(f.weight_class) or [])[:15])] if promo else [],
            "champion": (promo.champions.get(f.weight_class).name if promo.champions.get(f.weight_class) else "N/A") if promo else "N/A",
            "undisputed": promo.is_undisputed_champion(f, [gs.get("world"), gs.get("national"), gs.get("regional")]) if promo else False,
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

def _get_fight_booking_state(session):
    fb = session.get("current_fight_booking")
    if not fb:
        return None
    f = session.get("fighter")
    opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
    game_date = session.get("game_date", datetime.now())
    days_until = max(0, (fb.date - game_date).days) if fb.date else 0
    fight_week_day = None
    if 0 <= days_until <= 5:
        fight_week_events = ["Press Conference", "Open Workout", "Weigh-In", "Faceoff", "Rest Day", "Fight Night"]
        fight_week_day = fight_week_events[days_until] if days_until < 6 else None
    return {
        "opponent": {
            "name": opponent.name,
            "record": opponent.get_record_string(),
            "rank": opponent.rank,
            "archetype": opponent.archetype,
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
    from training import DRILLS as ALL_DRILLS
    available_drills = []
    if t.current_camp:
        drills = t.current_camp.available_drills
    else:
        drills = ALL_DRILLS
    for d in drills:
        gym_bonus = t.get_gym_bonus_for_drill(d.name)
        available_drills.append({
            "name": d.name, "duration": d.duration_days, "type": d.drill_type,
            "attrs": d.affected_attrs, "gym_bonus": round(gym_bonus * 100),
        })
    return {
        "in_training": t.in_training,
        "in_camp": t.current_camp is not None,
        "camp_name": t.current_camp.name if t.current_camp else None,
        "camp_type": t.current_camp.camp_type if t.current_camp else None,
        "camp_weeks": t.current_camp.duration_weeks if t.current_camp else 0,
        "camp_cost": t.current_camp.cost if t.current_camp else 0,
        "drill_name": t.current_drill.name if t.current_drill else None,
        "intensity": t.intensity,
        "days_trained": t.days_trained,
        "fatigue": round(t.fatigue * 100),
        "schedule": t.get_schedule_state(),
        "available_drills": available_drills,
        "film_study_available": t.film_study_sessions < 2,
        "recovery_active": t.recovery_active,
        "recovery_type": t.recovery_type,
    }

def _get_gym_atmosphere(session):
    f = session.get("fighter")
    if not f or not f.gym:
        return None
    gym_name = f.gym
    gym_fighters = []
    for prom in [gs.get("world"), gs.get("national"), gs.get("regional")]:
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
    return {
        "net_worth": f.net_worth,
        "agent": f.fighter.agent or "None",
        "agent_name": f.fighter.agent_name or "None",
        "gym": f.fighter.gym or "None",
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
        promotions = (gs.get("world"), gs.get("national"), gs.get("regional"))
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

def get_available_camps_data():
    camps = TrainingCamp.get_available_camps()
    result = []
    for c in camps:
        drills = []
        for d in c.available_drills:
            drills.append({"name": d.name, "duration": d.duration_days, "type": d.drill_type, "attrs": d.affected_attrs})
        result.append({"name": c.name, "type": c.camp_type, "weeks": c.duration_weeks, "cost": c.cost, "drills": drills})
    return result

def get_opponents_data(session):
    f = session.get("fighter")
    promo = session.get("current_promotion")
    if not f or not promo:
        return []
    all_promos = [gs.get("world"), gs.get("national"), gs.get("regional")]
    opps = promo.get_available_opponents(f, all_promotions=[p for p in all_promos if p and p != promo])
    result = []
    for opp, difficulty in opps:
        result.append({
            "name": opp.name,
            "record": opp.get_record_string(),
            "rank": opp.rank,
            "rating": round(opp.get_overall_rating(), 1),
            "archetype": opp.archetype,
            "age": opp.age,
            "nationality": opp.nationality,
            "height": opp.height,
            "reach": opp.reach,
            "wins": opp.wins,
            "losses": opp.losses,
            "knockouts": opp.knockouts,
            "submissions": opp.submissions,
            "win_streak": opp.win_streak,
            "loss_streak": opp.loss_streak,
            "difficulty": difficulty,
            "attributes": {k: round(v, 1) for k, v in opp.attributes.items()},
        })
    result.sort(key=lambda x: x["rank"])
    return result

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

            elif path == "/api/state":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                self.json_resp(get_state_dict(session))

            elif path == "/api/init":
                ensure_initialized()
                self.json_resp({"ready": True, "promotions": {
                    "regional": len(gs["regional"].fighters),
                    "national": len(gs["national"].fighters),
                    "world": len(gs["world"].fighters),
                }})

            elif path == "/create":
                ensure_initialized()
                name = params.get("name", [""])[0]
                if not name or name.strip() == "":
                    first, last = utils.generate_name()
                    name = f"{first} {last}"
                try:
                    age = int(params.get("age", ["25"])[0])
                except:
                    age = 25
                try:
                    wc = int(params.get("weight_class", ["3"])[0])
                except:
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
                regional = gs["regional"]
                career = CareerSystem(f)
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
                session["current_promotion"] = regional
                session["current_event"] = None
                session["current_fight_booking"] = None
                session["current_fight"] = None
                session["game_date"] = game_date
                
                self.send_response(302)
                self.send_header("Location", f"/?sid={sid}")
                self.end_headers()

            elif path == "/api/camps":
                self.json_resp({"camps": get_available_camps_data()})

            elif path == "/api/opponents":
                ensure_initialized()
                sid = params.get("sid", [""])[0]
                session = get_or_create_session(sid)
                self.json_resp({"opponents": get_opponents_data(session)})

            elif path == "/api/free_agent_offers":
                ensure_initialized()
                promos = []
                for p in gs["promotions"]:
                    if p.tier_name != "Regional":
                        continue
                    promos.append({"name": p.name, "tier": p.tier_name,
                                   "base_pay": p.base_pay, "win_bonus": p.win_bonus,
                                   "perf_bonus": p.perf_bonus,
                                   "num_fighters": len(p.fighters)})
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
                name = body.get("name", "")
                if not name or name.strip() == "":
                    first, last = utils.generate_name()
                    name = f"{first} {last}"
                age = body.get("age", 25)
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
                    wc = utils.WEIGHT_CLASSES[wc_param]
                weight = random.randint(wc["min"], wc["max"])
                sid = body.get("sid", "")
                nationality = body.get("nationality", "American")
                region = body.get("region", "California")
                trait_id = body.get("trait_id")
                personality_id = body.get("personality_id", "humble")
                stance = body.get("stance", None)
                game_date = datetime(2025, 1, 6)

                f = Fighter(name, age, weight, bg, "balanced", nationality, region, trait_id, personality_id, stance=stance, game_date=game_date)

                # Age-scaled starting stats: 18yo starts ~25% below base, 35yo starts at base+5%
                age_min = 18
                age_max = 35
                age_range = age_max - age_min
                age_pct = (age - age_min) / max(1, age_range)
                stat_mod = -15 + (age_pct * 20)  # -15 at 18, +5 at 35
                for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
                    f.attributes[attr] = utils.clamp(f.attributes[attr] + stat_mod, utils.ATTR_MIN, utils.ATTR_MAX)

                regional = gs["regional"]
                national = gs["national"]
                world = gs["world"]

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
                session["current_promotion"] = None
                session["current_event"] = None
                session["current_fight_booking"] = None
                session["current_fight"] = None
                session["game_date"] = game_date
                
                # Check if this is a form submission (not AJAX)
                if "application/x-www-form-urlencoded" in content_type:
                    # Return HTML page that loads the game
                    state_json = json.dumps(get_state_dict(session))
                    html = f'''<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>MMA Life - Game</title>
<meta http-equiv="refresh" content="0;url=/?sid={sid}">
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0a0a0f;color:#e0e0e0;padding:20px;text-align:center}}
.btn{{display:inline-block;padding:10px 20px;background:#e62400;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:16px}}
</style>
<script>
var sid = "{sid}";
var state = {state_json};
try{{localStorage.setItem("mma_state", JSON.stringify(state));localStorage.setItem("mma_sid", sid);}}catch(e){{}}
</script>
</head>
<body>
<h1>Fighter Created!</h1>
<p>Welcome to the pros, {f.name}!</p>
<p><a href="/?sid={sid}" class="btn">ENTER GAME</a></p>
</body>
</html>'''
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(html.encode())
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

                result = training.advance_day()

                game_date = session.get("game_date")
                if game_date:
                    game_date += timedelta(days=1)
                    session["game_date"] = game_date

                if f:
                    f.recover_injuries(game_date)

                if es and game_date:
                    es.advance_time(game_date)

                if game_date and game_date.day == 1:
                    if f:
                        f.months_inactive += 1
                        f.monthly_aging(game_date)
                    if finance:
                        finance.process_monthly(game_date)
                    run_world_sim_async(game_date, es)

                fight_today = False
                if fb and fb.date and game_date and game_date >= fb.date:
                    if not session.get("fight_completed"):
                        fight_today = True

                self.json_resp({
                    "success": True,
                    "state": get_state_dict(session),
                    "day_result": result,
                    "fight_today": fight_today,
                })

            elif path == "/api/start_camp":
                sid = body.get("sid", "")
                camp_idx = body.get("camp_idx", 0)
                drill_idx = body.get("drill_idx", 0)
                intensity = body.get("intensity", "moderate")
                session = get_or_create_session(sid)
                finance = session.get("finance")
                training = session.get("training")
                if not training or not finance:
                    self.json_resp({"error": "Not initialized"})
                    return
                camps = TrainingCamp.get_available_camps()
                if camp_idx >= len(camps):
                    self.json_resp({"error": "Invalid camp"})
                    return
                camp = camps[camp_idx]
                if drill_idx >= len(camp.available_drills):
                    self.json_resp({"error": "Invalid drill"})
                    return
                drill = camp.available_drills[drill_idx]
                if not finance.can_afford(camp.cost):
                    self.json_resp({"error": f"Cannot afford {camp.cost}"})
                    return
                if training.start_camp(camp, drill, intensity, finance):
                    self.json_resp({"success": True, "state": get_state_dict(session)})
                else:
                    self.json_resp({"error": "Failed to start camp"})

            elif path == "/api/start_training":
                sid = body.get("sid", "")
                drill_idx = body.get("drill_idx", 0)
                intensity = body.get("intensity", "moderate")
                session = get_or_create_session(sid)
                training = session.get("training")
                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return
                from training import DRILLS as ALL_DRILLS
                if drill_idx >= len(ALL_DRILLS):
                    self.json_resp({"error": "Invalid drill"})
                    return
                drill = ALL_DRILLS[drill_idx]
                if training.start_training(drill, intensity):
                    self.json_resp({"success": True, "state": get_state_dict(session)})
                else:
                    self.json_resp({"error": "Already training. Stop first."})

            elif path == "/api/stop_training":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                training = session.get("training")
                if training:
                    training.stop_training()
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/end_camp":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                training = session.get("training")
                if training:
                    training.end_camp()
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/book_fight":
                sid = body.get("sid", "")
                opp_name = body.get("opponent", "")
                weeks_out = body.get("weeks", 8)
                session = get_or_create_session(sid)
                f = session.get("fighter")
                promo = session.get("current_promotion")
                game_date = session.get("game_date", datetime.now())
                if not f or not promo:
                    self.json_resp({"error": "Not signed"})
                    return
                opps = promo.get_available_opponents(f)
                target = None
                for o, d in opps:
                    if o.name == opp_name:
                        target = o
                        break
                if not target:
                    for o in promo.fighters:
                        if o.name == opp_name and o.weight_class == f.weight_class:
                            target = o
                            break
                if not target:
                    self.json_resp({"error": "Opponent not found"})
                    return
                opponent = copy.deepcopy(target)
                is_title = promo.champions.get(f.weight_class) is not None and opponent.name == promo.champions[f.weight_class].name
                fight_date = game_date + timedelta(weeks=weeks_out)
                es = session.get("event_sys")
                event = es.create_event(f"Fight Night: {f.name} vs {opponent.name}", fight_date, promo)
                fb = es.book_fight(event, f, opponent, is_title_fight=is_title)
                es.generate_card(event, f, promo)
                session["current_event"] = event
                session["current_fight_booking"] = fb
                session["fight_completed"] = False
                session["career"].add_rivalry(opponent)
                self.json_resp({"success": True, "state": get_state_dict(session)})

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
                fight.strategy1.set_pre_fight_strategy(strat_id)
                ai_map = {
                    "brawler": "aggressive_striking", "counter_striker": "defensive_striking",
                    "wrestler": "wrestling_focus", "submission_artist": "submission_hunting",
                    "kickboxer": "kickboxing_focus", "boxer": "boxing_focus",
                    "muay_thai": "muay_thai_focus", "clinch_fighter": "clinch_dominance",
                    "balanced": random.choice([s["id"] for s in STRATEGIES]),
                }
                ai_s = ai_map.get(opponent.archetype, "balanced")
                if ai_s == "balanced":
                    ai_s = random.choice([s["id"] for s in STRATEGIES])
                fight.strategy2.set_pre_fight_strategy(ai_s)
                session["current_fight"] = fight
                session["fight_started"] = True
                result = fight.start_web_fight()
                print(f"FIGHT RESULT: status={result.get('status')}, events={len(result.get('events', []))}")
                if result.get('events'):
                    for i, e in enumerate(result['events'][:5]):
                        print(f"  event[{i}]: type={e.get('type')}, text={str(e.get('text',''))[:80]}")
                self.json_resp({"success": True, "fight_result": result, "opponent": opponent.name})

            elif path == "/api/fight_action":
                sid = body.get("sid", "")
                strategy = body.get("strategy")
                session = get_or_create_session(sid)
                fight = session.get("current_fight")
                if not fight:
                    self.json_resp({"error": "No active fight"})
                    return
                result = fight.submit_strategy_web(strategy)
                self.json_resp({"success": True, "fight_result": result})

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
                scouting_report = {
                    "level": "full" if scouted >= 3 else ("partial" if scouted >= 1 else "none"),
                    "sessions": scouted,
                    "opponent_archetype": opponent.archetype,
                    "opponent_background": opponent.background,
                    "opponent_attrs_visible": scouted >= 1,
                    "opponent_preferred_strategies": preferred_strats if scouted >= 3 else [],
                }
                self.json_resp({"success": True, "scouting": scouting_report})

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
                opponent = fb.fighter2 if fb.fighter1 == f else fb.fighter1
                winner = fight.winner
                won = winner == f if winner else False
                is_draw = winner is None
                method = fight.win_method or "Decision"
                fb.complete(winner, method, fight.win_round)
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
                session["fight_completed"] = True
                ensure_regional_opponents(session)
                self.json_resp({
                    "success": True, "won": won,
                    "state": get_state_dict(session),
                    "milestones": milestones,
                    "bonuses": bonuses,
                    "season_award": season_award,
                })

            elif path == "/api/sign_free_agent":
                sid = body.get("sid", "")
                tier_name = body.get("tier", "Regional")
                session = get_or_create_session(sid)
                career = session.get("career")
                f = session.get("fighter")
                game_date = session.get("game_date")
                promo = None
                for p in gs["promotions"]:
                    if p.tier_name == tier_name:
                        promo = p
                        break
                if not career or not promo or not f:
                    self.json_resp({"error": "Cannot sign"})
                    return
                career.sign_with_promotion(promo, 4, game_date)
                session["current_promotion"] = promo
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/accept_promotion":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                career = session.get("career")
                game_date = session.get("game_date")
                if not career:
                    self.json_resp({"error": "No career system"})
                    return
                promotions = (gs.get("world"), gs.get("national"), gs.get("regional"))
                offer = career.check_promotion_offer(promotions)
                if not offer:
                    self.json_resp({"error": "No promotion offer available"})
                    return
                career.sign_with_promotion(offer, 4, game_date)
                session["current_promotion"] = offer
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/advance_time":
                sid = body.get("sid", "")
                days = body.get("days", 7)
                session = get_or_create_session(sid)
                training = session.get("training")
                f = session.get("fighter")
                finance = session.get("finance")
                es = session.get("event_sys")
                fb = session.get("current_fight_booking")

                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return

                game_date = session.get("game_date")
                fight_today = False

                for _ in range(days):
                    training.advance_day()

                    if game_date:
                        game_date += timedelta(days=1)

                    if f:
                        f.recover_injuries(game_date)

                    if es and game_date:
                        es.advance_time(game_date)

                    if game_date and game_date.day == 1:
                        if f:
                            f.months_inactive += 1
                            f.monthly_aging(game_date)
                        if finance:
                            finance.process_monthly(game_date)
                        run_world_sim_async(game_date, es)

                    if fb and fb.date and game_date and game_date >= fb.date:
                        if not session.get("fight_completed"):
                            fight_today = True

                session["game_date"] = game_date

                self.json_resp({
                    "success": True,
                    "state": get_state_dict(session),
                    "fight_today": fight_today,
                })

            elif path == "/api/set_schedule":
                sid = body.get("sid", "")
                day_idx = body.get("day_idx", 0)
                drill_name = body.get("drill_name", None)
                session = get_or_create_session(sid)
                training = session.get("training")
                if not training:
                    self.json_resp({"error": "Not initialized"})
                    return
                if not training.week_started:
                    self.json_resp({"error": "Start training or a camp first to set up a schedule"})
                    return
                training.set_day_drill(day_idx, drill_name)
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/fight_offer":
                sid = body.get("sid", "")
                opp_name = body.get("opponent", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                promo = session.get("current_promotion")
                career = session.get("career")
                if not f or not promo:
                    self.json_resp({"error": "Not signed"})
                    return
                opps = promo.get_available_opponents(f)
                target = None
                for o, d in opps:
                    if o.name == opp_name:
                        target = o
                        break
                if not target:
                    self.json_resp({"error": "Opponent not found"})
                    return
                contract_pay = None
                if career and career.contract:
                    contract_pay = {
                        "base_pay": career.contract.base_pay,
                        "win_bonus": career.contract.win_bonus,
                        "total": career.contract.base_pay + career.contract.win_bonus,
                    }
                rivalry_status = None
                if career:
                    for r in career.rivalries:
                        opp_r = r.get_opponent(f)
                        if opp_r and opp_r.name == target.name:
                            rivalry_status = {"intensity": r.intensity, "fights": len(r.fights), "trilogy": r.trilogy}
                            break
                fight_history = []
                for fh in [f, target]:
                    recent = []
                    for fb_h in (session.get("current_event").fights if session.get("current_event") else []):
                        pass
                    total = fh.wins + fh.losses
                    last_5 = min(total, 5)
                    for i in range(last_5):
                        recent.append("W" if i < fh.wins else "L")
                    fight_history.append({
                        "name": fh.name,
                        "recent": recent,
                    })
                self.json_resp({
                    "success": True,
                    "offer": {
                        "opponent": {
                            "name": target.name,
                            "record": target.get_record_string(),
                            "rank": target.rank,
                            "rating": round(target.get_overall_rating(), 1),
                            "archetype": target.archetype,
                            "height": target.height,
                            "reach": target.reach,
                            "age": target.age,
                            "nationality": target.nationality,
                            "win_streak": target.win_streak,
                            "loss_streak": target.loss_streak,
                            "knockouts": target.knockouts,
                            "submissions": target.submissions,
                            "attributes": {k: round(v, 1) for k, v in target.attributes.items()},
                        },
                        "contract_pay": contract_pay,
                        "rivalry": rivalry_status,
                        "fight_history": fight_history,
                    }
                })

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
                self.json_resp({"success": success, "state": get_state_dict(session)})

            elif path == "/api/leave_gym":
                sid = body.get("sid", "")
                session = get_or_create_session(sid)
                f = session.get("fighter")
                if f:
                    f.gym = None
                self.json_resp({"success": True, "state": get_state_dict(session)})

            elif path == "/api/balance_test":
                """Run multiple simulated fights and return aggregate stats."""
                from fight import Fight
                from generator import generate_single_fighter
                sid = body.get("sid", "")
                iterations = body.get("iterations", 100)
                session = get_or_create_session(sid)
                f = session.get("fighter")
                if not f:
                    self.json_resp({"error": "No fighter in session"})
                    return
                wc_data = utils.get_weight_class(f.weight_class)
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
                    a_strat = random.choice(strats)
                    d_strat = random.choice(strats)
                    fight = Fight(f, opponent, rounds=3, is_title_fight=False)
                    fight.strategy1.set_pre_fight_strategy(a_strat)
                    fight.strategy2.set_pre_fight_strategy(d_strat)
                    for event in fight.simulate_fight_gen():
                        if event["type"] == "complete":
                            break
                    if fight.winner == f:
                        results["f1_wins"] += 1
                    elif fight.winner == opponent:
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
                from fight import Fight
                from generator import generate_single_fighter
                iterations = body.get("iterations", 100)
                f1_mean = body.get("f1_mean", 50)
                f1_std = body.get("f1_std", 10)
                f2_mean = body.get("f2_mean", 50)
                f2_std = body.get("f2_std", 10)
                wc_idx = body.get("weight_class", 3)
                wc_data = utils.WEIGHT_CLASSES[wc_idx]

                detailed = body.get("detailed", False)
                results = {"f1_wins": 0, "f2_wins": 0, "draws": 0,
                           "ko_tko_pct": 0, "sub_pct": 0, "dec_pct": 0,
                           "avg_rounds": 0, "by_method": {}}
                round_data = []

                for i in range(iterations):
                    f1 = generate_single_fighter(
                        random.randint(wc_data["min"], wc_data["max"]),
                        skill_mean=utils.gaussian_random(f1_mean, f1_std, 20, 80),
                        skill_std=utils.gaussian_random(12, 3, 5, 20)
                    )
                    f2 = generate_single_fighter(
                        random.randint(wc_data["min"], wc_data["max"]),
                        skill_mean=utils.gaussian_random(f2_mean, f2_std, 20, 80),
                        skill_std=utils.gaussian_random(12, 3, 5, 20)
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
    
    def session_cleanup():
        while True:
            time.sleep(300)
            sl = gs.get("sessions_lock")
            if sl:
                with sl:
                    stale = [sid for sid, s in gs["sessions"].items()
                             if time.time() - s.get("_created", 0) > 7200]
                    for sid in stale:
                        del gs["sessions"][sid]
                    if stale:
                        print(f"Cleaned {len(stale)} stale sessions")
    
    Thread(target=session_cleanup, daemon=True).start()
    
    print(f"Server starting on port {PORT}...")
    print("Initializing game world...")
    ensure_initialized()
    print("Game world ready!")
    print(f"Open http://localhost:{PORT} in your browser" if PORT == 8000 else f"Server running on {HOST}:{PORT}")
    server = ThreadedHTTPServer((HOST, PORT), Handler)
    server.allow_reuse_address = True
    server.serve_forever()
