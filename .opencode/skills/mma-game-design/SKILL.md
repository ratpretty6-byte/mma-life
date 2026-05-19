---
name: mma-game-design
description: Use when working on MMA Life Simulator game code, fight engine, career/promotion/training systems, or game balance. Contains domain rules, architecture, and known issues.
---

# MMA Life Simulator — Game Design Reference

## Architecture Overview

```
web_server.py (HTTP API + session management)
  +-- fighter.py     — Core fighter data model (29 attrs: 21 physical + 8 mental)
  +-- fight.py       — ~3200 line fight simulation engine (state machine)
  +-- positions.py   — Fight position state machine: DISTANCE → POCKET → CLINCH → GROUND
  +-- strategy.py    — 18 fight strategies with drift-based mid-fight adaptation
  +-- commentary.py  — Flavor text generation for fight events
  +-- training.py    — 13 drills, 6 camp templates, overtraining risk
  +-- career.py      — Career progression, rivalries, awards, retirement
  +-- promotion.py   — 3-tier promotions: Regional → National → World
  +-- events.py      — Event/fight booking system
  +-- finance.py     — Money, agents, gym memberships, PPV, taxes
  +-- health.py      — Injuries, medical suspensions
  +-- media.py       — Popularity, social media, press conferences
  +-- news.py        — Story formatting + StorylineTracker
  +-- world_sim.py   — Background AI simulation (monthly)
  +-- generator.py   — Fighter generation (3000 on init)
  +-- utils.py       — Constants, helpers, combos, severity tiers
```

### State Management
- **SQLite persistence** via `persistence.py` (`mma_life.db`). Sessions auto-saved on day advance, fight completion, promotion changes.
- Sessions stored per `sid` in `gs["sessions"]`. Survive server restarts via `save_session`/`load_session`.
- World sim runs monthly via daemon thread
- Session cleanup every 5 min (2h timeout)
- Save slots via `save_to_slot`/`load_from_slot` for manual save/load

### Fighter Model (fighter.py)
- 21 physical attrs + 8 mental attrs (0-100 scale)
- 10 body zones: left_eye, right_eye, jaw, temple, nose, chest, solar_plexus, liver, lead_leg, rear_leg
- Prime age: 24-33, Decline: 34+, Steep decline: 39+
- `ZONE_KO_MULTIPLIER`: jaw 1.4, temple 1.8, solar_plexus 1.3, liver 1.5

### Fight Engine (fight.py)
- Generator-based simulation: `simulate_fight_gen()` yields event dicts
- 6-tier severity: Blocked → Glancing → Clean → Solid → Flush → Devastating (+ Critical)
- KO accumulation: Dazed → Wobbled → On the verge → Finish (chin resists based on durability, mental toughness, composure, heart)
- 3 referee styles: protective, let_them_fight, strict
- 3 judges, 10-point must system with 10-8 gate logic
- Position system: Distance → Pocket → Clinch → Ground (Guard/Side/Mount/Back)
- 18 strategies with action weights, modifiers, counters
- 14 combos with IQ requirements, stamina multipliers, power bonuses
- Second wind: heart-based stamina recovery when gassed
- ROUND_DURATION = 300 (5 min), CHAMPIONSHIP_ROUNDS = 5, REGULAR_ROUNDS = 3

### Career System (career.py)
- 3-tier promotion ladder with rankings, titles, rivalries
- Awards: Fighter of the Year, KO/Sub/Fight of the Year, Comeback, Rookie
- Retirement at 40+ or 3-loss streaks at 35+
- Comeback within 2 years of retirement
- Title stripping after 180 days inactive

### Training System (training.py)
- 13 drills, 6 camp templates, film study 2x/week
- Overtraining at >80% fatigue
- Recovery: ice bath, massage, nutrition, meditation

### Financial System (finance.py)
- Fight purses with agent cuts, living expenses, gym fees
- Sponsorships by rank/popularity, PPV revenue sharing
- 30% tax on income >$50k/month
- Basic investment system

### Fight Week System (`web_server.py`)
- Triggered when `days_until_fight <= 5` after booking a fight
- Auto-triggered on `advance_day` (returns event in `day_result.fight_week_event`)
- Interactive endpoints allow player choices with stat effects:
  - `/api/press_conference` — 3 choices (respectful/trash_talk/staredown) affecting popularity, composure, confidence
  - `/api/open_workout` — 3 choices (technical/power/showboat) with attribute gains and popularity
  - `/api/cut_weight` — 3 intensity levels (safe/standard/aggressive) affecting success chance, hydration recovery, penalties
  - `/api/faceoff` — 3 choices (intense/calm/dismissive) with charisma vs composure stat check
  - `/api/rest_day` — 4 recovery options (ice_bath/massage/meditation/light_spar) for fatigue, injury, attribute bonuses
