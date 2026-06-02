# MMA Life Simulator — Agent Conventions

## Code Rules
- Python stdlib only (except: numpy, scipy, jinja2, websockets, diskcache, faker)
- No third-party packages beyond `requirements.txt` + dev tools
- Type hints from `typing` module
- Generator pattern for sequence-heavy fight logic
- Deep copy fighters before AI vs AI simulation

## Running Tests
```bash
make test          # Full suite with coverage
make test-fast     # Parallel (faster)
python3 -m pytest tests/test_foo.py -v -k "test_name"  # Single test
```

## Code Quality
```bash
make lint          # ruff check .
make typecheck     # mypy .
make security      # bandit
make deadcode      # vulture
make check         # All of the above + tests
make format        # ruff format .
```

## Git Conventions
- Commit messages: `verb: short description` (add, fix, refactor, test, docs)
- No commits unless explicitly requested
- Never force push to main

## MCP Servers Available
- **Playwright** — browser UI tests
- **SQLite** — query `mma_life.db` directly
- **GitHub** — repo management
- **Memory** — persist findings across sessions
- **Sequential Thinking** — structured multi-step reasoning
- **Filesystem** — controlled file access
- **Game API** — call game's HTTP API via MCP tools

## Subagents
| Agent | Model | Purpose |
|-------|-------|---------|
| playtester | kimi-k2.6 | Bulk fight sims + balance |
| reviewer | deepseek-v4-flash | Code quality enforcement |
| game-analyst | deepseek-v4-flash | SQLite game data queries |
| frontend-debugger | deepseek-v4-flash | Playwright UI testing |
| e2e-tester | kimi-k2.6 | Full API flow integration |
| fight-engine-tuner | kimi-k2.6 | 500+ sim balance tuning |
| save-validator | deepseek-v4-flash | DB integrity checks |
| performance-profiler | deepseek-v4-flash | CPU/memory profiling |
| config-designer | kimi-k2.6 | Combat.json balance tuning |
| seed-fuzzer | kimi-k2.6 | Determinism testing |

## When to Create New Skills
- When >3 bugs share the same root cause pattern
- When a subsystem has undocumented domain rules
- When a testing workflow takes >5 manual steps
