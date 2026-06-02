#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils
from fighter import Fighter
from fight import Fight
from strategy import STRATEGIES
from promotion import Promotion, Contract
from training import DRILLS, TrainingSystem
from finance import FinancialSystem
from health import HealthSystem

import random
import numpy as np

random.seed(42)
np.random.seed(42 % 2**30)

f1 = Fighter("Player Fighter", 25, 170, "mma", "balanced",
             nationality="American", region="California")
f2 = Fighter("Opponent Fighter", 28, 185, "bjj", "bjj_specialist",
             nationality="Brazilian", region="Rio de Janeiro")
for f in [f1, f2]:
    for attr in f.PHYSICAL_ATTRS + f.MENTAL_ATTRS:
        f.attributes[attr] = 70

print("MMA Life Simulator — Interactive Shell")
print("=" * 50)
print(f"  f1 = {f1.name} ({f1.archetype}, {f1.weight}lbs, {f1.age}yo)")
print(f"  f2 = {f2.name} ({f2.archetype}, {f2.weight}lbs, {f2.age}yo)")
print(f"  Fight, STRATEGIES, DRILLS, random, np imported")
print(f"  utils, Fighter, Contract, Promotion, TrainingSystem ready")
print("=" * 50)
