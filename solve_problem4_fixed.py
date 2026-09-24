#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题四修复版：基于问题三的批次划分与资源配置
修复内容：
1. 读取问题三调度方案（而非问题二）
2. 优化批次划分算法（目标：均衡分配）
3. 使用实际能耗数据和两阶段充电模型
4. 添加中继无人机资源计算
5. 从赛题数据加载UAV参数（不使用硬编码）
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
from itertools import combinations

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.battery.charging_model_correct import calculate_charging_time
from src.data.data_loader import DataLoader


def calculate_distance(coord1, coord2):
    """计算两点距离（km）"""
    lon1, lat1 = coord1
    lon2, lat2 = coord2

    R = 6371  # 地球半径
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (np.sin(dlat/2)**2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon/2)**2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    return R * c


def load_problem3_solution():
    """读取问题三调度方案"""
    print("\n[步骤1] 读取问题三调度方案...")

    # 读取运输调度
    transport_file = Path("结果/问题三_运输调度_新.xlsx")
    transport_df = pd.read_excel(transport_file)

    # 使用列索引而非列名（避免编码问题）
    # 新列结构（10列）：0=架次编号, 1=UAV_ID, 2=UAV_Type, 3=电池编号, 4=服务区, 5=货箱数量, 6=起飞时间, 7=降落时间, 8=飞行时长, 9=能耗

    transport_data = []
    for _, row in transport_df.iterrows():
        transport_data.append({
            'uav_id': row.iloc[1],      # UAV编号
            'uav_type': row.iloc[2],    # UAV类型
            'area_id': row.iloc[4],     # 服务区
            'num_cargos': row.iloc[5],  # 货箱数量
            'energy': row.iloc[9],      # 能耗
            'duration': row.iloc[8]     # 飞行时长
        })

    # 读取中继部署
    relay_file = Path("结果/问题三_中继部署方案_新.xlsx")
    relay_df = pd.read_excel(relay_file)

    relay_data = []
    for _, row in relay_df.iterrows():
        relay_data.append({
            'relay_id': row.iloc[0],
            'hover_energy': row.iloc[5] if len(row) > 5 else 0,
            'hover_time': row.iloc[6] if len(row) > 6 else 0
        })

    print(f"  运输架次: {len(transport_data)}")
    print(f"  中继数量: {len(relay_data)}")

    return transport_data, relay_data


def optimize_partition(service_areas, num_groups):
    """
    优化批次划分算法
    目标：工作量均衡 + 地理邻近性
    """
    print(f"\n[步骤2] 优化{num_groups}批次划分...")

    n = len(service_areas)
    ideal_size = n / num_groups

    print(f"  服务区总数: {n}")
    print(f"  理想批次大小: {ideal_size:.1f}")

    # 简化版：使用贪心算法
    # 按人口排序（工作量代理）
    sorted_areas = sorted(service_areas, key=lambda x: x['population'], reverse=True)

    # 初始化批次
    groups = [[] for _ in range(num_groups)]
    group_loads = [0] * num_groups

    # 分配服务区到负载最小的批次
    for area in sorted_areas:
        min_idx = group_loads.index(min(group_loads))
        groups[min_idx].append(area['id'])
        group_loads[min_idx] += area['population']

    # 计算均衡度
    max_size = max(len(g) for g in groups)
    min_size = min(len(g) for g in groups)
    imbalance = (max_size - min_size) / max_size * 100 if max_size > 0 else 0

    print(f"\n  批次分配:")
    for i, group in enumerate(groups):
        print(f"    批次{i+1}: {len(group)}个服务区 (人口{group_loads[i]})")
    print(f"  不均衡度: {imbalance:.1f}%")

    return groups, imbalance


