#!/usr/bin/env python3
"""Minimal script: create fighter, book fight, start fight, check winner identity."""
import json, time, urllib.request, urllib.parse, sys

BASE = "http://localhost:8000"
SID = "diag-1"

def api(method, path, data=None, timeout=10):
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

# Step 1: Create fighter
print("Creating fighter...")
r = api("POST", "/api/create_fighter", {"sid": SID, "name": "Diag Tester", "age": 25, "weight_class": 3, "nationality": "American", "background": "mma"})
sid = r.get("sid", SID)
print(f"SID={sid}, fighter created")

# Step 2: Sign free agent
print("Signing...")
r = api("POST", "/api/sign_free_agent", {"sid": sid})
print(f"  success={r.get('success')}")

# Step 3: Get offers
print("Getting offers...")
r = api("GET", "/api/fight_offers", {"sid": sid})
offers = r.get("offers", [])
opp = offers[0]["opponent"]["name"] if offers else None
print(f"  Offers: {len(offers)}, selected: {opp}")

# Step 4: Book fight
print("Booking fight...")
r = api("POST", "/api/book_fight", {"sid": sid, "opponent": opp, "weeks": 8})
print(f"  success={r.get('success')}, fight_booking={r.get('state',{}).get('fight_booking',{}).get('opponent',{}).get('name')}")

# Step 5: Bulk advance to fight day
r = api("POST", "/api/advance_time", {"sid": sid, "days": 55})
print(f"  Bulk advance: success={r.get('success')}, fight_today={r.get('fight_today')}")

# Step 6: Last advance day
r = api("POST", "/api/advance_day", {"sid": sid})
print(f"  Final advance: fight_today={r.get('fight_today')}")

if not r.get("fight_today"):
    r = api("POST", "/api/advance_day", {"sid": sid})
    print(f"  Extra advance: fight_today={r.get('fight_today')}")

# Step 7: Start fight
print("Starting fight...")
r = api("POST", "/api/start_fight", {"sid": sid, "strategy": "counter_striker"})
print(f"  success={r.get('success')}, streaming={r.get('fight_streaming')}")

# Step 8: Poll fight to completion
events = []
for _ in range(150):
    r = api("POST", "/api/fight_events", {"sid": sid, "from": len(events)})
    if r.get("success"):
        new = r.get("events", [])
        for ev in new:
            events.append(ev)
            if ev.get("type") in ("knockout", "submission", "decision", "complete"):
                print(f"  [{len(events)}] {ev.get('type')}: {ev.get('text','')[:80]}")
        if r.get("done"):
            print(f"  Fight done! Total events: {len(events)}")
            break
        if r.get("waiting"):
            print(f"  Strategy prompt at event {len(events)}, submitting...")
            api("POST", "/api/fight_action", {"sid": sid, "strategy": "balanced"})
    time.sleep(0.1)

# Step 9: DIAGNOSE — check winner identity BEFORE complete_fight
print("\n=== DIAGNOSIS ===")

# Get session data via state to see what's happening
s = api("GET", "/api/state", {"sid": sid})
print(f"State record: {s.get('fighter', {}).get('record')}")

# Check fight_state
fs = s.get("fight_state")
if fs:
    print(f"Fight state: winner={fs.get('winner')}, method={fs.get('win_method')}")
else:
    print("No fight_state in state response")

# Direct fight_events check
r = api("POST", "/api/fight_events", {"sid": sid, "from": 0})
print(f"Fight stream: done={r.get('done')}, waiting={r.get('waiting')}, total={r.get('total')}")

# Step 10: Complete fight
print("\nCompleting fight...")
r = api("POST", "/api/complete_fight", {"sid": sid}, timeout=30)
print(f"complete_fight keys: {list(r.keys())}")
print(f"  success={r.get('success')}, won={r.get('won')}")
print(f"  method={r.get('fight_details', {}).get('method')}, round={r.get('fight_details', {}).get('round')}")
if r.get("milestones"):
    print(f"  milestones={r['milestones']}")

# Final state
s = api("GET", "/api/state", {"sid": sid})
f = s.get("fighter", {})
print(f"\nFinal record: {f.get('record')} (wins={f.get('wins')}, losses={f.get('losses')}, draws={f.get('draws')})")
print(f"Rating: {f.get('rating')}")