- Events tracked in `fight_week_progress` dict per session
- Event order: press_conference → open_workout → weigh_in → faceoff → rest_day
- Weight cut failure: hydration penalty, purse deduction, potential fight cancellation
- Rest day skill unlocked after completing other events

### Scouting System (frontend only)
- Opponent stats visibility depends on `fighter.scouting_level`:
  - `scouting_level < 1`: stats show as "???"
  - `scouting_level < 3`: rounded ranges ("40-50", "60-70")
  - `scouting_level >= 3`: exact values
- Tale of the Tape shows: Record, Rank, Rating, Height, Reach, Age, KOs, Subs, Style (archetype), Background, Stance
- Difficulty tags computed from `risk` field: sacrifice→"Step Up", tough→"Tough Fight", 50-50→"Pick 'Em", gimme→"Should Win"

## Known Bugs & Issues

### Critical Bugs (gameplay-affecting)
1. `generator.py:141-143`: Archetype profile adjustments applied before new archetype is set — wrong profile
2. `fight.py:1891`: `target == "legs"` is unreachable (uses "lead_leg"/"rear_leg")
3. `fight.py:993-997`: `f1_td_att = takedowns_landed - takedowns_landed` (always 0)
4. `web_server.py:1270`: Fight history generation logic is broken
5. `utils.py:248/promotion.py:102`: SOS uses hardcoded `[50.0]`
6. `career.py:163-166`: Season awards date window can be skipped
7. `fight.py` knockdown checks: redundant health threshold conditions

### Code Quality Issues
- 3200-line fight.py needs splitting (after tests)
- Hundreds of hardcoded magic numbers (damage, stamina, financial) — some now in `config/combat.json`
- Sessions insecure (user-provided SID)
- Frontend is a monolithic `index.html` (no component framework)
- Some fight week event effects are unbalanced (weights not playtested)
- World sim doesn't handle fighters stuck in fight week state

### Fixed Bugs (recently resolved)
1. `fighter.py:__hash__`: Fixed crash on partially-constructed Fighter during `copy.deepcopy` (`deepcopy` of Fighter via `Contract`→`Promotion`→`contracts` dict key calls `__hash__` before `__init__` finishes `name` assignment). Fixed with `getattr` fallback.
2. `persistence.py:save_promotions`: Fixed fighter deduplication using `{f.name: f}` dict — lost fighters with duplicate names. Fixed by using `_db_id` as key.
3. `web_server.py:get_fight_booking_state`: Removed nationality filter causing empty opponent pools.
4. `web_server.py:advance_day`: Removed hard block during fight week — now auto-triggers events and returns them in response.
5. `templates/index.html:showComparison`: Fixed `o.difficulty` undefined crash by computing difficulty from `risk` field lookup. Fixed CSS grid alignment with `.compare-grid-3` class.

## Available Tooling

### SQLite Game DB (MCP)
Query `mma_life.db` directly with SQL to analyze game state, fighter stats, etc.
Example: `SELECT archetype, COUNT(*) FROM fighters GROUP BY archetype`

### GitHub MCP
Repo management — issues, PRs, code search. Auth uses `GITHUB_TOKEN` env var.

### Playwright MCP
Browser automation for UI testing. Takes screenshots, runs page interactions.

### Validation Plugin (`.opencode/plugins/validate.js`)
Auto-runs `python3 -m unittest` after every Python file edit.

### Analyze Tool (`python3 analyze.py`)
Reports: `all`, `balance`, `fighters`, `promotions`, `careers`, `world`
- Checks archetype/weight class distributions
- Finds hot streaks, ranking anomalies, career declines
- Reports promotion structure and champion status
- Reads player session data

### Agents
- `playtester` — bulk fight sims + balance analysis + fight week flow validation
- `reviewer` — code quality + stdlib enforcement + frontend review rules
- `game-analyst` — database queries + game data reports
- `frontend-debugger` — Playwright UI testing, screenshot comparison, console error detection
- `e2e-tester` — full end-to-end API flow: create → book → fight week → fight → results
- `fight-engine-tuner` — 500+ sim balance analysis, archetype matchups, combat.json tuning
- `save-validator` — SQLite schema integrity, orphaned records, corruption detection
- `performance-profiler` — CPU + memory profiling, O(n²) loop detection, deepcopy cost analysis

### Commands
- `/playtest` — run 500+ bulk sims, report KO/sub/decision rates, archetype matchups
- `/game-analyze` — comprehensive game data report from SQLite
- `/test-all` — run the full testing suite: reviewer → unittest → fight-engine-tuner → frontend-debugger → e2e-tester → save-validator → performance-profiler

## Coding Conventions
- **No external dependencies** — Python stdlib only (except opencode tooling)
- No third-party packages in requirements.txt
- `sqlite3` is stdlib and acceptable for persistence
- `unittest` is stdlib and acceptable for tests
- Use type hints from `typing` module
- Generator pattern for sequence-heavy logic
- Deep copy fighters before AI vs AI simulation
- Session state in dicts keyed by `sid`
