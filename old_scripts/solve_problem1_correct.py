#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一：符合赛题约束的求解器
严格满足：
1. 80箱完整配送
2. B型载重≤30kg
3. 体积≤0.25m³
4. 单服务区往返
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.data.data_loader import DataLoader


def calculate_distance(coord1, coord2):
    """计算两点距离（km）- Haversine公式"""
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    R = 6371  # 地球半径(km)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (np.sin(dlat/2)**2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon/2)**2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    return R * c


def expand_cargo_from_summary(summary_df):
    """从汇总表展开成80个独立货箱"""
    boxes = []
    box_id = 1

    for idx, row in summary_df.iterrows():
        total_boxes = int(row['总需求箱数'])
        first_batch = int(row['首批必须送达箱数'])

        for i in range(total_boxes):
            is_first = i < first_batch

            boxes.append({
                'cargo_id': f'C{box_id:03d}',
                'area_id': row['服务区编号'],
                'type': row['物资类型'],
                'weight': row['单箱质量（kg）'],
                'volume': row['单箱体积（m³）'],
                'priority': row['应急优先系数'],
                'is_first_batch': is_first,
                'deadline': row['首批截止时间（s）'] if is_first else row['期望送达时间（s）']
            })
            box_id += 1

    return pd.DataFrame(boxes)


def bin_packing_ffd(items, weight_limit=30, volume_limit=0.25):
    """
    First-Fit Decreasing装箱算法
    双约束：重量≤30kg AND 体积≤0.25m³
    """
    # 按重量降序排序
    sorted_items = sorted(items, key=lambda x: x['weight'], reverse=True)

    bins = []  # 每个bin是一个货箱列表

    for item in sorted_items:
        # 尝试放入现有bin
        placed = False

        for bin in bins:
            bin_weight = sum(b['weight'] for b in bin)
            bin_volume = sum(b['volume'] for b in bin)

            # 检查是否可以放入
            if (bin_weight + item['weight'] <= weight_limit and
                bin_volume + item['volume'] <= volume_limit):
                bin.append(item)
                placed = True
                break

        # 如果放不下，开新bin
        if not placed:
            bins.append([item])

    return bins


