#!/usr/bin/env python3
"""Fixed player journey trace with proper handling."""
import json, time, urllib.request, urllib.parse, sys

BASE = "http://localhost:8000"
SID = "audit-2"

failures = []
HAS_ERROR = False

def api(method, path, data=None, timeout=10):
    url = f"{BASE}{path}"
    if method == "GET" and data:
        url += "?" + urllib.parse.urlencode(data)
        data = None
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        txt = e.read().decode()[:300]
        return {"_http_error": e.code, "_body": txt}
    except urllib.error.URLError as e:
        return {"_timeout": True, "_error": str(e.reason)}
    except Exception as e:
        return {"_exception": str(e)}

def fail(step, desc, response, expected):
    global HAS_ERROR
    HAS_ERROR = True
    msg = f"\n### FAIL at {step}\nCall: {desc}\nResponse: {json.dumps(response, indent=2)[:400]}\nExpected: {expected}\n"
    failures.append(msg)
    print(msg)

def ok(step, msg):
    print(f"  [{step}] OK: {msg}")

print("=" * 60)
print("PLAYER JOURNEY TRACE v2")
print("=" * 60)

# Step 1: Create Fighter
print("\n--- Step 1: Create Fighter ---")
r = api("POST", "/api/create_fighter", {
    "sid": SID, "name": "Flow Tester", "age": 25,
    "weight_class": 3, "nationality": "American", "background": "mma"
})
if r.get("success") != True:
    fail("Step 1", "POST /api/create_fighter", r, "success=True")
else:
    ok("Step 1", f"Created fighter, SID={r.get('sid')}")
SID = r.get("sid", SID)

# Step 2: Get State — check subsystems exist
print("\n--- Step 2: Get State ---")
r = api("GET", "/api/state", {"sid": SID})
f = r.get("fighter")
if not f:
    fail("Step 2", "GET /api/state", r, "non-null fighter")
else:
    ok("Step 2", f"Fighter: {f['name']}, Record: {f['record']}, Age: {f['age']}")
missing = []
for key in ["training", "career", "finance", "health", "media"]:
    if r.get(key) is None: missing.append(key)
if missing:
    fail("Step 2", "GET /api/state", r, f"subsystems present, missing: {missing}")
else:
    ok("Step 2", "All subsystems (training, career, finance, health, media) present")

promo_offer = None
if r.get("career") and r["career"].get("promotion_offer"):
    promo_offer = r["career"]["promotion_offer"]
    ok("Step 2", f"Promotion offer exists: {promo_offer}")

# Step 3: Accept Promotion / Sign
print("\n--- Step 3: Sign with Promotion ---")
if promo_offer:
    r = api("POST", "/api/accept_promotion", {"sid": SID})
    if r.get("success"):
        pn = r.get("state", {}).get("promotion", {}).get("name", "?")
        ok("Step 3", f"Accepted promotion: {pn}")
    else:
        fail("Step 3", "POST /api/accept_promotion", r, "success=True")
else:
    r = api("POST", "/api/sign_free_agent", {"sid": SID})
    if r.get("success"):
        pn = r.get("state", {}).get("promotion", {}).get("name", "?")
        ok("Step 3", f"Signed as free agent to: {pn}")
    else:
        fail("Step 3", "POST /api/sign_free_agent", r, "success=True")

# Step 4: Get Fight Offers
print("\n--- Step 4: Get Fight Offers ---")
r = api("GET", "/api/fight_offers", {"sid": SID})
offers = r.get("offers", [])
if not offers:
    # Advance days until offers appear
    for day in range(1, 31):
        api("POST", "/api/advance_day", {"sid": SID})
        r = api("GET", "/api/fight_offers", {"sid": SID})
        if r.get("offers"):
            offers = r["offers"]
            ok("Step 4", f"Offers appeared after {day} days")
            break
if not offers:
    fail("Step 4", "GET /api/fight_offers", r, "at least 1 offer")
else:
    for o in offers:
        print(f"    {o['opponent']['name']} ({o['opponent']['record']}) risk={o.get('risk')}")
opponent_name = offers[0]["opponent"]["name"]
ok("Step 4", f"Selected: {opponent_name}")

# Step 5: Book Fight
print("\n--- Step 5: Book Fight ---")
r = api("POST", "/api/book_fight", {"sid": SID, "opponent": opponent_name, "weeks": 8})
if r.get("success"):
    ok("Step 5", f"Fight booked. has_fight={r.get('state', {}).get('has_fight')}")
    b = r.get("state", {}).get("fight_booking", {})
    days_until = b.get("days_until", "?")
    is_title = b.get("is_title", False)
    opp = b.get("opponent", {})
    print(f"    Days until: {days_until}, Title: {is_title}, Opponent: {opp.get('name')} ({opp.get('record')})")
else:
    fail("Step 5", "POST /api/book_fight", r, "success=True")

# Step 6: Advance to fight day (use advance_time for bulk + day-by-day for fight week)
print("\n--- Step 6: Advance to Fight ---")
r = api("GET", "/api/state", {"sid": SID})
days_until = r.get("fight_booking", {}).get("days_until", 0)
print(f"  Days until fight: {days_until}")

# Bulk advance to 6 days before
bulk_days = max(0, days_until - 6)
if bulk_days > 0:
    r = api("POST", "/api/advance_time", {"sid": SID, "days": bulk_days})
    if r.get("success"):
        ok("Step 6", f"Bulk advanced {bulk_days} days")
    else:
        # fall back to individual advance_day
        for _ in range(bulk_days):
            r = api("POST", "/api/advance_day", {"sid": SID})
            if not r.get("success"):
                break

