#!/usr/bin/env python3
import json
import os
import sys

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
SCHEMAS = {}

def load_json(path):
    with open(path) as f:
        return json.load(f)

def check_type(val, typ, path, errors):
    if typ == "int" and not isinstance(val, int):
        errors.append(f"{path}: expected int, got {type(val).__name__}")
    elif typ == "float" and not isinstance(val, (int, float)):
        errors.append(f"{path}: expected number, got {type(val).__name__}")
    elif typ == "string" and not isinstance(val, str):
        errors.append(f"{path}: expected string, got {type(val).__name__}")
    elif typ == "list" and not isinstance(val, list):
        errors.append(f"{path}: expected list, got {type(val).__name__}")
    elif typ == "object" and not isinstance(val, dict):
        errors.append(f"{path}: expected object, got {type(val).__name__}")

def check_range(val, lo, hi, path, errors):
    if isinstance(val, (int, float)):
        if val < lo or val > hi:
            errors.append(f"{path}: value {val} out of range [{lo}, {hi}]")

def check_combat(data, errors):
    required_keys = ["round", "stamina_costs", "strike_profiles", "target_damage_modifiers",
                     "severity_tiers", "critical_hit", "combo", "ko_system",
                     "head_damage_accumulation", "ground_tko", "recovery", "submission",
                     "balance_targets_3r_even"]
    for k in required_keys:
        if k not in data:
            errors.append(f"combat.json: missing required key '{k}'")

    if "round" in data:
        r = data["round"]
        check_range(r.get("duration", 0), 60, 600, "round.duration", errors)
        check_range(r.get("championship_rounds", 0), 3, 7, "round.championship_rounds", errors)
        check_range(r.get("regular_rounds", 0), 1, 5, "round.regular_rounds", errors)

    if "critical_hit" in data:
        ch = data["critical_hit"]
        check_range(ch.get("base_chance", 0), 0, 1, "critical_hit.base_chance", errors)
        check_range(ch.get("damage_multiplier", 0), 1, 5, "critical_hit.damage_multiplier", errors)

    if "severity_tiers" in data:
        for i, t in enumerate(data["severity_tiers"]):
            prefix = f"severity_tiers[{i}]"
            check_type(t, "object", prefix, errors)
            check_range(t.get("knockdown_chance", 0), 0, 1, f"{prefix}.knockdown_chance", errors)

    if "balance_targets_3r_even" in data:
        bt = data["balance_targets_3r_even"]
        total = bt.get("ko_tko_pct", 0) + bt.get("submission_pct", 0) + bt.get("decision_pct", 0)
        if abs(total - 100) > 2:
            errors.append(f"balance_targets_3r_even: percentages sum to {total}, expected ~100")

def check_career(data, errors):
    for k in ["age", "pro_tiers", "ranking", "finance", "contract", "injuries", "awards"]:
        if k not in data:
            errors.append(f"career.json: missing required key '{k}'")
    if "age" in data:
        a = data["age"]
        check_range(a.get("prime_start", 0), 18, 40, "age.prime_start", errors)
        check_range(a.get("retirement_age", 0), 30, 50, "age.retirement_age", errors)
    if "finance" in data:
        f = data["finance"]
        check_range(f.get("tax_rate", 0), 0, 1, "finance.tax_rate", errors)

def check_world(data, errors):
    for k in ["generation", "skills", "aging", "world_simulation", "weight_classes"]:
        if k not in data:
            errors.append(f"world.json: missing required key '{k}'")

def main():
    errors = []
    configs = {
        "combat.json": check_combat,
        "career.json": check_career,
        "world.json": check_world,
    }

    for fname, checker in configs.items():
        path = os.path.join(CONFIG_DIR, fname)
        if not os.path.exists(path):
            errors.append(f"{fname}: file not found")
            continue
        try:
            data = load_json(path)
            checker(data, errors)
        except json.JSONDecodeError as e:
            errors.append(f"{fname}: invalid JSON ({e})")

    if errors:
        print("CONFIG VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("All config files validated successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
