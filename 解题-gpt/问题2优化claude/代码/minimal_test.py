#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
最小化测试 - 直接使用main_optimize.py的所有代码，只改参数
"""

import sys
from pathlib import Path

# 确保能导入main_optimize
sys.path.insert(0, str(Path(__file__).parent))

from main_optimize import load_official_data, direct_mission
from nsga2_optimizer import NSGAIIOptimizer
from cpsat_scheduler import CPSATScheduler


def main():
    print("=" * 60)
    print("Minimal Test - Using main_optimize framework")
    print("=" * 60)

    # 1. Load data (same as main_optimize.py)
    cargo, cargo_by_id, types, areas, depot, dem = load_official_data()

    # 2. Take only first 20 cargos
    print(f"\nOriginal: {len(cargo_by_id)} cargos")
    cargo_ids = list(cargo_by_id.index)[:20]
    cargo_by_id_small = cargo_by_id.loc[cargo_ids].copy()
    print(f"Testing with: {len(cargo_by_id_small)} cargos")

    # 3. Create CP-SAT scheduler
    print("\nCreating CP-SAT scheduler...")
    cpsat_scheduler = CPSATScheduler(
        types=types,
        cargo_by_id=cargo_by_id_small,
        time_limit_sec=120
    )

    # 4. Create NSGA-II optimizer (minimal params)
    print("\nCreating NSGA-II optimizer...")
    optimizer = NSGAIIOptimizer(
        cargo_by_id=cargo_by_id_small,
        types=types,
        areas=areas,
        depot=depot,
        dem=dem,
        direct_mission_func=direct_mission,
        cpsat_scheduler=cpsat_scheduler,
        pop_size=5,
        max_generations=3,
        crossover_prob=0.9,
        mutation_prob=0.3,
        seed=42
    )

    # 5. Run optimization
    print("\nRunning optimization...")
    print("=" * 60)
    pareto_front = optimizer.optimize()

    # 6. Show results
    print("\n" + "=" * 60)
    print("Optimization complete!")
    print("=" * 60)

    if pareto_front:
        print(f"\nFound {len(pareto_front)} Pareto optimal solutions:")
        for i, ind in enumerate(pareto_front, 1):
            print(f"\nSolution {i}:")
            print(f"  Feasible: {ind.feasible}")
            if ind.objectives:
                obj = ind.objectives
                # 检查是否为无穷大
                import math
                if math.isinf(obj[0]):
                    print(f"  Missions: INFEASIBLE")
                    print(f"  Energy: INFEASIBLE")
                    print(f"  Time: INFEASIBLE")
                else:
                    print(f"  Missions: {int(obj[0])}")
                    print(f"  Energy: {obj[1]:.1f} kWh")
                    print(f"  Time: {obj[2]:.1f} min")
            else:
                print(f"  No objectives computed")
    else:
        print("\nWarning: No feasible solution found!")


if __name__ == '__main__':
    main()