# Fight week — advance day by day
expected_events = ["press_conference", "open_workout", "weigh_in", "faceoff", "rest_day"]
action_map = {
    "press_conference": lambda: api("POST", "/api/press_conference", {"sid": SID, "choice": "respectful"}),
    "open_workout": lambda: api("POST", "/api/open_workout", {"sid": SID, "choice": "technical"}),
    "weigh_in": lambda: api("POST", "/api/cut_weight", {"sid": SID, "intensity": "standard"}),
    "faceoff": lambda: api("POST", "/api/faceoff", {"sid": SID, "choice": "calm"}),
    "rest_day": lambda: api("POST", "/api/rest_day", {"sid": SID, "choice": "massage"}),
}

fight_reached = False
seen_events = []
for adv in range(1, 15):
    r = api("POST", "/api/advance_day", {"sid": SID})
    if r.get("fight_today"):
        fight_reached = True
        ok("Step 6", f"Fight day reached after {adv} advances in fight week")
        break
    day_result = r.get("day_result", {})
    fwe = day_result.get("fight_week_event")
    if fwe:
        ev = fwe.get("event")
        seen_events.append(ev)
        print(f"    Advance {adv}: event={ev} - {fwe.get('text', '')[:60]}")
        # Verify event ordering
        expected_idx = len(seen_events) - 1
        if expected_idx < len(expected_events):
            if ev != expected_events[expected_idx]:
                fail("Step 6", f"advance_day #{adv}", r, f"event '{expected_events[expected_idx]}', got '{ev}'")
        # Perform the action
        if ev in action_map:
            ar = action_map[ev]()
            if ar.get("success"):
                ok("Step 6", f"{ev} action completed")

if not fight_reached:
    fail("Step 6", "POST /api/advance_day x15", r, "fight_today=True")

# Step 7: Start Fight
print("\n--- Step 7: Start Fight ---")
r = api("POST", "/api/start_fight", {"sid": SID, "strategy": "counter_striker"})
if r.get("success") and r.get("fight_streaming"):
    ok("Step 7", f"Fight started! Streaming: {r['fight_streaming']}, Opponent: {r.get('opponent')}")
else:
    fail("Step 7", "POST /api/start_fight", r, "success=True, fight_streaming=True")

# Step 8+9: Poll events, submit strategy when prompted
print("\n--- Step 8+9: Fight Loop ---")
events = []
done = False
total_polls = 0
while total_polls < 200:
    r = api("POST", "/api/fight_events", {"sid": SID, "from": len(events)})
    total_polls += 1
    if not r.get("success"):
        time.sleep(0.1)
        continue
    new_ev = r.get("events", [])
    for ev in new_ev:
        events.append(ev)
        etype = ev.get("type", "?")
        text = ev.get("text", "")[:70]
        print(f"    [{len(events)}] {etype}: {text}")
    done = r.get("done", False)
    waiting = r.get("waiting", False)
    if waiting:
        ok("Step 8", f"Strategy prompt at event {len(events)}")
        ar = api("POST", "/api/fight_action", {"sid": SID, "strategy": "balanced"})
        if ar.get("success"):
            ok("Step 9", "Strategy submitted")
        else:
            fail("Step 9", "POST /api/fight_action", ar, "success=True")
    if done:
        ok("Step 8", f"Fight done after {total_polls} polls, {len(events)} events")
        break
    if not waiting:
        time.sleep(0.15)

if not done:
    fail("Step 8", "POST /api/fight_events x200", r, "done=True")

# Step 10: Complete Fight
print("\n--- Step 10: Complete Fight ---")
r = api("POST", "/api/complete_fight", {"sid": SID}, timeout=30)
if r.get("success"):
    ok("Step 10", f"Fight completed! Won={r.get('won')}, Method={r.get('fight_details', {}).get('method')}, Round={r.get('fight_details', {}).get('round')}")
    if r.get("milestones"):
        print(f"    Milestones: {r['milestones']}")
else:
    fail("Step 10", "POST /api/complete_fight", r, "success=True")
    # Check what's in the session
    print("\n  Diagnosing...")
    s = api("GET", "/api/state", {"sid": SID})
    fs = api("POST", "/api/fight_events", {"sid": SID, "from": 0})
    print(f"  fight_events response: success={fs.get('success')}, done={fs.get('done')}, waiting={fs.get('waiting')}")
    print(f"  State has_fight: {s.get('has_fight')}")
    print(f"  fight_booking: {json.dumps(s.get('fight_booking'))[:200] if s.get('fight_booking') else 'None'}")
    print(f"  fight_state: {json.dumps(s.get('fight_state'))[:200] if s.get('fight_state') else 'None'}")

# Final state
print("\n--- Final State ---")
r = api("GET", "/api/state", {"sid": SID})
f = r.get("fighter")
if f:
    ok("Final", f"Fighter: {f['name']}, Record: {f['record']}, Rating: {f['rating']}, Rank: {f['rank']}, Net Worth: {f.get('net_worth')}")
else:
    fail("Final", "GET /api/state", r, "fighter present")

print("\n" + "=" * 60)
print("RESULTS")
print("=" * 60)
if failures:
    print(f"\n{len(failures)} FAILURE(S):")
    for f in failures:
        print(f)
    n = len(failures)
    if n >= 3:
        print("OVERALL FLOW: BROKEN")
    elif n >= 1:
        print("OVERALL FLOW: BUMPY")
else:
    print("\nALL STEPS PASSED")
    print("OVERALL FLOW: SMOOTH")
print("=" * 60)
