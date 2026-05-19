---
name: mma-testing
description: Testing conventions for MMA Life Simulator. Patterns for unit tests, deterministic simulations, mocking fighters, and e2e flow tests.
---

# MMA Life Simulator — Testing Reference

## Testing Framework

- Use `unittest` (stdlib) for all tests
- Run with: `python3 -m unittest discover -s tests -v`
- Auto-run via `.opencode/plugins/validate.js` after Python file edits
- Tests live in `/workspace/mma-life/tests/`

## Existing Test Files

| File | Tests | Description |
|---|---|---|
| `test_fight_engine.py` | 7 | Fight completion, round bounds, determinism, stamina, submission rates |
| `test_balance_validation.py` | 9 | KO rates balanced vs unbalanced, target rate validation |
| `test_persistence.py` | 14 | DB roundtrip, session save/load, version compatibility |

## Deterministic Fight Testing

Always seed random for reproducible tests:

```python
import random
import numpy as np

def setUp(self):
    random.seed(42)
    np.random.seed(42 % 2**30)
    self.f1 = Fighter("Fighter A", 28, 170, "mma", "balanced")
    self.f2 = Fighter("Fighter B", 28, 170, "mma", "balanced")
    # Set all attributes to known values
    for f in [self.f1, self.f2]:
        for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
            f.attributes[attr] = 70

def run_fight(self, seed=None):
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed % 2**30)
    fight = Fight(self.f1, self.f2, rounds=3)
    fight.strategy1.set_pre_fight_strategy("balanced")
    fight.strategy2.set_pre_fight_strategy("balanced")
    for event in fight.simulate_fight_gen():
        if event["type"] == "complete":
            break
    return fight
```

## Testing Generator-Based Code

The fight engine uses `yield` to produce event dicts. Test individual events:

```python
def test_event_stream(self):
    gen = fight.simulate_fight_gen()
    events = list(gen)  # collect all events
    event_types = [e['type'] for e in events]
    assert 'round_start' in event_types
    assert 'round_end' in event_types
    assert 'complete' in event_types
```

## Balance Testing

Run batch simulations and check outcome distributions:

```python
def run_batch(n=200):
    results = Counter()
    for i in range(n):
        random.seed(i)
        f1 = make_fighter("F1", some_attrs)
        f2 = make_fighter("F2", other_attrs)
        fight = Fight(f1, f2)
        for event in fight.simulate_fight_gen():
            if event['type'] == 'complete':
                break
        results[fight.method] += 1
    total = sum(results.values())
    return {k: v/total*100 for k, v in results.items()}
```

## Mocking Fighters

For tests that don't need full fight simulation:

```python
def make_fighter(name, attrs=None, archetype="balanced"):
    f = Fighter(name, 28, 170, "mma", archetype)
    if attrs:
        for k, v in attrs.items():
            f.attributes[k] = v
    return f
```

## E2E Testing via API

Don't use curl in tests — use Python's `urllib.request` or direct function calls:

```python
import urllib.request
import json

def api_call(path, data=None, sid="test"):
    if data is None:
        data = {}
    data["sid"] = sid
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(f"http://localhost:8080{path}", data=body)
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())
```

## What to Assert

| Scenario | Assertions |
|---|---|
| Fight completes | `winner is not None`, `method in ("KO","SUB","DEC")` |
| Fight week event | `result.status == "completed"` |
| Attribute changes | `fighter.attributes[attr] after > before` |
| Stat comparison | `showComparison()` does not throw, all fields defined |
| Session isolation | Two SIDs have independent state |
| Save/load | After save + reinit, state matches |

## Performance Testing

```python
import time, tracemalloc

tracemalloc.start()
t0 = time.time()
# ... test code ...
elapsed = time.time() - t0
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
```

## Known Testing Pitfalls

1. **Fight non-determinism**: Fight outcomes vary unless both `random.seed()` AND `numpy.random.seed()` are set
2. **Fighter deepcopy**: Tests modifying fighters must use `copy.deepcopy()` to avoid cross-test contamination
3. **Global state**: `generator.py` caches the fighter pool in a global. Tests that modify fighters must account for this
4. **Session state**: Sessions time out after 2h. Long test suites must use fresh SIDs
5. **DB isolation**: Use `tempfile.mktemp()` for DB paths to avoid test interference
