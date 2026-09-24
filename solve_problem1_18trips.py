#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一终极优化版 - 严格18架次
策略: 优先使用C型大载荷机型，强制合并小批次
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
    cruise_power = uav_spec['cruise_power_kw']
    cruise_speed_ms = uav_spec['cruise_speed_ms']
    time_h = (distance_km * 2 * 1000) / cruise_speed_ms / 3600
    base_energy = cruise_power * time_h
    weight_factor = 1 + (weight_kg / uav_spec['max_load_kg']) * 0.3
    return base_energy * weight_factor


def greedy_pack(items, max_weight, max_volume, max_energy, distance_km, uav_spec):
    """贪婪装箱 - 尽可能多装"""
    items = sorted(items, key=lambda x: x['priority'], reverse=True)

    selected = []
    total_weight = 0
    total_volume = 0

    for item in items:
        new_weight = total_weight + item['weight']
        new_volume = total_volume + item['volume']
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
    print("问题一终极优化版 - 严格18架次")
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

    print(f"  服务区: {len(service_areas)}个")
    print(f"  货物: {len(cargos)}个")

    # 获取C型机规格（最大载荷）
    c_spec = uav_types[uav_types['type'] == 'C'].iloc[0]
    b_spec = uav_types[uav_types['type'] == 'B'].iloc[0]

    print(f"\n机型规格:")
    print(f"  C型: 载重{c_spec['max_load_kg']}kg, 体积{c_spec['max_volume_m3']}m3, "
          f"电池{c_spec['battery_capacity_kwh']}kWh")
    print(f"  B型: 载重{b_spec['max_load_kg']}kg, 体积{b_spec['max_volume_m3']}m3, "
          f"电池{b_spec['battery_capacity_kwh']}kWh")

    # 按服务区分组
    print("\n[步骤2] 按服务区分组...")
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

    depot_coord = (depot['longitude'], depot['latitude'])

    # 优先使用C型机，每个服务区尽量1架次
    print("\n[步骤3] 优化组批（目标18架次）...")
    missions = []

    for area_id in sorted(cargos_by_area.keys()):
        area = service_areas[service_areas['id'] == area_id].iloc[0]
        area_coord = (area['longitude'], area['latitude'])
        distance = calculate_distance(depot_coord, area_coord)

        area_cargos = cargos_by_area[area_id].copy()
        num_cargos = len(area_cargos)

        print(f"\n  服务区 {area_id} ({num_cargos}箱, {distance:.1f}km)")

        trip = 0
        while len(area_cargos) > 0:
            trip += 1

            # 优先用C型（大载荷）
            uav = c_spec
            uav_type = 'C'

            max_weight = uav['max_load_kg']
            max_volume = uav['max_volume_m3']
            battery = uav['battery_capacity_kwh']
            reserve = uav['battery_reserve_pct']
            max_energy = battery * (1 - reserve)

            # 贪婪装箱
            selected = greedy_pack(
                area_cargos, max_weight, max_volume,
                max_energy, distance, uav
            )

            # 如果C型装不下，尝试B型
            if len(selected) == 0:
                uav = b_spec
                uav_type = 'B'
                max_weight = uav['max_load_kg']
                max_volume = uav['max_volume_m3']
                max_energy = uav['battery_capacity_kwh'] * (1 - uav['battery_reserve_pct'])

                selected = greedy_pack(
                    area_cargos, max_weight, max_volume,
                    max_energy, distance, uav
                )

            if len(selected) == 0:
                print(f"    警告: 剩余{len(area_cargos)}箱无法配送")
                break

            total_weight = sum(c['weight'] for c in selected)
            total_volume = sum(c['volume'] for c in selected)
            actual_energy = calculate_energy(distance, total_weight, uav)
            time_min = (distance * 2 * 1000) / uav['cruise_speed_ms'] / 60

            missions.append({
                'area_id': area_id,
                'area_name': area['name'],
                'uav_type': uav_type,
                'num_cargos': len(selected),
                'cargo_ids': [c['id'] for c in selected],
                'total_weight': total_weight,
                'total_volume': total_volume,
                'total_priority': sum(c['priority'] for c in selected),
                'total_energy': actual_energy,
                'flight_time': time_min,
                'distance': distance
            })

            print(f"    架次{trip}: {uav_type}型装载{len(selected)}箱 "
                  f"({total_weight:.1f}kg, {total_volume:.3f}m3, {actual_energy:.2f}kWh)")

            # 移除已选择的货物
            selected_ids = set(c['id'] for c in selected)
            area_cargos = [c for c in area_cargos if c['id'] not in selected_ids]

    # 汇总结果
    print("\n" + "="*80)
    print("优化结果")
    print("="*80)

    total_trips = len(missions)
    total_cargos = sum(m['num_cargos'] for m in missions)
    total_energy = sum(m['total_energy'] for m in missions)

    print(f"\n总架次: {total_trips}")
    print(f"配送货箱: {total_cargos}/80")
    print(f"总能耗: {total_energy:.2f} kWh")

    # 机型统计
    print("\n机型使用:")
    for uav_type in ['B', 'C']:
        type_missions = [m for m in missions if m['uav_type'] == uav_type]
        if len(type_missions) > 0:
            print(f"  {uav_type}型: {len(type_missions)}架次, "
                  f"{sum(m['num_cargos'] for m in type_missions)}箱, "
                  f"{sum(m['total_energy'] for m in type_missions):.2f}kWh")

    # 评估
    print("\n" + "="*80)
    print("目标评估")
    print("="*80)

    if total_trips <= 18:
        print(f"[SUCCESS] 达成18架次目标! (实际: {total_trips}架次)")
    else:
        print(f"[FAIL] 超过18架次目标 (实际: {total_trips}架次, 超出: {total_trips-18})")

    if total_cargos == 80:
        print(f"[SUCCESS] 全部80个货箱配送完成!")
    else:
        print(f"[FAIL] 货箱配送不完整 ({total_cargos}/80)")

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
    output_file = output_dir / "问题一_18架次方案.xlsx"
    result_df.to_excel(output_file, index=False)
    print(f"  结果已保存: {output_file}")

    # 服务区汇总
    area_summary = []
    for area_id in sorted(cargos_by_area.keys()):
        area_missions = [m for m in missions if m['area_id'] == area_id]
        area_summary.append({
            '服务区ID': area_id,
            '服务区名称': area_missions[0]['area_name'],
            '架次数': len(area_missions),
            '货箱总数': sum(m['num_cargos'] for m in area_missions),
            '总能耗(kWh)': round(sum(m['total_energy'] for m in area_missions), 2),
            '距离(km)': round(area_missions[0]['distance'], 2)
        })

    summary_df = pd.DataFrame(area_summary)
    summary_file = output_dir / "问题一_服务区汇总_18架次.xlsx"
    summary_df.to_excel(summary_file, index=False)
    print(f"  汇总已保存: {summary_file}")

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
