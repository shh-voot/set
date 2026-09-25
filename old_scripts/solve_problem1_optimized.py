#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一优化版：目标18架次
策略：
1. 更强的背包算法（考虑货箱价值密度）
2. 优先使用大型无人机（C型）
3. 精细化装载优化
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader


def calculate_distance(coord1, coord2):
    """计算两点距离（km）"""
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (np.sin(dlat/2)**2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon/2)**2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    return R * c


def calculate_flight_energy(distance_km, total_weight_kg, uav_specs):
    """计算飞行能耗"""
    cruise_speed = uav_specs['cruise_speed_m_s']

    # 功率计算
    P_cruise = (uav_specs['mass_kg'] + total_weight_kg) * 9.8 * cruise_speed / 1000
    P_ascent = P_cruise * 1.5
    P_descent = P_cruise * 0.7

    # 时间计算
    t_ascent = uav_specs['cruise_altitude_m'] / 5 / 60
    t_descent = uav_specs['cruise_altitude_m'] / 3 / 60
    t_cruise = (distance_km * 2) / (cruise_speed * 0.001) / 60

    # 能耗
    E_ascent = P_ascent * t_ascent / 60
    E_descent = P_descent * t_descent / 60
    E_cruise = P_cruise * t_cruise / 60

    return E_ascent + E_cruise + E_descent


def advanced_knapsack(cargos, max_weight, max_volume, max_energy, uav_type):
    """
    高级背包算法：考虑货箱价值和能耗约束
    目标：最大化装载货箱数
    """
    n = len(cargos)
    if n == 0:
        return []

    # 按价值密度排序（重量+体积的综合密度）
    cargo_list = []
    for i, cargo in enumerate(cargos):
        density = 1.0 / (cargo['weight'] + cargo['volume'] * 100)  # 价值密度
        cargo_list.append({
            'index': i,
            'cargo': cargo,
            'density': density
        })

    cargo_list.sort(key=lambda x: x['density'], reverse=True)

    # 贪心+回溯
    best_solution = []
    best_count = 0

    def backtrack(idx, current_weight, current_volume, current_energy, current_solution):
        nonlocal best_solution, best_count

        if len(current_solution) > best_count:
            best_solution = current_solution.copy()
            best_count = len(current_solution)

        if idx >= len(cargo_list):
            return

        # 剪枝：剩余货物数量不足以超过当前最优解
        if len(current_solution) + (len(cargo_list) - idx) <= best_count:
            return

        # 尝试选择当前货箱
        cargo_info = cargo_list[idx]
        cargo = cargo_info['cargo']

        new_weight = current_weight + cargo['weight']
        new_volume = current_volume + cargo['volume']
        new_energy = cargo['energy']  # 简化：直接使用预计算能耗

        if (new_weight <= max_weight and
            new_volume <= max_volume and
            new_energy <= max_energy):
            # 选择
            backtrack(idx + 1, new_weight, new_volume, new_energy,
                     current_solution + [cargo_info['index']])

        # 不选择
        backtrack(idx + 1, current_weight, current_volume, current_energy,
                 current_solution)

    backtrack(0, 0, 0, 0, [])

    return [cargos[i] for i in best_solution]


