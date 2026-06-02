# Test Fixtures

Place pre-built `mma_life.db` files here for testing specific game scenarios.

## Expected Fixtures

- `title_contender.db` — Player is ranked #1, title shot imminent
- `injured_fighter.db` — Player has an active injury
- `deep_career.db` — Player is 10+ years into their career
- `empty_world.db` — Minimal world state for fast test setup

## Usage

```python
import shutil
import tempfile

def use_fixture(name):
    src = f"tests/fixtures/{name}.db"
    dst = os.path.join(tempfile.mkdtemp(), "mma_life.db")
    shutil.copy(src, dst)
    return dst
```
