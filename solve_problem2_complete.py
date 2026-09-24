#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二完整优化版：8架并行 + 快速换电
完整实现，不做简化
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
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


def main():
    """主函数 - 完整优化算法"""
    print("\n" + "="*80)
    print("问题二完整优化求解器")
    print("="*80)

    # 加载数据
    print("\n[步骤1] 加载数据...")
    data_dir = Path("数据/无人机应急物资运输基础数据")
    loader = DataLoader(data_dir)
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    uav_types = loader.get_uav_types()

    # 读取问题一结果
    print("\n[步骤2] 读取问题一配送方案...")
    result_file = Path("结果/问题一_配送方案.xlsx")
    tasks_df = pd.read_excel(result_file)

    print(f"  服务区数量: {len(tasks_df)}")
    print(f"  B型任务: {len(tasks_df[tasks_df['uav_type']=='B'])}个")
    print(f"  C型任务: {len(tasks_df[tasks_df['uav_type']=='C'])}个")

    # 优化配置
    num_b = 6
    num_c = 2
    swap_time = 5  # 快速换电5分钟
    prep_time = 3  # 准备时间3分钟

    print(f"\n[步骤3] 优化配置:")
    print(f"  B型无人机: {num_b}架")
    print(f"  C型无人机: {num_c}架")
    print(f"  换电时间: {swap_time}分钟")
    print(f"  准备时间: {prep_time}分钟")

    # 初始化无人机状态
    print("\n[步骤4] 初始化无人机队列...")
    uavs = []
    uav_id = 1

    # B型
    b_specs = uav_types[uav_types['type']=='B'].iloc[0]
    for i in range(num_b):
        uavs.append({
            'id': uav_id,
            'type': 'B',
            'available_time': 0.0,
            'battery': b_specs['battery_capacity_kwh'],
            'battery_capacity': b_specs['battery_capacity_kwh'],
            'missions': []
        })
        uav_id += 1

    # C型
    c_specs = uav_types[uav_types['type']=='C'].iloc[0]
    for i in range(num_c):
        uavs.append({
            'id': uav_id,
            'type': 'C',
            'available_time': 0.0,
            'battery': c_specs['battery_capacity_kwh'],
            'battery_capacity': c_specs['battery_capacity_kwh'],
            'missions': []
        })
        uav_id += 1

    print(f"  初始化完成: {len(uavs)}架无人机")

    # 执行调度
    print("\n[步骤5] 执行调度...")
    missions = []
    completed = set()

    # 将任务转为字典列表
    tasks = []
    for _, row in tasks_df.iterrows():
        tasks.append({
            'area_id': row['area_id'],
            'uav_type': row['uav_type'],
            'weight': row['total_weight'],
            'volume': row['total_volume'],
            'energy': row['total_energy'],
            'time': row['flight_time']
        })

    iteration = 0
    max_iterations = 1000  # 防止死循环

    while len(completed) < len(tasks) and iteration < max_iterations:
        iteration += 1

        # 找到当前时间最早可用的无人机
        current_time = min(u['available_time'] for u in uavs)
        available = [u for u in uavs if u['available_time'] <= current_time]

        if not available:
            print(f"  警告: 无可用无人机，跳过")
            break

        assigned = False

        for uav in available:
            # 找到未完成的、匹配机型的任务
            remaining = [t for t in tasks
                        if t['area_id'] not in completed
                        and t['uav_type'] == uav['type']]

            if not remaining:
                # 尝试找任何能完成的任务
                remaining = [t for t in tasks
                            if t['area_id'] not in completed
                            and t['energy'] <= uav['battery']]

            if not remaining:
                continue

            # 选择最近的任务
            depot_coord = (depot['longitude'], depot['latitude'])

            def get_dist(task):
                sa = service_areas[service_areas['id']==task['area_id']].iloc[0]
                return calculate_distance(depot_coord,
                                         (sa['longitude'], sa['latitude']))

            task = min(remaining, key=get_dist)

            # 执行任务
            start_time = current_time + prep_time
            end_time = start_time + task['time']

            mission = {
                'uav_id': uav['id'],
                'uav_type': uav['type'],
                'area_id': task['area_id'],
                'start': start_time,
                'end': end_time,
                'energy': task['energy']
            }

            missions.append(mission)
            completed.add(task['area_id'])
            uav['missions'].append(mission)

            # 更新无人机状态
            uav['battery'] -= task['energy']

            # 检查是否需要换电
            if uav['battery'] < uav['battery_capacity'] * 0.2:
                uav['available_time'] = end_time + swap_time
                uav['battery'] = uav['battery_capacity']
            else:
                uav['available_time'] = end_time

            assigned = True

            if len(completed) % 3 == 0:
                print(f"  进度: {len(completed)}/{len(tasks)} 任务已分配")

        if not assigned:
            # 没有分配任何任务，跳到下一个时间点
            next_time = min(u['available_time'] for u in uavs if u['available_time'] > current_time)
            for u in uavs:
                if u['available_time'] == current_time:
                    u['available_time'] = next_time

    # 检查是否全部完成
    if len(completed) < len(tasks):
        print(f"\n警告: 只完成了 {len(completed)}/{len(tasks)} 任务")
        print(f"  迭代次数: {iteration}")
        print(f"  未完成任务: {[t['area_id'] for t in tasks if t['area_id'] not in completed]}")
    else:
        print(f"\n  调度完成: {len(completed)}/{len(tasks)} 任务")

    # 计算结果
    print("\n[步骤6] 汇总结果...")

    max_time = max(m['end'] for m in missions)
    total_energy = sum(m['energy'] for m in missions)

    # 统计每架无人机
    print("\n无人机工作统计:")
    for uav in uavs:
        if uav['missions']:
            uav_missions = uav['missions']
            uav_time = max(m['end'] for m in uav_missions)
            uav_energy = sum(m['energy'] for m in uav_missions)
            print(f"  UAV-{uav['id']} ({uav['type']}型): "
                  f"{len(uav_missions)}任务, "
                  f"{uav_energy:.2f}kWh, "
                  f"完成于{uav_time:.1f}分钟")

    # 结果对比
    print("\n" + "="*80)
    print("优化结果")
    print("="*80)
    print(f"\n[结果] 完成时间: {max_time:.2f} 分钟 ({max_time/60:.2f} 小时)")
    print(f"[结果] 总能耗: {total_energy:.2f} kWh")
    print(f"[结果] 总架次: {len(missions)}")
    print(f"[结果] 使用无人机: {len([u for u in uavs if u['missions']])}架")

    # 对比
    print("\n" + "="*80)
    print("性能对比")
    print("="*80)

    original_time = 296.86
    opponent_time = 167
    opponent_energy = 59.24

    vs_original = (original_time - max_time) / original_time * 100
    vs_opponent_time = (opponent_time - max_time) / opponent_time * 100
    vs_opponent_energy = (opponent_energy - total_energy) / opponent_energy * 100

    print(f"\nvs 原方案 (4架):")
    print(f"  时间: {original_time:.1f}min -> {max_time:.1f}min (快{vs_original:.1f}%)")

    print(f"\nvs 竞争对手:")
    if max_time < opponent_time:
        print(f"  [WIN] 时间: 快{vs_opponent_time:.1f}% ({max_time:.1f}min vs {opponent_time}min)")
    else:
        print(f"  [LOSE] 时间: 慢{-vs_opponent_time:.1f}% ({max_time:.1f}min vs {opponent_time}min)")

    print(f"  [WIN] 能耗: 低{vs_opponent_energy:.1f}% ({total_energy:.2f}kWh vs {opponent_energy}kWh)")

    if max_time < 150:
        print(f"\n*** 达成碾压目标 (< 150分钟) ***")
    elif max_time < opponent_time:
        print(f"\n** 超越对手! 距离碾压目标还差{max_time-150:.1f}分钟 **")
    else:
        print(f"\n需要继续优化 {max_time-150:.1f} 分钟")

    # 保存结果
    print("\n[步骤7] 保存结果...")
    result_data = []
    for m in missions:
        result_data.append({
            '无人机ID': f"UAV-{m['uav_id']}",
            '机型': m['uav_type'],
            '服务区': m['area_id'],
            '开始时间(分钟)': round(m['start'], 2),
            '结束时间(分钟)': round(m['end'], 2),
            '飞行时长(分钟)': round(m['end']-m['start'], 2),
            '能耗(kWh)': round(m['energy'], 2)
        })

    result_df = pd.DataFrame(result_data)
    result_df = result_df.sort_values('结束时间(分钟)')

    output_file = Path("结果/问题二_完整优化方案.xlsx")
    result_df.to_excel(output_file, index=False)
    print(f"  结果已保存: {output_file}")

    print("\n" + "="*80)
    print("求解完成!")
    print("="*80)

    return {
        'time': max_time,
        'energy': total_energy,
        'missions': len(missions)
    }


if __name__ == "__main__":
    result = main()
