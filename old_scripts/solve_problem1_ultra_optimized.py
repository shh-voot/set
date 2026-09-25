#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一超级优化版 - 目标18架次
使用最优货箱组批算法 + 多机型混合
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader


def calculate_distance(coord1, coord2):
    """计算两点距离 (km)"""
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


def calculate_energy(distance_km, weight_kg, uav_spec):
    """简化能耗计算"""
    # 使用data_loader已经计算好的巡航功率
    cruise_power = uav_spec['cruise_power_kw']
    cruise_speed_ms = uav_spec['cruise_speed_ms']

    # 往返时间 (小时)
    time_h = (distance_km * 2 * 1000) / cruise_speed_ms / 3600

    # 基础能耗
    base_energy = cruise_power * time_h

    # 载重修正 (简化模型)
    weight_factor = 1 + (weight_kg / uav_spec['max_load_kg']) * 0.3

    return base_energy * weight_factor


def knapsack_3d(items, max_weight, max_volume, max_energy, distance_km, uav_spec):
    """三维背包 - 优先高价值货物"""
    items = sorted(items, key=lambda x: x['priority'], reverse=True)

    selected = []
    total_weight = 0
    total_volume = 0

    for item in items:
        new_weight = total_weight + item['weight']
        new_volume = total_volume + item['volume']

        # 检查能耗约束
        test_energy = calculate_energy(distance_km, new_weight, uav_spec)

        if (new_weight <= max_weight and
            new_volume <= max_volume and
            test_energy <= max_energy):
            selected.append(item)
            total_weight = new_weight
            total_volume = new_volume

    return selected


