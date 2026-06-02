#!/usr/bin/env python3
"""Diagnose winner identity bug with longer timeouts and reference checking."""
import json, time, urllib.request, urllib.parse, sys

BASE = "http://localhost:8000"
SID = "diag-2"
TIMEOUT = 60

def api(method, path, data=None, timeout=TIMEOUT):
    url = f"{BASE}{path}"
    if method == "GET" and data:
        url += "?" + urllib.parse.urlencode(data)
        data = None
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if data: req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"_error": str(e)}

# Create
print("Creating fighter...")
r = api("POST", "/api/create_fighter", {"sid": SID, "name": "Diag Tester", "age": 25, "weight_class": 3, "nationality": "American", "background": "mma"})
sid = r.get("sid", SID)
print(f"  SID={sid}, success={r.get('success')}")

# Sign
print("Signing...")
r = api("POST", "/api/sign_free_agent", {"sid": sid})
print(f"  success={r.get('success')}, promo={r.get('state',{}).get('promotion',{}).get('name')}")

# Offers
print("Offers...")
r = api("GET", "/api/fight_offers", {"sid": sid})
offers = r.get("offers", [])
opp = offers[0]["opponent"]["name"] if offers else None
print(f"  Offers: {len(offers)}, selected: {opp}")

# Book
print("Booking...")
r = api("POST", "/api/book_fight", {"sid": sid, "opponent": opp, "weeks": 8})
print(f"  success={r.get('success')}, days_until={r.get('state',{}).get('fight_booking',{}).get('days_until')}")

# Bulk advance
print("Advancing...")
r = api("POST", "/api/advance_time", {"sid": sid, "days": 50})

# Fight week day-by-day
fight_reached = False
for i in range(10):
    r = api("POST", "/api/advance_day", {"sid": sid})
    if r.get("fight_today"):
        fight_reached = True
        print(f"  Fight day! (advance {i+1})")
        break
    fwe = r.get("day_result", {}).get("fight_week_event", {})
    if fwe:
        ev = fwe.get("event")
        txt = fwe.get("text", "")[:60]
        print(f"  Advance {i+1}: {ev} - {txt}")
        actions = {"press_conference": "respectful", "open_workout": "technical", "weigh_in": "standard", "faceoff": "calm", "rest_day": "massage"}
        if ev == "weigh_in":
            ar = api("POST", "/api/cut_weight", {"sid": sid, "intensity": "standard"})
            print(f"    weigh_in: passed={ar.get('passed')}")
        elif ev == "press_conference":
            ar = api("POST", "/api/press_conference", {"sid": sid, "choice": "respectful"})
        elif ev == "open_workout":
            ar = api("POST", "/api/open_workout", {"sid": sid, "choice": "technical"})
        elif ev == "faceoff":
            ar = api("POST", "/api/faceoff", {"sid": sid, "choice": "calm"})
        elif ev == "rest_day":
            ar = api("POST", "/api/rest_day", {"sid": sid, "choice": "massage"})

if not fight_reached:
    print("  ERROR: fight day not reached")

# Start fight
print("\nStarting fight...")
r = api("POST", "/api/start_fight", {"sid": sid, "strategy": "counter_striker"})
print(f"  success={r.get('success')}, streaming={r.get('fight_streaming')}")

# Poll to completion
events = []
strat_count = 0
for poll in range(200):
    r = api("POST", "/api/fight_events", {"sid": sid, "from": len(events)})
    if r.get("success"):
        new = r.get("events", [])
        for ev in new:
            events.append(ev)
            if ev.get("type") in ("knockout", "submission", "decision", "complete"):
                print(f"  [{len(events)}] {ev.get('type')}: {ev.get('text','')[:90]}")
        if r.get("done"):
            print(f"  Fight done! ({len(events)} events)")
            break
        if r.get("waiting"):
            strat_count += 1
            api("POST", "/api/fight_action", {"sid": sid, "strategy": "balanced"})
            print(f"  Strategy #{strat_count} submitted")
    time.sleep(0.1)

# Check object identity before complete_fight
print("\n=== Pre-complete_fight diagnosis ===")
# Use run_code_unsafe via a diagnostic approach: store refs in the state
s = api("GET", "/api/state", {"sid": sid})
fs = s.get("fight_state", {})
print(f"Fight state: winner={fs.get('winner')}, method={fs.get('win_method')}")

# Complete fight
print("\nCompleting fight...")
r = api("POST", "/api/complete_fight", {"sid": sid}, timeout=30)
print(f"success={r.get('success')}, won={r.get('won')}")
print(f"method={r.get('fight_details',{}).get('method')}, round={r.get('fight_details',{}).get('round')}")
print(f"raw keys: {json.dumps({k: v for k, v in r.items() if k != 'state'}, default=str)[:300]}")

# Final
s = api("GET", "/api/state", {"sid": sid})
f = s.get("fighter", {})
print(f"\nFinal: {f.get('record')} (W:{f.get('wins')} L:{f.get('losses')} D:{f.get('draws')}) Rating:{f.get('rating')}")