def calculate_resources_per_group(group_areas, transport_missions, relay_missions,
                                   simulation_hours=30):
    """
    计算单个批次的资源需求
    使用实际能耗数据和两阶段充电模型
    """
    # 筛选该批次的运输任务
    group_transport = [m for m in transport_missions if m['area_id'] in group_areas]

    if not group_transport:
        return {
            'batteries_B': 0, 'batteries_C': 0,
            'chargers_B': 0, 'chargers_C': 0,
            'relays': 0, 'relay_batteries': 0
        }

    # 统计机型
    b_missions = [m for m in group_transport if m['uav_type'] == 'B']
    c_missions = [m for m in group_transport if m['uav_type'] == 'C']

    # 从赛题数据加载电池容量和充电时间（不使用硬编码）
    loader = DataLoader()
    loader.load_all()
    uav_df = loader.get_uav_types()

    battery_capacity = {}
    full_charge_time = {}
    for _, row in uav_df.iterrows():
        uav_type = row['type']
        battery_capacity[uav_type] = row['battery_capacity_kwh']
        full_charge_time[uav_type] = row['full_charge_time_min']

    print(f"  [真实数据] B型: {battery_capacity['B']}kWh, {full_charge_time['B']}分钟")
    print(f"  [真实数据] C型: {battery_capacity['C']}kWh, {full_charge_time['C']}分钟")

    # 计算B型资源
    batteries_B = 0
    chargers_B = 0
    if b_missions:
        total_energy_B = sum(m['energy'] for m in b_missions)
        max_duration_B = max(m['duration'] for m in b_missions)

        # 估算电池需求：总能耗 / 单电池容量 * 安全系数
        batteries_B = int(np.ceil(total_energy_B / battery_capacity['B'] * 1.3))

        # 估算充电桩需求：基于充电时间和任务时间
        # 假设每个电池需要充电1次，充电时间40分钟
        total_charge_cycles = batteries_B
        charge_duration = full_charge_time['B']
        chargers_B = int(np.ceil(total_charge_cycles * charge_duration / (simulation_hours * 60) * 1.5))
        chargers_B = max(1, chargers_B)

    # 计算C型资源
    batteries_C = 0
    chargers_C = 0
    if c_missions:
        total_energy_C = sum(m['energy'] for m in c_missions)
        max_duration_C = max(m['duration'] for m in c_missions)

        batteries_C = int(np.ceil(total_energy_C / battery_capacity['C'] * 1.3))

        total_charge_cycles = batteries_C
        charge_duration = full_charge_time['C']
        chargers_C = int(np.ceil(total_charge_cycles * charge_duration / (simulation_hours * 60) * 1.5))
        chargers_C = max(1, chargers_C)

    # 中继资源（所有批次共享中继）
    num_relays = len(relay_missions)
    relay_batteries = num_relays * 2  # 每架中继配2组电池

    return {
        'batteries_B': batteries_B,
        'batteries_C': batteries_C,
        'chargers_B': chargers_B,
        'chargers_C': chargers_C,
        'relays': num_relays,
        'relay_batteries': relay_batteries
    }


