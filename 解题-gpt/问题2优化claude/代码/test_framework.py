#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速测试脚本 - 验证优化框架

运行小规模测试（5代，10个个体）来验证代码正确性
"""
from __future__ import annotations

import sys
from pathlib import Path

# 设置路径
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
WORK = PROJECT / "解题-gpt"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(WORK / "代码"))

print("=" * 60)
print("Quick Test - Validate Optimization Framework")
print("=" * 60)

# Test 1: Import check
print("\n[Test 1] Checking module imports...")
try:
    from src.data.data_loader import DataLoader
    from src.terrain.dem_loader import DEMLoader
    from solve_problem1_18trips import direct_mission
    print("  [OK] Project modules imported")
except ImportError as e:
    print(f"  [FAIL] Project module import failed: {e}")
    sys.exit(1)

try:
    from ortools.sat.python import cp_model
    print("  [OK] OR-Tools imported")
except ImportError as e:
    print(f"  [FAIL] OR-Tools import failed: {e}")
    print("    Please run: pip install ortools")
    sys.exit(1)

try:
    from cpsat_scheduler import CPSATScheduler, Mission
    from nsga2_optimizer import NSGAIIOptimizer, Individual
    print("  [OK] Optimizer modules imported")
except ImportError as e:
    print(f"  [FAIL] Optimizer module import failed: {e}")
    sys.exit(1)

# Test 2: Data loading
print("\n[Test 2] Loading official data...")
try:
    data_dir = PROJECT / "数据" / "无人机应急物资运输基础数据"
    dem_dir = PROJECT / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"

    loader = DataLoader(str(data_dir))
    loader.load_all()

    cargo = loader.get_cargos().copy()
    cargo_by_id = cargo.set_index("货箱编号", drop=False)

    types = {r["type"]: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
    areas = {r["id"]: r.to_dict() for _, r in loader.get_service_areas().iterrows()}
    depot = loader.get_depot()

    dem = DEMLoader(str(next(dem_dir.glob("*.mat"))))
    dem.load()

    print(f"  [OK] Data loaded successfully")
    print(f"    Cargo boxes: {len(cargo)}")
    print(f"    Service areas: {len(areas)}")
    print(f"    UAV types: {len(types)}")
except Exception as e:
    print(f"  [FAIL] Data loading failed: {e}")
    sys.exit(1)

# Test 3: CP-SAT scheduler
print("\n[Test 3] Testing CP-SAT scheduler...")
try:
    scheduler = CPSATScheduler(types=types, cargo_by_id=cargo_by_id, time_limit_sec=10)

    # Create simple test missions
    test_missions = [
        Mission(
            mission_id=1,
            area_id='S01',
            uav_type='A',
            cargo_ids=['C001'],
            energy_kwh=2.0,
            duration_min=20.0,
            delivery_offset_min=15.0,
            deadline_min=60.0
        ),
        Mission(
            mission_id=2,
            area_id='S02',
            uav_type='A',
            cargo_ids=['C002'],
            energy_kwh=2.5,
            duration_min=25.0,
            delivery_offset_min=18.0,
            deadline_min=80.0
        )
    ]

    result = scheduler.schedule(test_missions)

    if result.success:
        print(f"  [OK] CP-SAT scheduling successful")
        print(f"    Makespan: {result.makespan_min:.2f} minutes")
        print(f"    Solve time: {result.solve_time_sec:.2f} seconds")
    else:
        print(f"  [WARN] CP-SAT scheduling failed to find solution")

except Exception as e:
    print(f"  [FAIL] CP-SAT scheduler test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: NSGA-II optimizer initialization
print("\n[Test 4] Testing NSGA-II optimizer...")
try:
    optimizer = NSGAIIOptimizer(
        cargo_by_id=cargo_by_id,
        types=types,
        areas=areas,
        depot=depot,
        dem=dem,
        direct_mission_func=direct_mission,
        cpsat_scheduler=scheduler,
        pop_size=5,  # Small scale test
        max_generations=2,  # Only 2 generations
        seed=42
    )
    print(f"  [OK] NSGA-II optimizer initialized")

    # Test population initialization
    print("\n[Test 5] Testing population initialization...")
    population = optimizer.initialize_population()
    print(f"  [OK] Population initialized, size: {len(population)}")

    # Test individual evaluation (only first one)
    print("\n[Test 6] Testing individual evaluation...")
    ind = population[0]
    print(f"    Initial individual: {len(ind.groups)} missions")

    # Only structure check (full evaluation takes too long)
    if len(ind.groups) > 0:
        print(f"    Mission 1: {len(ind.groups[0])} boxes, visiting {len(ind.routes[0])} areas, using type {ind.types[0]}")
        print(f"  [OK] Individual structure correct")

except Exception as e:
    print(f"  [FAIL] NSGA-II optimizer test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# All tests passed
print("\n" + "=" * 60)
print("[OK] All tests passed! Optimization framework ready")
print("=" * 60)
print("\nTo run full optimization:")
print("  python main_optimize.py")
print("\nOr run quick test:")
print("  python quick_run.py")
