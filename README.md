# MMA Life Simulator

A text-based MMA career simulation game with a web UI. Build your fighter, train, climb the rankings, fight for titles, and manage your career.

## Quick Start

```bash
python3 web_server.py
# Open http://localhost:8000 in your browser
```

## Features

- **Fight Engine**: 9-zone health model, 6-tier severity system, 18 strategies, submission/KO/decision victories
- **Career Mode**: 3-tier promotions (Regional → National → World), rankings, titles, rivalries, awards
- **Training**: 13 drills, 6 camp templates, overtraining risk, film study
- **Financial**: Contracts, sponsorships, PPV revenue, taxes, investments, agents
- **Media**: Press conferences, social media, popularity system
- **Health**: Injuries, medical suspensions, aging, recovery
- **World Simulation**: Background AI fights, rankings, prospect generation

## Architecture

```
web_server.py   HTTP API + session management (port 8000)
fighter.py      Fighter data model (29 attributes, body zones)
fight.py        Fight simulation engine (generator-based)
positions.py    Position state machine (distance → clinch → ground)
strategy.py     18 strategies with mid-fight adaptation
training.py     Training drills, camps, weekly schedules
career.py       Career progression, rivalries, awards
promotion.py    3-tier promotions with rankings
finance.py      Money management, contracts, PPV
health.py       Injuries, medical suspensions
media.py        Popularity, press, social media
events.py       Event booking system
world_sim.py    Background AI world simulation
generator.py    Fighter generation
news.py         Story formatting
persistence.py  SQLite persistence layer

config/
  combat.json   Combat balance constants
  career.json   Career & financial constants
  world.json    World generation constants
```

## API

All endpoints accept JSON or form-encoded POST data (GET for read-only).

| Endpoint | Method | Description |
|---|---|---|
| `/api/state?sid=...` | GET | Get full game state |
| `/api/create_fighter` | POST | Create new fighter career |
| `/api/advance_day` | POST | Advance one day |
| `/api/advance_time` | POST | Advance multiple days |
| `/api/start_fight` | POST | Begin a booked fight |
| `/api/fight_action` | POST | Submit round strategy |
| `/api/complete_fight` | POST | Finalize fight results |
| `/api/start_training` | POST | Begin training |
| `/api/start_camp` | POST | Begin training camp |
| `/api/sign_free_agent` | POST | Sign with promotion |
| `/api/book_fight` | POST | Book a fight |
| `/api/opponents` | GET | List available opponents |
| `/api/balance_test` | GET | Run balance statistics |
| `/api/bulk_simulate` | GET | Bulk AI fight simulation |

## Persistence

Data is saved to `mma_life.db` (SQLite) automatically on day advance,
fight completion, and promotion changes. Sessions survive server restarts.

## Development

```bash
# Run tests
python3 -m unittest tests.test_fight_engine -v

# Edit balance configs
vim config/combat.json
vim config/career.json

# Check code style (stdlib only — no external deps)
python3 -c "import ast; ast.parse(open('fight.py').read())"
```

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

