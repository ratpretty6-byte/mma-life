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
- **No database currently** — all in-memory via `gs` global dict in web_server.py
- Sessions stored per `sid` in `gs["sessions"]`
- World sim runs monthly via daemon thread
- Session cleanup every 5 min (2h timeout)

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
- Hundreds of hardcoded magic numbers (damage, stamina, financial)
- No persistence (in-memory only)
- No tests
- Sessions insecure (user-provided SID)
- README is 1 line

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
- `playtester` — bulk fight sims + balance analysis
- `reviewer` — code quality + stdlib enforcement
- `game-analyst` — database queries + game data reports

### Commands
- `/playtest` — run 50 bulk sims, report KO/sub/decision rates
- `/game-analyze` — comprehensive game data report from SQLite

## Coding Conventions
- **No external dependencies** — Python stdlib only (except opencode tooling)
- No third-party packages in requirements.txt
- `sqlite3` is stdlib and acceptable for persistence
- `unittest` is stdlib and acceptable for tests
- Use type hints from `typing` module
- Generator pattern for sequence-heavy logic
- Deep copy fighters before AI vs AI simulation
- Session state in dicts keyed by `sid`
