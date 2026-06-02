.PHONY: test lint typecheck security deadcode serve clean db-reset validate-config shell format check ci

# =============================================================================
# MMA Life Simulator — Developer Commands
# =============================================================================

test:
	python3 -m pytest -v --tb=short --cov=. --cov-report=term-missing:skip-covered

test-fast:
	python3 -m pytest -v --tb=short -n auto

test-watch:
	pytest-watch -- -v --tb=short

lint:
	ruff check .

typecheck:
	mypy .

security:
	bandit -r . --exclude '/.opencode/,/templates/,/tests/,/node_modules/,/.venv/,/config/'

deadcode:
	vulture . --min-confidence 80 --exclude '.opencode,node_modules,templates,config'

validate-config:
	python3 scripts/validate_config.py

shell:
	python3 scripts/shell.py

serve:
	python3 web_server.py

format:
	ruff format .

check: lint typecheck security deadcode test

clean:
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	rm -f mma_life.db mma_life.db-shm mma_life.db-wal
	rm -rf .session_cache/

db-reset:
	rm -f mma_life.db mma_life.db-shm mma_life.db-wal
	rm -rf .session_cache/
	echo "Database reset. Restart the server to regenerate."