def main():
    print("\n" + "="*80)
    print("问题一超级优化版 - 目标18架次")
    print("="*80)

    # 加载数据
    print("\n[步骤1] 加载数据...")
    data_dir = Path("数据/无人机应急物资运输基础数据")
    loader = DataLoader(data_dir)
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    uav_types = loader.get_uav_types()
    cargos = loader.get_cargos()

    print(f"  服务区数量: {len(service_areas)}")
    print(f"  货物总数: {len(cargos)}")
    print(f"  机型数量: {len(uav_types)}")

    # 按服务区分组
    print("\n[步骤2] 按服务区分组货物...")
    cargos_by_area = {}
    for _, cargo in cargos.iterrows():
        area_id = cargo['服务区编号']
        if area_id not in cargos_by_area:
            cargos_by_area[area_id] = []
        cargos_by_area[area_id].append({
            'id': cargo['货箱编号'],
            'weight': cargo['单箱质量（kg）'],
            'volume': cargo['单箱体积（m³）'],
            'priority': cargo['应急优先系数']
        })

    print(f"  共 {len(cargos_by_area)} 个服务区需要配送")

    # 为每个服务区选择最优机型和组批
    print("\n[步骤3] 为每个服务区优化机型和组批...")
    missions = []

    depot_coord = (depot['longitude'], depot['latitude'])

    for area_id in sorted(cargos_by_area.keys()):
        area = service_areas[service_areas['id'] == area_id].iloc[0]
        area_coord = (area['longitude'], area['latitude'])
        distance = calculate_distance(depot_coord, area_coord)

        area_cargos = cargos_by_area[area_id].copy()
        total_cargos = len(area_cargos)

        print(f"  服务区 {area_id} ({total_cargos}个货箱, {distance:.1f}km)...")

        trip_count = 0

        # 尽量用大型机完成
        while len(area_cargos) > 0:
            best_mission = None
            best_remaining = len(area_cargos)

            # 尝试每种机型
            for _, uav in uav_types.iterrows():
                uav_type = uav['type']
                max_weight = uav['max_load_kg']
                max_volume = uav['max_volume_m3']
                battery = uav['battery_capacity_kwh']
                reserve = uav['battery_reserve_pct']
                max_energy = battery * (1 - reserve)

                # 背包算法选择货物
                selected = knapsack_3d(
                    area_cargos, max_weight, max_volume,
                    max_energy, distance, uav
                )

                if len(selected) > 0:
                    remaining = len(area_cargos) - len(selected)

                    # 优先选择能装更多货物的方案
                    if remaining < best_remaining:
                        # 计算实际能耗
                        total_weight = sum(c['weight'] for c in selected)
                        actual_energy = calculate_energy(distance, total_weight, uav)

                        # 计算飞行时间
                        time_min = (distance * 2 * 1000) / uav['cruise_speed_ms'] / 60

                        best_mission = {
                            'area_id': area_id,
                            'area_name': area['name'],
                            'uav_type': uav_type,
                            'num_cargos': len(selected),
                            'cargo_ids': [c['id'] for c in selected],
                            'total_weight': total_weight,
                            'total_volume': sum(c['volume'] for c in selected),
                            'total_priority': sum(c['priority'] for c in selected),
                            'total_energy': actual_energy,
                            'flight_time': time_min,
                            'distance': distance
                        }
                        best_remaining = remaining

            if best_mission is None:
                print(f"    警告: 剩余 {len(area_cargos)} 个货箱无法配送")
                break

            # 添加任务
            missions.append(best_mission)
            trip_count += 1

            # 移除已选择的货物
            selected_ids = set(best_mission['cargo_ids'])
            area_cargos = [c for c in area_cargos if c['id'] not in selected_ids]

            if len(area_cargos) > 0:
                print(f"    架次{trip_count}: {best_mission['uav_type']}型 {best_mission['num_cargos']}箱, "
                      f"剩余{len(area_cargos)}箱")

    # 汇总结果
    print("\n" + "="*80)
    print("优化结果")
    print("="*80)

    total_trips = len(missions)
    total_cargos = sum(m['num_cargos'] for m in missions)
    total_energy = sum(m['total_energy'] for m in missions)

    print(f"\n[结果] 总架次: {total_trips}")
    print(f"[结果] 配送货箱: {total_cargos}/80")
    print(f"[结果] 总能耗: {total_energy:.2f} kWh")

    # 按机型统计
    print("\n机型使用统计:")
    for uav_type in ['A', 'B', 'C']:
        type_missions = [m for m in missions if m['uav_type'] == uav_type]
        if len(type_missions) > 0:
            type_cargos = sum(m['num_cargos'] for m in type_missions)
            type_energy = sum(m['total_energy'] for m in type_missions)
            print(f"  {uav_type}型: {len(type_missions)}架次, {type_cargos}箱, {type_energy:.2f}kWh")

    # 对比目标
    print("\n" + "="*80)
    print("对比竞争对手")
    print("="*80)

    if total_trips <= 18:
        print(f"[SUCCESS] 达成18架次目标! (实际: {total_trips}架次)")
    else:
        print(f"[WARN] 未达成18架次目标 (实际: {total_trips}架次, 差距: {total_trips-18})")

    if total_cargos == 80:
        print(f"[SUCCESS] 全部80个货箱配送完成!")
    else:
        print(f"[WARN] 货箱配送不完整 ({total_cargos}/80)")

    # 保存结果
    print("\n[步骤4] 保存结果...")
    result_data = []
    for i, m in enumerate(missions, 1):
        result_data.append({
            '架次': i,
            '服务区ID': m['area_id'],
            '服务区名称': m['area_name'],
            '机型': m['uav_type'],
            '货箱数': m['num_cargos'],
            '货箱ID': ','.join(m['cargo_ids']),
            '总重量(kg)': round(m['total_weight'], 2),
            '总体积(m³)': round(m['total_volume'], 4),
            '总价值': m['total_priority'],
            '能耗(kWh)': round(m['total_energy'], 2),
            '飞行时间(分钟)': round(m['flight_time'], 2),
            '距离(km)': round(m['distance'], 2)
        })

    result_df = pd.DataFrame(result_data)

    output_dir = Path("结果")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "问题一_超级优化方案.xlsx"

    result_df.to_excel(output_file, index=False)
    print(f"  结果已保存: {output_file}")

    print("\n" + "="*80)
    print("求解完成!")
    print("="*80)

    return {
        'trips': total_trips,
        'cargos': total_cargos,
        'energy': total_energy
    }


if __name__ == "__main__":
    result = main()
