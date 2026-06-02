#!/usr/bin/env python3
"""Full player journey trace for MMA Life Simulator HTTP API."""
import json
import time
import urllib.request
import urllib.parse

BASE = "http://localhost:8000"
SID = "audit-1"

failures = []

def api(method, path, data=None):
    url = f"{BASE}{path}"
    if method == "GET" and data:
        url += "?" + urllib.parse.urlencode(data)
        data = None
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:200]}
    except Exception as e:
        return {"_exception": str(e)}

def log_fail(step, call, response, expected):
    msg = f"\n### FAIL at {step}\nCall: {call}\nResponse: {json.dumps(response, indent=2)[:300]}\nExpected: {expected}\n"
    failures.append(msg)
    print(msg)

def check(step, resp, key, expected_val, call_desc):
    if isinstance(resp, dict) and resp.get("_http_error"):
        log_fail(step, call_desc, resp, f"HTTP error {resp['_http_error']}, expected {key}={expected_val}")
        return False
    actual = resp.get(key)
    if actual != expected_val:
        log_fail(step, call_desc, resp, f"{key}={expected_val}, got {actual}")
        return False
    return True

print("=" * 60)
print("PLAYER JOURNEY TRACE: MMA Life Simulator")
print("=" * 60)

# Step 1: Create Fighter
print("\n--- Step 1: Create Fighter ---")
r = api("POST", "/api/create_fighter", {
    "sid": SID, "name": "Flow Tester", "age": 25,
    "weight_class": 3, "nationality": "American", "background": "mma"
})
if not check("Step 1", r, "success", True,
             'POST /api/create_fighter sid=audit-1 name="Flow Tester" ...'):
    # Even if success missing, try to get sid
    pass
print(f"Response keys: {list(r.keys())}")
print(f"Success: {r.get('success')}, SID: {r.get('sid')}")
actual_sid = r.get("sid", SID)
if actual_sid != SID:
    print(f"NOTE: SID changed from '{SID}' to '{actual_sid}'")
    SID = actual_sid

# Step 2: Get State
print("\n--- Step 2: Get State ---")
r = api("GET", "/api/state", {"sid": SID})
check("Step 2", r, "fighter", None, "GET /api/state")  # might be nested
if r.get("fighter"):
    print("Fighter exists:", r["fighter"]["name"])
else:
    log_fail("Step 2", "GET /api/state", r, "fighter object in response")
# Check sub-systems
for key in ["training", "career", "promotion", "finance", "health", "media"]:
    if r.get(key) is not None:
        print(f"  {key}: OK")
    else:
        print(f"  {key}: MISSING")

promo_offer = None
if r.get("career") and r["career"].get("promotion_offer"):
    promo_offer = r["career"]["promotion_offer"]
    print(f"  Promotion offer: {promo_offer}")

# Step 3: Accept Promotion
print("\n--- Step 3: Accept Promotion ---")
if promo_offer:
    r = api("POST", "/api/accept_promotion", {"sid": SID})
    check("Step 3", r, "success", True,
          f"POST /api/accept_promotion sid={SID}")
    print(f"Accepted promotion. Response keys: {list(r.keys())}")
    if r.get("state"):
        print(f"  Current promotion: {r['state'].get('promotion', {}).get('name')}")
else:
    # Maybe the fighter was auto-signed in create_fighter
    # Check if promotion exists in state
    r2 = api("GET", "/api/state", {"sid": SID})
    if r2.get("promotion") and r2["promotion"].get("name"):
        print(f"Already signed with: {r2['promotion']['name']}")
    else:
        # Try signing with a regional promotion
        r3 = api("POST", "/api/sign_free_agent", {"sid": SID})
        if r3.get("success"):
            print("Signed as free agent to regional promotion")
        else:
            log_fail("Step 3", "POST /api/sign_free_agent", r3, "success=True after accepting promotion offer")

# Step 4: Get Fight Offers
print("\n--- Step 4: Get Fight Offers ---")
r = api("GET", "/api/fight_offers", {"sid": SID})
offers = r.get("offers", [])
print(f"Fight offers: {len(offers)}")
if offers:
    for o in offers:
        print(f"  Opponent: {o['opponent']['name']}, Record: {o['opponent']['record']}, Risk: {o.get('risk')}")
else:
    print("No offers available. Advancing days...")
    # Advance days until offers appear
    for day in range(1, 31):
        r2 = api("POST", "/api/advance_day", {"sid": SID})
        if not r2.get("success"):
            print(f"  Day {day}: advance failed - {r2}")
            break
        r3 = api("GET", "/api/fight_offers", {"sid": SID})
        if r3.get("offers"):
            offers = r3["offers"]
            print(f"  Offers appeared after {day} days!")
            for o in offers:
                print(f"    Opponent: {o['opponent']['name']}, Risk: {o.get('risk')}")
            break
    else:
        log_fail("Step 4", "GET /api/fight_offers after 30 days", r3, "at least 1 fight offer")