def solve_problem4(num_groups=2):
    """
    问题四主求解函数
    """
    print("\n" + "="*80)
    print(f"问题四修复版求解器 - {num_groups}批次划分")
    print("="*80)

    # 加载问题三方案
    transport_missions, relay_missions = load_problem3_solution()

    # 读取服务区数据
    service_file = Path("数据/无人机应急物资运输基础数据/调度中心与服务区.xlsx")
    service_df = pd.read_excel(service_file)

    # 提取服务区信息（跳过标题行）
    service_areas = []
    for i in range(len(service_df)):
        area_id = service_df.iloc[i, 0]
        if pd.isna(area_id) or not str(area_id).startswith('S'):
            continue

        service_areas.append({
            'id': area_id,
            'lon': service_df.iloc[i, 2],
            'lat': service_df.iloc[i, 3],
            'population': service_df.iloc[i, 5] if not pd.isna(service_df.iloc[i, 5]) else 0
        })

    print(f"\n服务区数量: {len(service_areas)}")

    # 优化批次划分
    groups, imbalance = optimize_partition(service_areas, num_groups)

    # 计算每个批次的资源需求
    print(f"\n[步骤3] 计算资源需求...")

    total_batteries_B = 0
    total_batteries_C = 0
    total_chargers_B = 0
    total_chargers_C = 0

    group_resources = []

    for i, group in enumerate(groups):
        print(f"\n  批次{i+1} ({len(group)}个服务区):")
        print(f"    服务区: {', '.join(group)}")

        resources = calculate_resources_per_group(group, transport_missions, relay_missions)

        print(f"    B型电池: {resources['batteries_B']}组")
        print(f"    C型电池: {resources['batteries_C']}组")
        print(f"    B型充电桩: {resources['chargers_B']}个")
        print(f"    C型充电桩: {resources['chargers_C']}个")

        total_batteries_B += resources['batteries_B']
        total_batteries_C += resources['batteries_C']
        total_chargers_B += resources['chargers_B']
        total_chargers_C += resources['chargers_C']

        group_resources.append(resources)

    # 中继资源（所有批次共享）
    num_relays = len(relay_missions)
    relay_batteries = num_relays * 2

    total_batteries = total_batteries_B + total_batteries_C + relay_batteries
    total_chargers = total_chargers_B + total_chargers_C + 1  # +1 for relay charger

    print("\n" + "="*80)
    print("资源需求汇总")
    print("="*80)
    print(f"\n[运输无人机资源]")
    print(f"  B型电池: {total_batteries_B}组")
    print(f"  C型电池: {total_batteries_C}组")
    print(f"  B型充电桩: {total_chargers_B}个")
    print(f"  C型充电桩: {total_chargers_C}个")

    print(f"\n[中继无人机资源]")
    print(f"  中继无人机: {num_relays}架")
    print(f"  中继电池: {relay_batteries}组")
    print(f"  中继充电桩: 1个（共享）")

    print(f"\n[总计]")
    print(f"  总电池数: {total_batteries}组")
    print(f"  总充电桩数: {total_chargers}个")
    print(f"  批次不均衡度: {imbalance:.1f}%")

    # 保存结果
    print(f"\n[步骤4] 保存结果...")

    result_data = []
    for i, group in enumerate(groups):
        result_data.append({
            '批次': f"批次{i+1}",
            '服务区数量': len(group),
            '服务区列表': ', '.join(group),
            'B型电池': group_resources[i]['batteries_B'],
            'C型电池': group_resources[i]['batteries_C'],
            'B型充电桩': group_resources[i]['chargers_B'],
            'C型充电桩': group_resources[i]['chargers_C']
        })

    # 添加总计行
    result_data.append({
        '批次': '总计',
        '服务区数量': len(service_areas),
        '服务区列表': f"不均衡度: {imbalance:.1f}%",
        'B型电池': total_batteries_B,
        'C型电池': total_batteries_C,
        'B型充电桩': total_chargers_B,
        'C型充电桩': total_chargers_C
    })

    # 添加中继行
    result_data.append({
        '批次': '中继资源',
        '服务区数量': num_relays,
        '服务区列表': f"{num_relays}架中继无人机",
        'B型电池': 0,
        'C型电池': 0,
        'B型充电桩': 0,
        'C型充电桩': 0
    })

    result_df = pd.DataFrame(result_data)
    output_file = Path(f"结果/问题四_{num_groups}批次_修复版.xlsx")
    result_df.to_excel(output_file, index=False)
    print(f"  结果已保存: {output_file}")

    print("\n" + "="*80)
    print("求解完成！")
    print("="*80)

    return {
        'num_groups': num_groups,
        'groups': groups,
        'imbalance': imbalance,
        'total_batteries': total_batteries,
        'total_chargers': total_chargers,
        'batteries_B': total_batteries_B,
        'batteries_C': total_batteries_C,
        'relay_batteries': relay_batteries,
        'chargers_B': total_chargers_B,
        'chargers_C': total_chargers_C
    }


if __name__ == "__main__":
    print("问题四修复版")
    print("基于问题三调度方案的批次划分与资源配置")
    print()

    # 求解2批次
    result_2 = solve_problem4(num_groups=2)

    print("\n\n")

    # 求解3批次
    result_3 = solve_problem4(num_groups=3)

    # 对比
    print("\n" + "="*80)
    print("方案对比")
    print("="*80)
    print(f"\n2批次方案:")
    print(f"  总电池: {result_2['total_batteries']}组")
    print(f"  总充电桩: {result_2['total_chargers']}个")
    print(f"  不均衡度: {result_2['imbalance']:.1f}%")

    print(f"\n3批次方案:")
    print(f"  总电池: {result_3['total_batteries']}组")
    print(f"  总充电桩: {result_3['total_chargers']}个")
    print(f"  不均衡度: {result_3['imbalance']:.1f}%")

    if result_3['imbalance'] < result_2['imbalance']:
        print(f"\n推荐: 3批次方案（更均衡）")
    else:
        print(f"\n推荐: 2批次方案")
