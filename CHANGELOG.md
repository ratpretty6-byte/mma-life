# Changelog

## [Unreleased]

### Added
- CI pipeline via GitHub Actions (ruff, mypy, bandit, vulture, pytest, coverage)
- Pre-commit hooks for automatic code quality checks
- Memory, Sequential Thinking, and Filesystem MCP servers
- Custom Game API MCP server for agent-driven integration testing
- Config schema validator (scripts/validate_config.py)
- Interactive balance tuning dashboard (templates/balance.html)
- Game state inspector debug page (templates/debug.html)
- Python REPL shell for quick experimentation (scripts/shell.py)
- Makefile with common developer commands
- AGENTS.md documenting all subagent conventions
- Docker Compose configuration
- EditorConfig for consistent code style
- VSCode workspace configuration (debugging, lint-on-save)
- GitHub issue templates (bug report, feature request)
- Dependabot configuration for automated dependency updates
- Seed fuzzer subagent for determinism testing
- Config designer subagent for balance tuning

### Changed
- Updated pyproject.toml with bandit, vulture, and hypothesis config sections
- Updated .opencode/opencode.json with new MCP servers and agents
- Updated .gitignore for new tooling patterns