def main():
    print("\n" + "="*80)
    print("问题一优化版 - 目标18架次")
    print("="*80)

    # 加载数据
    print("\n[步骤1] 加载数据...")
    data_dir = Path("数据/无人机应急物资运输基础数据")
    loader = DataLoader(data_dir)
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    uav_types = loader.get_uav_types()
    cargo_demand = loader.get_cargos()

    print(f"  服务区数量: {len(service_areas)}")
    print(f"  货箱总数: {len(cargo_demand)}")
    print(f"  无人机类型: {len(uav_types)}")

    # 按服务区分组货物
    print("\n[步骤2] 按服务区分组货物...")
    cargos_by_area = {}
    for _, cargo in cargo_demand.iterrows():
        area_id = cargo['服务区编号']
        if area_id not in cargos_by_area:
            cargos_by_area[area_id] = []
        cargos_by_area[area_id].append({
            'id': cargo['货箱编号'],
            'weight': cargo['单箱质量（kg）'],
            'volume': cargo['单箱体积（m³）'],
            'priority': cargo['应急优先系数'],
            'category': cargo['物资类型']
        })

    depot_coord = (depot['longitude'], depot['latitude'])

    # 为每个服务区计算最优配送方案
    print("\n[步骤3] 优化每个服务区的配送方案...")
    print("  策略: 优先使用大型无人机，最大化装载")

    results = []
    total_missions = 0

    for area_id in sorted(cargos_by_area.keys()):
        cargos = cargos_by_area[area_id]
        area_info = service_areas[service_areas['id'] == area_id].iloc[0]
        area_coord = (area_info['longitude'], area_info['latitude'])
        distance = calculate_distance(depot_coord, area_coord)

        print(f"\n  处理 {area_id} ({len(cargos)}个货箱, {distance:.1f}km)...")

        remaining_cargos = cargos.copy()
        area_missions = []

        # 优先尝试C型（载重最大）
        for uav_type_name in ['C', 'B', 'A']:
            if not remaining_cargos:
                break

            uav_spec = uav_types[uav_types['type'] == uav_type_name].iloc[0]
            max_payload = uav_spec['max_payload_kg']
            max_volume = uav_spec['cargo_volume_m3']
            battery_capacity = uav_spec['battery_capacity_kwh']
            safety_margin = 0.20
            max_energy = battery_capacity * (1 - safety_margin)

            while remaining_cargos:
                # 为当前货箱计算能耗
                for cargo in remaining_cargos:
                    cargo['energy'] = calculate_flight_energy(
                        distance, cargo['weight'], uav_spec)

                # 使用高级背包算法
                selected = advanced_knapsack(
                    remaining_cargos, max_payload, max_volume, max_energy, uav_type_name)

                if not selected:
                    # 当前机型无法装载，尝试下一个机型
                    break

                # 计算实际能耗
                total_weight = sum(c['weight'] for c in selected)
                total_volume = sum(c['volume'] for c in selected)
                total_priority = sum(c['priority'] for c in selected)
                actual_energy = calculate_flight_energy(distance, total_weight, uav_spec)

                # 计算飞行时间
                cruise_speed = uav_spec['cruise_speed_m_s']
                altitude = uav_spec['cruise_altitude_m']
                t_ascent = altitude / 5
                t_descent = altitude / 3
                t_cruise = (distance * 2 * 1000) / cruise_speed
                flight_time = (t_ascent + t_cruise + t_descent) / 60

                mission = {
                    'area_id': area_id,
                    'area_name': area_info['name'],
                    'uav_type': uav_type_name,
                    'num_cargos': len(selected),
                    'cargo_ids': [c['id'] for c in selected],
                    'total_weight': total_weight,
                    'total_volume': total_volume,
                    'total_priority': total_priority,
                    'total_energy': actual_energy,
                    'flight_time': flight_time,
                    'distance': distance
                }

                area_missions.append(mission)
                total_missions += 1

                # 移除已装载的货箱
                selected_ids = set(c['id'] for c in selected)
                remaining_cargos = [c for c in remaining_cargos
                                   if c['id'] not in selected_ids]

                print(f"    架次{total_missions}: {uav_type_name}型, {len(selected)}箱, "
                      f"{total_weight:.1f}kg, {total_volume:.3f}m³, {actual_energy:.2f}kWh")

        results.extend(area_missions)

        if remaining_cargos:
            print(f"    警告: {area_id} 还有 {len(remaining_cargos)} 个货箱未分配！")

    # 统计结果
    print("\n" + "="*80)
    print("优化结果")
    print("="*80)

    total_cargos = sum(m['num_cargos'] for m in results)
    total_energy = sum(m['total_energy'] for m in results)

    print(f"\n[结果] 总架次: {len(results)}")
    print(f"[结果] 总货箱: {total_cargos}/80")
    print(f"[结果] 总能耗: {total_energy:.2f} kWh")

    # 按机型统计
    print("\n按机型统计:")
    for uav_type in ['A', 'B', 'C']:
        missions = [m for m in results if m['uav_type'] == uav_type]
        if missions:
            num_cargos = sum(m['num_cargos'] for m in missions)
            energy = sum(m['total_energy'] for m in missions)
            avg_cargos = num_cargos / len(missions)
            print(f"  {uav_type}型: {len(missions)}架次, {num_cargos}箱, "
                  f"平均{avg_cargos:.1f}箱/架次, {energy:.2f}kWh")

    # 对比
    print("\n" + "="*80)
    print("优化效果")
    print("="*80)

    baseline_missions = 32
    target_missions = 18

    improvement = (baseline_missions - len(results)) / baseline_missions * 100
    vs_target = len(results) - target_missions

    print(f"\nvs 原方案:")
    print(f"  架次: {baseline_missions} -> {len(results)} (减少{baseline_missions - len(results)}架次, {improvement:.1f}%)")

    print(f"\nvs 竞争对手目标:")
    if len(results) <= target_missions:
        print(f"  [WIN] 达到目标! {len(results)}架次 <= {target_missions}架次")
    else:
        print(f"  [WARN] 还需优化{vs_target}架次")

    # 保存结果
    print("\n[步骤4] 保存结果...")
    result_df = pd.DataFrame(results)
    output_file = Path("结果/问题一_18架次优化方案.xlsx")
    result_df.to_excel(output_file, index=False)
    print(f"  结果已保存: {output_file}")

    print("\n" + "="*80)
    print("求解完成!")
    print("="*80)

    return {
        'missions': len(results),
        'cargos': total_cargos,
        'energy': total_energy
    }


if __name__ == "__main__":
    result = main()
