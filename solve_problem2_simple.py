#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二：多架次调度优化（简化版）
基于问题一的结果，扩展到多架次场景
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader
from src.energy.energy_model import EnergyModel


class Problem2SimpleSolver:
    """
    问题二简化求解器

    策略：
    1. 读取问题一的结果（单架次方案）
    2. 模拟多架无人机并行执行
    3. 考虑充电时间和准备时间
    4. 生成甘特图和统计数据
    """

    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.depot = data_loader.get_depot()

        # 配置参数
        self.charging_time = 30  # 充电时间（分钟）
        self.preparation_time = 5  # 准备时间（分钟）

    def solve(self, problem1_result_file: str, num_uavs_per_type: dict):
        """
        求解问题二

        Args:
            problem1_result_file: 问题一结果文件路径
            num_uavs_per_type: 每种机型的数量 {'A': 2, 'B': 3, 'C': 1}

        Returns:
            schedule_df: 调度方案
            stats: 统计数据
        """
        print("="*80)
        print("问题二求解器启动（简化版）")
        print("="*80)

        # 1. 读取问题一结果
        print("\n[步骤1] 读取问题一结果...")
        df_problem1 = pd.read_excel(problem1_result_file, engine='openpyxl')
        print(f"问题一共有 {len(df_problem1)} 个配送任务")

        # 2. 初始化无人机队列
        print("\n[步骤2] 初始化无人机队列...")
        uav_fleet = self._initialize_fleet(num_uavs_per_type)
        print(f"总无人机数: {len(uav_fleet)}")

        # 3. 分配任务
        print("\n[步骤3] 分配任务到无人机...")
        schedule = self._assign_tasks(df_problem1, uav_fleet)

        # 4. 生成结果
        print("\n[步骤4] 生成调度方案...")
        schedule_df = pd.DataFrame(schedule)

        # 5. 计算统计
        print("\n[步骤5] 计算统计数据...")
        stats = self._compute_stats(schedule_df)

        return schedule_df, stats

    def _initialize_fleet(self, num_uavs_per_type: dict) -> list:
        """初始化无人机队列"""
        fleet = []
        uav_id = 1

        for uav_type, count in num_uavs_per_type.items():
            if count == 0:
                continue
            uav_params = self.loader.get_uav_type(uav_type)
            for i in range(count):
                fleet.append({
                    'uav_id': uav_id,
                    'uav_type': uav_type,
                    'available_time': 0.0,  # 分钟
                    'battery_capacity': uav_params['battery_capacity_kwh'],
                    'current_energy': uav_params['battery_capacity_kwh'],
                    'total_missions': 0
                })
                print(f"  UAV-{uav_id}: {uav_type}型")
                uav_id += 1

        return fleet

    def _assign_tasks(self, df_problem1: pd.DataFrame, fleet: list) -> list:
        """分配任务"""
        schedule = []

        # 按机型分组任务
        for uav_type in df_problem1['uav_type'].unique():
            type_tasks = df_problem1[df_problem1['uav_type'] == uav_type].copy()
            type_uavs = [u for u in fleet if u['uav_type'] == uav_type]

            if len(type_uavs) == 0:
                print(f"  警告: 没有{uav_type}型无人机，跳过{len(type_tasks)}个任务")
                continue

            print(f"\n  {uav_type}型: {len(type_tasks)}个任务, {len(type_uavs)}架无人机")

            # 轮流分配任务
            for idx, (_, task_row) in enumerate(type_tasks.iterrows()):
                # 选择最早可用的无人机
                uav = min(type_uavs, key=lambda u: u['available_time'])

                # 计算任务时间
                area_id = task_row['area_id']
                area = self.loader.get_service_area(area_id)

                if area is None:
                    continue

                # 获取无人机参数
                uav_params = self.loader.get_uav_type(uav['uav_type'])

                # 直接使用问题一已计算的飞行时间和能耗
                flight_time = task_row['flight_time']  # 问题一已计算
                energy_needed = task_row['total_energy']

                # 确定开始时间
                start_time = uav['available_time']

                # 检查是否需要充电
                needs_charging = uav['current_energy'] < energy_needed
                if needs_charging:
                    start_time += self.charging_time
                    uav['current_energy'] = uav['battery_capacity']

                # 加上准备时间
                start_time += self.preparation_time

                # 计算结束时间
                end_time = start_time + flight_time

                # 记录任务
                schedule.append({
                    '无人机ID': f"UAV-{uav['uav_id']}",
                    '机型': uav['uav_type'],
                    '服务区': area_id,
                    '服务区名称': task_row['area_name'],
                    '货物数': int(task_row['num_cargos']),
                    '总重量(kg)': task_row['total_weight'],
                    '总体积(m3)': task_row['total_volume'],
                    '能耗(kWh)': energy_needed,
                    '开始时间(分钟)': round(start_time, 2),
                    '结束时间(分钟)': round(end_time, 2),
                    '飞行时长(分钟)': round(flight_time, 2),
                    '是否充电': '是' if needs_charging else '否'
                })

                # 更新无人机状态
                uav['available_time'] = end_time
                uav['current_energy'] -= energy_needed
                uav['total_missions'] += 1

                print(f"    UAV-{uav['uav_id']} -> {task_row['area_name']}: "
                      f"{start_time:.1f}-{end_time:.1f}分钟 "
                      f"{'[充电]' if needs_charging else ''}")

        return schedule

    def _compute_stats(self, schedule_df: pd.DataFrame) -> dict:
        """计算统计数据"""
        if len(schedule_df) == 0:
            return {}

        stats = {
            'total_missions': len(schedule_df),
            'total_cargos': int(schedule_df['货物数'].sum()),
            'total_weight': schedule_df['总重量(kg)'].sum(),
            'total_energy': schedule_df['能耗(kWh)'].sum(),
            'max_completion_time': schedule_df['结束时间(分钟)'].max(),
            'num_charging': (schedule_df['是否充电'] == '是').sum(),
            'charging_rate': (schedule_df['是否充电'] == '是').sum() / len(schedule_df) * 100
        }

        # 按机型统计
        type_stats = {}
        for uav_type in schedule_df['机型'].unique():
            type_df = schedule_df[schedule_df['机型'] == uav_type]
            type_stats[uav_type] = {
                'missions': len(type_df),
                'cargos': int(type_df['货物数'].sum()),
                'energy': type_df['能耗(kWh)'].sum()
            }

        stats['type_stats'] = type_stats

        return stats