def solve_problem1():
    """求解问题一"""
    print("="*80)
    print("问题一求解器 - 严格符合赛题约束版本")
    print("="*80)

    # 加载数据
    print("\n[步骤1] 加载基础数据...")
    data_dir = Path("数据/无人机应急物资运输基础数据")
    loader = DataLoader(data_dir)
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    uav_types = loader.get_uav_types()

    # 读取物资需求
    cargo_summary = pd.read_excel(data_dir / "物资需求与配送时限.xlsx")

    print(f"  服务区数: {len(service_areas)}")
    print(f"  物资汇总行数: {len(cargo_summary)}")

    # 展开成80箱
    print("\n[步骤2] 展开货箱清单...")
    cargo_df = expand_cargo_from_summary(cargo_summary)

    print(f"  独立货箱数: {len(cargo_df)}")
    print(f"  总重量: {cargo_df['weight'].sum():.2f} kg")
    print(f"  总体积: {cargo_df['volume'].sum():.3f} m3")

    # 理论最少架次
    theoretical_min_weight = np.ceil(cargo_df['weight'].sum() / 30)
    theoretical_min_volume = np.ceil(cargo_df['volume'].sum() / 0.25)
    theoretical_min = int(max(theoretical_min_weight, theoretical_min_volume))

    print(f"\n[步骤3] 理论分析:")
    print(f"  按重量: {theoretical_min_weight:.0f}架次")
    print(f"  按体积: {theoretical_min_volume:.0f}架次")
    print(f"  理论下限: {theoretical_min}架次")

    # B型参数
    b_type = uav_types[uav_types['type'] == 'B'].iloc[0]

    print(f"\n[步骤4] B型无人机参数:")
    print(f"  载重限制: {b_type['max_load_kg']} kg")
    print(f"  体积限制: {b_type['max_volume_m3']} m3")

    # 实际可用限制
    effective_weight_limit = 30  # 赛题单程最大载荷
    effective_volume_limit = min(b_type['max_volume_m3'], 0.25)

    print(f"  实际载重限制: {effective_weight_limit} kg")
    print(f"  实际体积限制: {effective_volume_limit} m3")

    # 按服务区分组装箱
    print("\n[步骤5] 按服务区执行装箱...")

    all_trips = []
    trip_id = 1

    for area_id in sorted(cargo_df['area_id'].unique()):
        area_cargo = cargo_df[cargo_df['area_id'] == area_id].to_dict('records')

        print(f"\n  {area_id}: {len(area_cargo)}箱, "
              f"{sum(c['weight'] for c in area_cargo):.1f}kg, "
              f"{sum(c['volume'] for c in area_cargo):.3f}m3")

        # FFD装箱
        bins = bin_packing_ffd(area_cargo,
                              weight_limit=effective_weight_limit,
                              volume_limit=effective_volume_limit)

        print(f"    装箱结果: {len(bins)}架次")

        # 生成架次记录
        for bin_idx, bin_cargo in enumerate(bins):
            bin_weight = sum(c['weight'] for c in bin_cargo)
            bin_volume = sum(c['volume'] for c in bin_cargo)
            cargo_ids = [c['cargo_id'] for c in bin_cargo]

            # 验证约束
            assert bin_weight <= effective_weight_limit, f"超重: {bin_weight}kg"
            assert bin_volume <= effective_volume_limit, f"超体积: {bin_volume}m3"

            # 计算距离
            area_info = service_areas[service_areas['id'] == area_id].iloc[0]
            distance = calculate_distance(
                (depot['longitude'], depot['latitude']),
                (area_info['longitude'], area_info['latitude'])
            )

            # 简化能耗模型（基于巡航功率和速度）
            # 往返距离（km）
            round_trip_distance = 2 * distance
            # 巡航时间（小时）
            cruise_speed_kmh = b_type['cruise_speed_ms'] * 3.6
            cruise_time_h = round_trip_distance / cruise_speed_kmh
            # 巡航能耗（kWh）
            cruise_energy = cruise_time_h * b_type['cruise_power_kw']

            # 爬升下降能耗（简化估算，假设高度500m）
            altitude_energy = 0.5  # kWh

            # 总能耗
            energy = cruise_energy + altitude_energy

            # 飞行时间（往返，分钟）
            flight_time = cruise_time_h * 60

            all_trips.append({
                'trip_id': trip_id,
                'area_id': area_id,
                'cargo_count': len(bin_cargo),
                'cargo_ids': '、'.join(cargo_ids),
                'total_weight': bin_weight,
                'total_volume': bin_volume,
                'distance_km': distance,
                'energy_kwh': energy,
                'flight_time_min': flight_time,
                'weight_util': bin_weight / effective_weight_limit * 100,
                'volume_util': bin_volume / effective_volume_limit * 100
            })

            print(f"      架次{trip_id}: {len(bin_cargo)}箱, "
                  f"{bin_weight:.1f}kg({bin_weight/30*100:.0f}%), "
                  f"{bin_volume:.3f}m3({bin_volume/0.25*100:.0f}%)")

            trip_id += 1

    # 汇总结果
    result_df = pd.DataFrame(all_trips)

    print("\n" + "="*80)
    print("求解完成")
    print("="*80)

    total_trips = len(result_df)
    total_energy = result_df['energy_kwh'].sum()
    total_time = result_df['flight_time_min'].sum()
    avg_weight_util = result_df['weight_util'].mean()
    avg_volume_util = result_df['volume_util'].mean()

    print(f"\n总架次数: {total_trips}")
    print(f"总能耗: {total_energy:.2f} kWh")
    print(f"总飞行时间: {total_time:.2f} 分钟")
    print(f"平均重量利用率: {avg_weight_util:.1f}%")
    print(f"平均体积利用率: {avg_volume_util:.1f}%")

    print(f"\n与理论对比:")
    print(f"  理论下限: {theoretical_min}架次")
    print(f"  实际结果: {total_trips}架次")
    print(f"  装箱损失: {(total_trips - theoretical_min) / theoretical_min * 100:.1f}%")

    # 约束验证
    print(f"\n约束验证:")
    max_weight = result_df['total_weight'].max()
    max_volume = result_df['total_volume'].max()

    print(f"  最大载重: {max_weight:.2f} kg (限制30kg) {'OK' if max_weight <= 30 else 'FAIL'}")
    print(f"  最大体积: {max_volume:.3f} m3 (限制0.25m3) {'OK' if max_volume <= 0.25 else 'FAIL'}")
    print(f"  货箱总数: {cargo_df['cargo_id'].nunique()}箱 {'OK' if cargo_df['cargo_id'].nunique() == 80 else 'FAIL'}")

    # 保存结果
    output_file = Path("结果/问题一_严格约束方案.xlsx")
    result_df.to_excel(output_file, index=False)
    print(f"\n结果已保存: {output_file}")

    return {
        'trips': total_trips,
        'energy': total_energy,
        'time': total_time,
        'theoretical_min': theoretical_min
    }


if __name__ == "__main__":
    result = solve_problem1()
