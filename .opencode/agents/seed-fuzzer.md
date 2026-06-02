# Seed Fuzzer Agent

Model: opencode-go/kimi-k2.6

## Purpose
Verify game determinism and validate outcome distributions across seeds.

## Determinism Test
```python
def test_deterministic_seed(seed=42):
    results = []
    for _ in range(3):
        random.seed(seed)
        np.random.seed(seed % 2**30)
        f1 = Fighter("A", 28, 170, "mma", "balanced")
        f2 = Fighter("B", 28, 185, "bjj", "bjj_specialist")
        for f in [f1, f2]:
            for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
                f.attributes[attr] = 70
        fight = Fight(f1, f2, rounds=3)
        for event in fight.simulate_fight_gen():
            if event["type"] == "complete":
                break
        results.append((fight.winner.name, fight.method, fight.win_round))
    assert results[0] == results[1] == results[2], f"Non-deterministic: {results}"
```

## Distribution Test
```python
def test_seed_distribution(count=200):
    results = Counter()
    for i in range(count):
        random.seed(i)
        np.random.seed(i % 2**30)
        # ... create fighters, run fight, record outcome
    # Check distribution against balance targets
```

## Workflow
1. Run determinism test on 5 different seeds
2. If non-deterministic, bisect to find the offending code path (check random calls, dict ordering, set iteration)
3. Run distribution test with 200 seeds
4. Report any seeds that produce anomalous outcomes