def main():
    """主函数"""
    print("="*80)
    print("问题二：多架次调度优化（简化版）")
    print("="*80)

    # 加载数据
    print("\n[数据加载]")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 检查问题一结果
    problem1_file = Path("结果/问题一_配送方案.xlsx")
    if not problem1_file.exists():
        print(f"\n错误: 未找到问题一结果文件: {problem1_file}")
        print("请先运行 solve_problem1.py")
        return

    # 创建求解器
    print("\n[创建求解器]")
    solver = Problem2SimpleSolver(loader)

    # 求解
    print("\n[开始求解]")
    schedule_df, stats = solver.solve(
        problem1_result_file=str(problem1_file),
        num_uavs_per_type={'A': 0, 'B': 3, 'C': 1}
    )

    # 保存结果
    print("\n[保存结果]")
    output_dir = Path("结果")
    output_dir.mkdir(exist_ok=True)

    schedule_file = output_dir / "问题二_调度方案.xlsx"
    schedule_df.to_excel(schedule_file, index=False, engine='openpyxl')
    print(f"调度方案已保存: {schedule_file}")

    # 打印统计
    print("\n" + "="*80)
    print("调度结果统计")
    print("="*80)
    print(f"总任务数: {stats['total_missions']}")
    print(f"总货物数: {stats['total_cargos']}")
    print(f"总载重: {stats['total_weight']:.2f} kg")
    print(f"总能耗: {stats['total_energy']:.2f} kWh")
    print(f"最大完成时间: {stats['max_completion_time']:.1f} 分钟 "
          f"({stats['max_completion_time']/60:.2f} 小时)")
    print(f"充电次数: {stats['num_charging']} ({stats['charging_rate']:.1f}%)")

    print("\n各机型使用情况:")
    for uav_type, type_stat in stats['type_stats'].items():
        print(f"  {uav_type}型: {type_stat['missions']}次任务, "
              f"{type_stat['cargos']}件货物, "
              f"{type_stat['energy']:.2f} kWh")

    print("\n任务列表（前10个）:")
    print(schedule_df.head(10).to_string(index=False))

    print("\n" + "="*80)
    print("问题二求解完成！")
    print("="*80)

    # 对比问题一
    print("\n与问题一对比:")
    problem1_time = schedule_df['飞行时长(分钟)'].sum()
    problem2_time = stats['max_completion_time']
    time_saved = problem1_time - problem2_time
    print(f"  单架次总时间: {problem1_time:.1f} 分钟")
    print(f"  多架次完成时间: {problem2_time:.1f} 分钟")
    print(f"  节省时间: {time_saved:.1f} 分钟 ({time_saved/problem1_time*100:.1f}%)")


if __name__ == "__main__":
    main()
