---
name: mma-debugging
description: Common bug patterns, debugging workflows, and log analysis for MMA Life Simulator.
---

# MMA Life Simulator — Debugging Reference

## Common Bug Patterns

### 1. `'Fighter' object has no attribute 'name'`
**Root Cause**: `Fighter.__hash__` is called on a partially-constructed object during `copy.deepcopy()`. The circular reference chain is:
- `Fighter` → `Contract` → `Promotion` → `contracts: Dict[Fighter, Contract]`
- During deepcopy, the proto-object used as a dict key has no `name` yet because `__init__` hasn't finished.

**Fix**: In `__hash__`, use `getattr` fallbacks:
```python
def __hash__(self):
    return hash((getattr(self, '_db_id', None), id(self)))
```

### 2. `Fighter` deduplication losing fighters
**Root Cause**: `load_promotions` uses `{f.name: f}` dict for dedup, losing fighters with duplicate names.

**Fix**: Use `(f._db_id, f.age)` as key instead of `f.name`.

### 3. `o.difficulty` is undefined (TypeError in JS)
**Root Cause**: Backend sends `risk` field but frontend reads `difficulty`. The `risk` values are `sacrifice`, `tough`, `50-50`, `gimme`.

**Fix**: Compute difficulty from `risk`:
```javascript
const diffLookup = {sacrifice:"Step Up", tough:"Tough Fight", "50-50":"Pick 'Em", gimme:"Should Win"};
const diff = o.risk ? diffLookup[o.risk] : (o.difficulty || "Unknown");
```

### 4. Fight week blocks day advance
**Root Cause**: `advance_day` returns error when `days_until_fight > 0`, stopping all progression.

**Fix**: Auto-trigger fight week events and return them in `day_result.fight_week_event` instead of blocking. Use a `FIGHT_WEEK_EVENTS` mapping: `{5: press_conference, 4: open_workout, 3: weigh_in, 2: faceoff, 1: rest_day}`.

### 5. CSS grid broken (2 columns instead of 3)
**Root Cause**: `.compare-grid` is defined as `grid-template-columns: 1fr 1fr` (2 columns) but Tale of the Tape rows have 3 children (my value | label | opp value).

**Fix**: Use `.compare-grid-3` with `grid-template-columns: 1fr auto 1fr`.

### 6. opponent lists empty
**Root Cause**: Opponent pool filtering requires `opp.nationality == f.nationality`. If no fighters share the player's nationality, the pool is empty.

**Fix**: Remove nationality filter from opponent query in `_get_fight_booking_state`.

## Debugging Workflow

### Step 1: Reproduce
1. Start server: `python3 web_server.py`
2. Open browser to `http://localhost:8000`
3. Note exact steps that trigger the bug

### Step 2: Check Server Logs
```bash
# Server prints to stdout. Look for:
# - Tracebacks
# - "ERROR" lines
# - "WARNING" lines about session/state
```

### Step 3: Isolate via API
```bash
# Direct API call without browser:
curl -s -X POST -d 'sid=debug&param=value' 'http://localhost:8080/api/endpoint'
```

### Step 4: Minimal Reproduction in Python
```python
import web_server
# Set up session directly
session = web_server.get_or_create_session("debug")
# Call the failing function
```

### Step 5: Check State
```bash
curl -s 'http://localhost:8080/api/state?sid=debug' | python3 -m json.tool
```

## Log Analysis

### Server Startup
- "Starting server on port X" — OK
- "Address already in use" — kill previous process
- "No module named X" — stdlib missing? Check Python version

### Session Messages
- "New session" — created
- "Session timed out" — reclaimed after 2h
- "Session not found" — bad SID, or reaped

### Fight Engine Logs
- "Fight: A vs B, R1" — fight started
- "Winner: A by KO R2" — fight completed
- "Round X time exceeded" — possible infinite loop

## Quick Fix Reference

| Symptom | Likely Fix | File |
|---|---|---|
| `'name'` error on deepcopy | Fix `__hash__` with `getattr` | `fighter.py` |
| Empty opponent list | Remove nationality filter | `web_server.py:get_fight_booking_state` |
| Can't advance during fight week | Add auto-event trigger | `web_server.py:advance_day` |
| `/api/start_training` 404 | Add endpoint | `web_server.py:do_POST` |
| Stats comparison shows wrong difficulty | Use `risk` field lookup | `templates/index.html:showComparison` |
| CSS rows misaligned | Use `compare-grid-3` class | `templates/index.html` |
| Fighters disappearing on save | Fix `load_promotions` dedup key | `persistence.py` |

## Testing Failed Fixes

After applying a fix:
1. `python3 -m unittest discover -s tests -v` — all pass?
2. Start server, reproduce the bug scenario manually
3. Run `fight-engine-tuner` for balance regression
4. Run `frontend-debugger` for UI regression
5. Commit with `Fixes:` in message referencing the bug
