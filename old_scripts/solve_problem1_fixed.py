#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一修复版：支持多架次配送，确保80箱货物全部送达
赛题要求：同一服务区可由多个架次分批服务
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader
from src.problem1.knapsack_solver import Problem1Solver


def solve_problem1_complete():
    """问题一完整求解：多架次配送直到80箱全部送达"""

    print("\n" + "="*80)
    print("问题一修复版：多架次配送方案（80箱完整配送）")
    print("="*80)

    # 加载数据
    print("\n[步骤1] 加载数据...")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    uavs = loader.get_uav_types()
    all_cargos = loader.get_cargos()

    print(f"  调度中心: {depot['name']}")
    print(f"  服务区: {len(service_areas)}个")
    print(f"  货箱总数: {len(all_cargos)}箱")

    # 初始化求解器
    print("\n[步骤2] 初始化求解器...")
    solver = Problem1Solver(loader)

    # 追踪已配送货箱
    delivered_cargos = set()
    all_trips = []
    trip_id = 1

    print("\n[步骤3] 执行多架次配送...")
    print("="*80)

    # 按服务区分组
    for idx, area in service_areas.iterrows():
        area_id = area['id']
        area_name = area['name']

        print(f"\n{'='*60}")
        print(f"服务区 {idx+1}/15: {area_id} - {area_name}")
        print(f"{'='*60}")

        # 获取该服务区所有未配送的货箱
        area_cargos = all_cargos[all_cargos['服务区编号'] == area_id].copy()
        remaining_cargos = area_cargos[~area_cargos['货箱编号'].isin(delivered_cargos)].copy()

        print(f"  总需求: {len(area_cargos)}箱")
        print(f"  待配送: {len(remaining_cargos)}箱")

        if len(remaining_cargos) == 0:
            print("  [跳过] 无待配送货物")
            continue

        # 多架次配送直到该服务区货物全部送达
        trip_count = 0
        max_trips = 10  # 防止死循环

        while len(remaining_cargos) > 0 and trip_count < max_trips:
            trip_count += 1

            # 为当前剩余货物选择最优机型和装载方案
            best_solution = None
            best_uav_type = None
            best_score = -1

            for _, uav in uavs.iterrows():
                uav_type = uav['type']

                # 临时修改求解器的货物列表
                original_cargos = solver.data_loader.cargos
                solver.data_loader.cargos = remaining_cargos
                solver.cargos = remaining_cargos

                result = solver.solve_single_trip(area_id, uav_type, method='greedy')

                # 恢复原始货物列表
                solver.data_loader.cargos = original_cargos
                solver.cargos = original_cargos

                if 'error' in result or not result.get('is_feasible', False):
                    continue

                # 评分：优先级总和 / 能耗
                score = result['total_value'] / max(result['energy_kwh'], 0.1)

                if score > best_score:
                    best_score = score
                    best_solution = result
                    best_uav_type = uav_type

            if best_solution is None:
                print(f"  [架次{trip_count}] 无可行方案，剩余{len(remaining_cargos)}箱无法配送")
                break

            # 记录配送方案
            delivered_in_trip = best_solution['selected_cargos']
            num_delivered = len(delivered_in_trip)

            # 提取货箱ID列表（selected_cargos是字典列表）
            cargo_ids = [cargo['id'] for cargo in delivered_in_trip]

            trip_record = {
                'trip_id': trip_id,
                'area_id': area_id,
                'area_name': area_name,
                'uav_type': best_uav_type,
                'num_cargos': num_delivered,
                'total_weight': best_solution['total_weight_kg'],
                'total_volume': best_solution['total_volume_m3'],
                'total_energy': best_solution['energy_kwh'],
                'flight_time': best_solution['flight_time_min'],
                'total_value': best_solution['total_value']
            }

            all_trips.append(trip_record)

            # 更新已配送集合
            for cargo_id in cargo_ids:
                delivered_cargos.add(cargo_id)

            # 更新剩余货物
            remaining_cargos = remaining_cargos[~remaining_cargos['货箱编号'].isin(cargo_ids)]

            print(f"  [架次{trip_count}] {best_uav_type}型: "
                  f"{num_delivered}箱, "
                  f"{best_solution['total_weight_kg']:.1f}kg, "
                  f"{best_solution['energy_kwh']:.2f}kWh")

            trip_id += 1

        if len(remaining_cargos) > 0:
            print(f"  [警告] 仍有{len(remaining_cargos)}箱未配送")

    # 生成结果汇总
    print("\n" + "="*80)
    print("配送结果汇总")
    print("="*80)

    trips_df = pd.DataFrame(all_trips)

    print(f"\n总架次数: {len(trips_df)}")
    print(f"配送货箱: {len(delivered_cargos)}/{len(all_cargos)} ({len(delivered_cargos)/len(all_cargos)*100:.1f}%)")
    print(f"总能耗: {trips_df['total_energy'].sum():.2f} kWh")
    print(f"总飞行时间: {trips_df['flight_time'].sum():.2f} 分钟")

    # 按服务区汇总
    print("\n按服务区统计:")
    area_summary = trips_df.groupby('area_id').agg({
        'trip_id': 'count',
        'num_cargos': 'sum',
        'total_energy': 'sum'
    }).rename(columns={'trip_id': '架次数', 'num_cargos': '货箱数', 'total_energy': '能耗kWh'})
    print(area_summary.to_string())

    # 保存结果
    print("\n[步骤4] 保存结果...")
    output_dir = Path("结果")
    output_dir.mkdir(exist_ok=True)

    # 保存详细架次表
    trips_df.to_excel(output_dir / "问题一_多架次配送方案.xlsx", index=False)
    print(f"  已保存: 问题一_多架次配送方案.xlsx")

    # 保存服务区汇总
    area_summary.to_excel(output_dir / "问题一_服务区汇总.xlsx")
    print(f"  已保存: 问题一_服务区汇总.xlsx")

    # 保存货箱配送清单
    cargo_delivery = []
    for _, trip in trips_df.iterrows():
        # 找回该架次配送的货箱
        area_cargos = all_cargos[all_cargos['服务区编号'] == trip['area_id']]
        # 这里简化处理，实际需要记录每个架次的具体货箱
        for cargo_id in area_cargos['货箱编号'].head(trip['num_cargos']):
            if cargo_id in delivered_cargos:
                cargo_delivery.append({
                    'trip_id': trip['trip_id'],
                    'cargo_id': cargo_id,
                    'area_id': trip['area_id']
                })

    print("\n" + "="*80)

    if len(delivered_cargos) == len(all_cargos):
        print("✅ 成功配送全部80箱货物！")
    else:
        print(f"⚠️  仍有{len(all_cargos) - len(delivered_cargos)}箱未配送")

    print("="*80)

    return {
        'total_trips': len(trips_df),
        'total_cargos': len(delivered_cargos),
        'total_energy': trips_df['total_energy'].sum(),
        'total_time': trips_df['flight_time'].sum()
    }


if __name__ == "__main__":
    result = solve_problem1_complete()