if not offers:
    log_fail("Step 4", "GET /api/fight_offers", r, "at least 1 fight offer. Response: " + json.dumps(r)[:200])
    print("Cannot continue without offers. Exiting.")
    print_report()
    exit(1)

opponent_name = offers[0]["opponent"]["name"]
print(f"Selected opponent: {opponent_name}")

# Step 5: Book Fight
print("\n--- Step 5: Book Fight ---")
r = api("POST", "/api/accept_offer", {"sid": SID, "opponent": opponent_name, "weeks": 8})
if not check("Step 5", r, "success", True,
             f'POST /api/accept_offer sid={SID} opponent={opponent_name} weeks=8'):
    # Try book_fight as alternative
    r = api("POST", "/api/book_fight", {"sid": SID, "opponent": opponent_name, "weeks": 8})
    check("Step 5b", r, "success", True,
          f'POST /api/book_fight sid={SID} opponent={opponent_name} weeks=8')
print(f"Booking response state.has_fight: {r.get('state', {}).get('has_fight')}")

# Check booking details
r_state = api("GET", "/api/state", {"sid": SID})
booking = r_state.get("fight_booking")
if booking:
    days_until = booking.get("days_until")
    print(f"Fight booked! Days until fight: {days_until}")
    print(f"  Opponent: {booking.get('opponent', {}).get('name')}")
    print(f"  Is title: {booking.get('is_title')}")
else:
    log_fail("Step 5", "GET /api/state", r_state, "fight_booking to exist after booking")

# Step 6: Fight Week - Advance day by day
print("\n--- Step 6: Fight Week ---")
FIGHT_WEEK_MAP = {
    5: ("press_conference", lambda: api("POST", "/api/press_conference", {"sid": SID, "choice": "respectful"})),
    4: ("open_workout", lambda: api("POST", "/api/open_workout", {"sid": SID, "choice": "technical"})),
    3: ("weigh_in", lambda: api("POST", "/api/cut_weight", {"sid": SID, "intensity": "standard"})),
    2: ("faceoff", lambda: api("POST", "/api/faceoff", {"sid": SID, "choice": "calm"})),
    1: ("rest_day", lambda: api("POST", "/api/rest_day", {"sid": SID, "choice": "massage"})),
}

# Get current days_until
r_state = api("GET", "/api/state", {"sid": SID})
days_until = r_state.get("fight_booking", {}).get("days_until", 0) if r_state.get("fight_booking") else 0
print(f"Starting fight week from days_until={days_until}")

fight_reached = False
for day_step in range(1, 20):  # safety limit
    # Get current state to check days_until
    r_state = api("GET", "/api/state", {"sid": SID})
    booking = r_state.get("fight_booking")
    if not booking:
        print(f"  No booking on advance #{day_step} - fight already complete or canceled")
        break
    days_until = booking.get("days_until", 0)
    fight_week_day = booking.get("fight_week_day")
    
    print(f"\n  Advance #{day_step}: days_until={days_until}, fight_week_day={fight_week_day}")
    
    # Advance day
    r = api("POST", "/api/advance_day", {"sid": SID})
    if not r.get("success") and not r.get("fight_today"):
        print(f"  Advance_day response: {r}")
        # Might be fight week blocking
        day_result = r.get("day_result", {})
        fwe = day_result.get("fight_week_event", {})
        if fwe:
            print(f"  Fight week event triggered: {fwe.get('event')} - {fwe.get('text', '')[:80]}")
        else:
            print(f"  Unexpected response: {json.dumps(r)[:200]}")
    
    day_result = r.get("day_result", {})
    fwe = day_result.get("fight_week_event", {})
    
    # Log what happened
    if fwe:
        print(f"  Event: {fwe.get('event')} - {fwe.get('text', '')[:80]}")
    
    if r.get("fight_today"):
        fight_reached = True
        print("  *** FIGHT DAY! ***")
        break
else:
    if not fight_reached:
        log_fail("Step 6", "POST /api/advance_day x20", r, "fight_today=True within 20 days")

if not fight_reached:
    print("WARNING: Fight day was not reached via advance_day. Checking state...")
    r_state = api("GET", "/api/state", {"sid": SID})
    if r_state.get("fight_booking"):
        print(f"  Still have booking: {json.dumps(r_state['fight_booking'])[:200]}")
    if r_state.get("has_fight"):
        print("  has_fight=True - might need more days")
        # Try more advances
        for day_step in range(20, 60):
            r = api("POST", "/api/advance_day", {"sid": SID})
            if r.get("fight_today"):
                fight_reached = True
                print(f"  FIGHT DAY reached after {day_step} total advances!")
                break
        if not fight_reached:
            log_fail("Step 6", "POST /api/advance_day x60", r, "fight_today=True")

