#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
超简化快速测试 - 只测试少量货箱
运行时间约5-10分钟
"""

import os
import sys
from main_optimize import load_official_data, direct_mission
from nsga2_optimizer import NSGAIIOptimizer
from cpsat_scheduler import CPSATScheduler


def main():
    print("=" * 60)
    print("超简化测试 - 简化规模")
    print("=" * 60)

    # 1. 加载完整数据
    print("\n加载数据...")
    cargo, cargo_by_id, types, areas, depot, dem = load_official_data()

    print(f"\n原始统计：")
    print(f"  总货箱数: {len(cargo_by_id)}")
    print(f"  服务区数: {len(areas)}")

    # 查看数据结构
    print("\n[DEBUG] Checking cargo_by_id structure")
    first_cargo = cargo_by_id.iloc[0]
    print(f"  Type: {type(first_cargo)}")

    # 安全地打印列名
    try:
        cols = list(cargo_by_id.columns)
        print(f"  Columns count: {len(cols)}")
        # 只打印ASCII安全的列名
        for col in cols:
            try:
                print(f"    - {col}")
            except:
                print(f"    - [column name encoding issue]")
    except Exception as e:
        print(f"  Error getting columns: {e}")

    # 打印第一行的键
    try:
        first_dict = first_cargo.to_dict()
        print(f"  First row keys: {len(first_dict)}")
    except Exception as e:
        print(f"  Error converting to dict: {e}")

    # 2. 简化货箱：只选前15个（约2-3个服务区）
    cargo_ids = list(cargo_by_id.index)[:15]
    cargo_by_id_small = cargo_by_id.loc[cargo_ids]

    # 获取涉及的服务区
    used_areas = set()
    for idx, row in cargo_by_id_small.iterrows():
        # 使用正确的列名（可能是'服务区编号'或'sid'）
        if '服务区编号' in row:
            used_areas.add(row['服务区编号'])
        elif 'sid' in row:
            used_areas.add(row['sid'])

    print(f"\n简化后统计：")
    print(f"  测试货箱: {len(cargo_by_id_small)}")
    print(f"  涉及服务区: {len(used_areas)}")

    # 计算总重量
    if 'weight' in cargo_by_id_small.columns:
        total_weight = cargo_by_id_small['weight'].sum()
    elif '重量(kg)' in cargo_by_id_small.columns:
        total_weight = cargo_by_id_small['重量(kg)'].sum()
    else:
        total_weight = 0
    print(f"  总重量: {total_weight} kg")

    # 3. 创建CP-SAT调度器（放宽时限）
    print("\n创建CP-SAT调度器...")
    cpsat_scheduler = CPSATScheduler(
        types=types,
        cargo_by_id=cargo_by_id_small,
        time_limit_sec=180  # 放宽到180秒
    )

    # 4. 创建NSGA-II优化器（小规模）
    print("\n创建NSGA-II优化器（小规模）...")
    optimizer = NSGAIIOptimizer(
        cargo_by_id=cargo_by_id_small,
        types=types,
        areas=areas,
        depot=depot,
        dem=dem,
        direct_mission_func=direct_mission,
        cpsat_scheduler=cpsat_scheduler,
        pop_size=5,         # 极小种群
        max_generations=3,  # 只测试3代
        crossover_prob=0.9,
        mutation_prob=0.3,
        seed=42
    )

    # 5. 运行优化
    print("\n开始优化...")
    print("=" * 60)
    pareto_front = optimizer.optimize()

    # 6. 输出结果
    print("\n" + "=" * 60)
    print("优化完成！")
    print("=" * 60)

    if pareto_front:
        print(f"\n找到 {len(pareto_front)} 个帕累托最优解：")
        for i, ind in enumerate(pareto_front, 1):
            print(f"\n方案 {i}:")
            print(f"  架次数: {ind.fitness[0]}")
            print(f"  总能耗: {ind.fitness[1]:.1f} kWh")
            print(f"  完成时间: {ind.fitness[2]:.1f} min")
    else:
        print("\n警告：未找到可行解！")
        print("可能原因：")
        print("1. CP-SAT时限太短（当前180秒）")
        print("2. 约束过于严格")
        print("3. 问题规模仍然太大")


if __name__ == '__main__':
    main()
