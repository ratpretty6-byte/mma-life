#!/usr/bin/env python3
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HISTORICAL_RATES = {
    "UFC 2010-2019 (all weight classes)": {
        "ko_tko_pct": 31.3,
        "submission_pct": 18.0,
        "decision_pct": 49.4,
        "source": "UFC.com historical stats"
    },
    "UFC Heavyweight": {
        "ko_tko_pct": 45.0,
        "submission_pct": 12.0,
        "decision_pct": 43.0,
        "source": "Estimated from UFC HW history"
    },
    "UFC Lightweight": {
        "ko_tko_pct": 25.0,
        "submission_pct": 22.0,
        "decision_pct": 53.0,
        "source": "Estimated from UFC LW history"
    },
    "UFC Women's Strawweight": {
        "ko_tko_pct": 15.0,
        "submission_pct": 25.0,
        "decision_pct": 60.0,
        "source": "Estimated from UFC WSW history"
    }
}

def main():
    print("MMA Life — Real UFC Outcome Rates Reference")
    print("=" * 60)
    for label, data in HISTORICAL_RATES.items():
        print(f"\n{label}:")
        print(f"  KO/TKO:      {data['ko_tko_pct']:.1f}%")
        print(f"  Submission:  {data['submission_pct']:.1f}%")
        print(f"  Decision:    {data['decision_pct']:.1f}%")
        print(f"  (Source: {data['source']})")
    print("\n" + "=" * 60)
    print("These values serve as balance targets for combat.json tuning.")

if __name__ == "__main__":
    main()