# Step 7: Start Fight
print("\n--- Step 7: Start Fight ---")
r = api("POST", "/api/start_fight", {"sid": SID, "strategy": "counter_striker"})
if not check("Step 7", r, "success", True,
             f"POST /api/start_fight sid={SID} strategy=counter_striker"):
    print(f"start_fight error: {r}")
    # Try to check state
    r_state = api("GET", "/api/state", {"sid": SID})
    print(f"Current state keys: {list(r_state.keys())}")
    if r_state.get("error"):
        print(f"State error: {r_state['error']}")
print(f"Fight streaming: {r.get('fight_streaming')}, Opponent: {r.get('opponent')}")

# Step 8: Poll Fight Events
print("\n--- Step 8: Poll Fight Events ---")
events = []
done = False
waiting = False
poll_count = 0
while not done and poll_count < 60:
    r = api("POST", "/api/fight_events", {"sid": SID, "from": len(events)})
    if r.get("success"):
        new_events = r.get("events", [])
        if new_events:
            events.extend(new_events)
            for ev in new_events:
                etype = ev.get("type", "unknown")
                text = ev.get("text", ev.get("message", ""))[:60]
                print(f"  Event: {etype} - {text}")
        done = r.get("done", False)
        waiting = r.get("waiting", False)
        if waiting:
            print("  --> Waiting for player input (strategy_prompt)")
    else:
        print(f"  Poll error: {r}")
    poll_count += 1
    if not done and not waiting:
        time.sleep(0.2)

if not done and poll_count >= 60:
    log_fail("Step 8", "POST /api/fight_events x60", r, "done=True within 60 polls")

# Step 9: Submit Strategy (if prompted)
print("\n--- Step 9: Submit Strategy ---")
if waiting:
    r = api("POST", "/api/fight_action", {"sid": SID, "strategy": "balanced"})
    if check("Step 9", r, "success", True,
             "POST /api/fight_action sid=audit-1 strategy=balanced"):
        print("Strategy submitted!")
    # Continue polling until done
    while not done and poll_count < 120:
        r = api("POST", "/api/fight_events", {"sid": SID, "from": len(events)})
        if r.get("success"):
            new_events = r.get("events", [])
            if new_events:
                events.extend(new_events)
                for ev in new_events:
                    etype = ev.get("type", "unknown")
                    text = ev.get("text", ev.get("message", ""))[:60]
                    print(f"  Event after strategy: {etype} - {text}")
            done = r.get("done", False)
            waiting = r.get("waiting", False)
            if waiting:
                # Another strategy prompt
                r2 = api("POST", "/api/fight_action", {"sid": SID, "strategy": "balanced"})
                if not r2.get("success"):
                    log_fail("Step 9b", "POST /api/fight_action", r2, "success=True for second strategy")
                print("  Additional strategy submitted")
        poll_count += 1
        if not done and not waiting:
            time.sleep(0.2)
else:
    print("No strategy prompt needed (fight may have completed without player input)")

# Step 10: Complete Fight
print("\n--- Step 10: Complete Fight ---")
r = api("POST", "/api/complete_fight", {"sid": SID})
if not check("Step 10", r, "success", True,
             "POST /api/complete_fight sid=audit-1"):
    print(f"complete_fight error: {r}")
else:
    print(f"Fight result: {'WON' if r.get('won') else 'LOST'} (or draw)")
    if r.get("fight_details"):
        fd = r["fight_details"]
        print(f"  Method: {fd.get('method')}, Round: {fd.get('round')}")
    if r.get("milestones"):
        print(f"  Milestones: {r['milestones']}")
    if r.get("season_award"):
        print(f"  Season award: {r['season_award']}")
    print("Fight completed successfully!")

# Final State Check
print("\n--- Final State ---")
r = api("GET", "/api/state", {"sid": SID})
if r.get("fighter"):
    f = r["fighter"]
    print(f"Fighter: {f['name']}, Record: {f['record']}, Age: {f['age']}")
    print(f"  Wins: {f['wins']}, Losses: {f['losses']}, Draws: {f['draws']}")
    print(f"  Rating: {f['rating']}, Rank: {f['rank']}")
    print(f"  Net worth: {f.get('net_worth')}")
else:
    log_fail("Final", "GET /api/state", r, "fighter object")

# Summary
print("\n" + "=" * 60)
print("JOURNEY TRACE RESULTS")
print("=" * 60)
if failures:
    print(f"\nFAILURES: {len(failures)}")
    for f in failures:
        print(f)
    print("OVERALL FLOW: BROKEN" if len(failures) >= 3 else "OVERALL FLOW: BUMPY")
else:
    print("\nALL 10 STEPS PASSED WITHOUT ERRORS")
    print("OVERALL FLOW: SMOOTH")
print("=" * 60)
