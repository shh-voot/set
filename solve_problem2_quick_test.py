#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二优化版：8架并行 + 快速换电策略（简化版）
目标：快速验证优化效果
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader


def main():
    """主函数 - 简化版快速测试"""
    print("\n" + "="*80)
    print("问题二优化求解器 - 简化快速版")
    print("="*80)

    # 加载数据
    print("\n加载数据...")
    data_dir = Path("数据/无人机应急物资运输基础数据")
    loader = DataLoader(data_dir)
    loader.load_all()

    # 读取问题一的结果
    print("\n读取问题一配送方案...")
    result_file = Path("结果/问题一_配送方案.xlsx")
    df = pd.read_excel(result_file)

    print(f"服务区数量: {len(df)}")
    print(f"总能耗: {df['total_energy'].sum():.2f} kWh")
    print(f"总飞行时间: {df['flight_time'].sum():.2f} 分钟")

    # 优化配置
    num_b_uavs = 6  # B型6架
    num_c_uavs = 2  # C型2架
    battery_swap_time = 5  # 快速换电5分钟

    print(f"\n优化配置:")
    print(f"  B型无人机: {num_b_uavs}架")
    print(f"  C型无人机: {num_c_uavs}架")
    print(f"  换电时间: {battery_swap_time}分钟")

    # 简化调度算法：平均分配
    print("\n执行优化调度...")

    # 分离B型和C型任务
    b_tasks = df[df['uav_type'] == 'B'].copy()
    c_tasks = df[df['uav_type'] == 'C'].copy()

    print(f"  B型任务: {len(b_tasks)}个")
    print(f"  C型任务: {len(c_tasks)}个")

    # B型任务平均分配给6架
    b_tasks_per_uav = len(b_tasks) // num_b_uavs
    b_remainder = len(b_tasks) % num_b_uavs

    # C型任务平均分配给2架
    c_tasks_per_uav = len(c_tasks) // num_c_uavs
    c_remainder = len(c_tasks) % num_c_uavs

    print(f"  B型每架平均: {b_tasks_per_uav}个任务")
    print(f"  C型每架平均: {c_tasks_per_uav}个任务")

    # 计算完成时间（简化模型：最繁忙无人机的时间）
    # B型最繁忙的无人机
    b_max_tasks = b_tasks_per_uav + (1 if b_remainder > 0 else 0)
    b_max_time = b_tasks.nlargest(b_max_tasks, 'flight_time')['flight_time'].sum()

    # 计算换电次数（假设每3次任务换电一次）
    b_swaps = max(0, b_max_tasks - 1) // 3
    b_total_time = b_max_time + b_swaps * battery_swap_time

    # C型最繁忙的无人机
    if len(c_tasks) > 0:
        c_max_tasks = c_tasks_per_uav + (1 if c_remainder > 0 else 0)
        c_max_time = c_tasks.nlargest(min(c_max_tasks, len(c_tasks)), 'flight_time')['flight_time'].sum()
        c_swaps = max(0, c_max_tasks - 1) // 3
        c_total_time = c_max_time + c_swaps * battery_swap_time
    else:
        c_total_time = 0

    # 最终完成时间
    max_completion_time = max(b_total_time, c_total_time)

    # 总能耗不变
    total_energy = df['total_energy'].sum()

    print("\n" + "="*80)
    print("优化结果")
    print("="*80)
    print(f"\n[OK] 完成时间: {max_completion_time:.2f} 分钟 ({max_completion_time/60:.2f} 小时)")
    print(f"[OK] 总能耗: {total_energy:.2f} kWh")
    print(f"[OK] 使用无人机: {num_b_uavs + num_c_uavs}架")
    print(f"[OK] B型换电次数: 约{b_swaps * num_b_uavs}次")

    # 对比
    print("\n" + "="*80)
    print("与对手对比")
    print("="*80)
    opponent_time = 167  # 对手时间
    opponent_energy = 59.24  # 对手能耗
    original_time = 296.86  # 原方案时间

    time_vs_opponent = (opponent_time - max_completion_time) / opponent_time * 100
    time_vs_original = (original_time - max_completion_time) / original_time * 100
    energy_vs_opponent = (opponent_energy - total_energy) / opponent_energy * 100

    print(f"\n相比原方案:")
    print(f"  时间: {original_time:.1f}分钟 → {max_completion_time:.1f}分钟 (快{time_vs_original:.1f}%)")

    print(f"\n相比对手:")
    if max_completion_time < opponent_time:
        print(f"  [WIN] 时间: 快{time_vs_opponent:.1f}% ({max_completion_time:.1f}分钟 vs {opponent_time}分钟)")
    else:
        print(f"  [WARN] 时间: 慢{-time_vs_opponent:.1f}% ({max_completion_time:.1f}分钟 vs {opponent_time}分钟)")

    print(f"  [WIN] 能耗: 低{energy_vs_opponent:.1f}% ({total_energy:.2f} kWh vs {opponent_energy} kWh)")

    if max_completion_time < 150:
        print(f"\n*** 已达成碾压目标（< 150分钟）！***")
    elif max_completion_time < opponent_time:
        print(f"\n** 已超越对手！继续优化可达到碾压目标！**")
    else:
        print(f"\n还需优化 {max_completion_time - 150:.1f} 分钟才能达到碾压目标")

    print("\n" + "="*80)
    print("求解完成")
    print("="*80)

    return {
        'completion_time': max_completion_time,
        'total_energy': total_energy,
        'num_uavs': num_b_uavs + num_c_uavs
    }


if __name__ == "__main__":
    result = main()
