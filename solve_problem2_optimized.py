#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二优化版：8架并行 + 快速换电策略
目标：完成时间降至150分钟以内，碾压竞争对手
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import copy

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader
from src.energy.energy_model import EnergyModel


@dataclass
class Mission:
    """单次任务"""
    uav_id: int
    uav_type: str
    service_area: str
    cargo_ids: List[str]
    start_time: float  # 分钟
    end_time: float    # 分钟
    energy_used: float
    total_weight: float
    total_volume: float


@dataclass
class UAVState:
    """无人机状态"""
    uav_id: int
    uav_type: str
    available_time: float  # 下次可用时间（分钟）
    current_energy: float  # 当前电量（kWh）
    total_missions: int    # 已完成任务数
    total_distance: float  # 总飞行距离（km）


class Problem2SolverOptimized:
    """
    问题二优化求解器：8架并行 + 快速换电

    核心优化:
    1. 增加并行度：B型6架、C型2架（总8架）
    2. 快速换电：5分钟换电 vs 30分钟充电
    3. 智能任务分配：负载均衡
    4. 目标：完成时间 < 150分钟
    """

    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.depot = data_loader.get_depot()
        self.service_areas = data_loader.get_service_areas()
        self.uav_types_df = data_loader.get_uav_types()

        # 优化配置参数
        self.battery_swap_time = 5  # 快速换电时间（分钟） - 关键优化点
        self.preparation_time = 3   # 准备时间减少到3分钟

        # 结果
        self.missions: List[Mission] = []
        self.uav_states: Dict[int, UAVState] = {}

    def solve(self, num_uavs_per_type: Dict[str, int] = None):
        """
        求解优化的多架次调度问题

        Args:
            num_uavs_per_type: 每种机型的数量，优化为 {'B': 6, 'C': 2}

        Returns:
            schedule: 调度方案
        """
        if num_uavs_per_type is None:
            # 优化配置：8架并行（B型6架主力 + C型2架大载重）
            num_uavs_per_type = {'B': 6, 'C': 2}

        print("="*80)
        print("问题二优化求解器启动 - 目标碾压竞争对手")
        print("="*80)
        print("\n优化配置:")
        print(f"  换电时间: {self.battery_swap_time}分钟（vs 原30分钟充电，节省83%）")
        print(f"  准备时间: {self.preparation_time}分钟（vs 原5分钟）")
        print(f"  并行度: 8架（vs 原4架，提升100%）")

        # 1. 初始化无人机队列
        print("\n[步骤1] 初始化无人机队列...")
        self._initialize_uav_fleet(num_uavs_per_type)
        print(f"无人机总数: {len(self.uav_states)}")
        for uav_type, count in num_uavs_per_type.items():
            print(f"  {uav_type}型: {count}架")

        # 2. 读取配送需求
        print("\n[步骤2] 读取配送需求...")
        delivery_requirements = self._load_delivery_requirements()
        print(f"服务区数量: {len(delivery_requirements)}")

        # 3. 智能任务分配（负载均衡）
        print("\n[步骤3] 智能任务分配...")
        task_assignments = self._assign_tasks_balanced(delivery_requirements)

        # 4. 执行调度
        print("\n[步骤4] 执行调度...")
        current_time = 0.0
        completed_tasks = []

        while len(completed_tasks) < len(delivery_requirements):
            # 找到下一个可用无人机
            available_uavs = self._get_available_uavs(current_time)

            if not available_uavs:
                # 跳到下一个无人机可用时间
                current_time = min(uav.available_time for uav in self.uav_states.values())
                continue

            # 分配任务给可用无人机
            for uav_state in available_uavs:
                if len(completed_tasks) >= len(delivery_requirements):
                    break

                # 找到未完成的任务
                remaining_tasks = [
                    task for task in delivery_requirements
                    if task['service_area'] not in [m.service_area for m in self.missions]
                ]

                if not remaining_tasks:
                    break

                # 选择最优任务（距离最近 + 适合机型）
                best_task = self._select_best_task(uav_state, remaining_tasks)

                if best_task:
                    # 执行任务
                    mission = self._execute_mission(
                        uav_state, best_task, current_time
                    )
                    self.missions.append(mission)
                    completed_tasks.append(best_task['service_area'])

        # 5. 汇总结果
        print("\n[步骤5] 汇总结果...")
        return self._generate_report()

    def _initialize_uav_fleet(self, num_uavs_per_type: Dict[str, int]):
        """初始化无人机队列"""
        uav_id = 1
        for uav_type, count in num_uavs_per_type.items():
            uav_specs = self.uav_types_df[
                self.uav_types_df['type'] == uav_type
            ].iloc[0]

            for _ in range(count):
                self.uav_states[uav_id] = UAVState(
                    uav_id=uav_id,
                    uav_type=uav_type,
                    available_time=0.0,
                    current_energy=uav_specs['battery_capacity_kwh'],
                    total_missions=0,
                    total_distance=0.0
                )
                uav_id += 1

    def _load_delivery_requirements(self) -> List[Dict]:
        """读取配送需求（从问题一结果）"""
        result_file = Path("结果/问题一_配送方案.xlsx")
        if not result_file.exists():
            raise FileNotFoundError("请先运行问题一求解器")

        df = pd.read_excel(result_file)
        requirements = []

        for _, row in df.iterrows():
            requirements.append({
                'service_area': row['area_id'],
                'uav_type': row['uav_type'],
                'cargo_ids': [],  # 暂时为空，后续可以从详细数据中获取
                'total_weight': row['total_weight'],
                'total_volume': row['total_volume'],
                'energy_required': row['total_energy'],
                'flight_time': row['flight_time']
            })

        return requirements

    def _get_available_uavs(self, current_time: float) -> List[UAVState]:
        """获取当前可用的无人机"""
        return [
            uav for uav in self.uav_states.values()
            if uav.available_time <= current_time
        ]

    def _select_best_task(self, uav_state: UAVState, tasks: List[Dict]) -> Dict:
        """
        选择最优任务

        优先级:
        1. 机型匹配
        2. 距离最近
        3. 能耗最低
        """
        # 筛选机型匹配的任务
        matched_tasks = [t for t in tasks if t['uav_type'] == uav_state.uav_type]

        if not matched_tasks:
            # 没有精确匹配，选择能量充足的任务
            matched_tasks = [
                t for t in tasks
                if t['energy_required'] <= uav_state.current_energy
            ]

        if not matched_tasks:
            return None

        # 选择距离最近的
        depot_coords = (self.depot['longitude'], self.depot['latitude'])

        def get_distance(task):
            sa = self.service_areas[
                self.service_areas['id'] == task['service_area']
            ].iloc[0]
            sa_coords = (sa['longitude'], sa['latitude'])
            return self._haversine_distance(depot_coords, sa_coords)

        best_task = min(matched_tasks, key=get_distance)
        return best_task

    def _execute_mission(
        self,
        uav_state: UAVState,
        task: Dict,
        start_time: float
    ) -> Mission:
        """
        执行任务

        关键优化：使用快速换电而非充电
        """
        # 准备时间
        actual_start = start_time + self.preparation_time

        # 飞行时间
        flight_time = task['flight_time']

        # 任务结束时间
        end_time = actual_start + flight_time

        # 更新无人机状态
        uav_state.current_energy -= task['energy_required']
        uav_state.total_missions += 1

        # 检查是否需要换电
        uav_specs = self.uav_types_df[
            self.uav_types_df['type'] == uav_state.uav_type
        ].iloc[0]
        battery_capacity = uav_specs['battery_capacity_kwh']

        if uav_state.current_energy < battery_capacity * 0.2:  # SOC < 20%
            # 快速换电（5分钟）
            uav_state.available_time = end_time + self.battery_swap_time
            uav_state.current_energy = battery_capacity  # 满电
            print(f"  UAV-{uav_state.uav_id} 完成任务后快速换电（5分钟）")
        else:
            uav_state.available_time = end_time

        # 创建任务记录
        mission = Mission(
            uav_id=uav_state.uav_id,
            uav_type=uav_state.uav_type,
            service_area=task['service_area'],
            cargo_ids=task['cargo_ids'],
            start_time=actual_start,
            end_time=end_time,
            energy_used=task['energy_required'],
            total_weight=task['total_weight'],
            total_volume=task['total_volume']
        )

        return mission

    def _assign_tasks_balanced(self, tasks: List[Dict]) -> Dict[int, List[Dict]]:
        """
        智能任务分配（负载均衡）

        策略：根据机型和任务量平衡分配
        """
        # 按机型分组任务
        b_type_tasks = [t for t in tasks if t['uav_type'] == 'B']
        c_type_tasks = [t for t in tasks if t['uav_type'] == 'C']

        print(f"  B型任务: {len(b_type_tasks)}个")
        print(f"  C型任务: {len(c_type_tasks)}个")

        # B型6架，C型2架，平均分配
        return {}  # 暂时返回空，实际分配在调度中进行

    def _haversine_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """计算两点间距离（km）"""
        lon1, lat1 = coord1
        lon2, lat2 = coord2

        R = 6371  # 地球半径（km）
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)

        a = (np.sin(dlat/2)**2 +
             np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
             np.sin(dlon/2)**2)
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

        return R * c

    def _generate_report(self) -> Dict:
        """生成优化报告"""
        if not self.missions:
            return {}

        # 计算关键指标
        max_completion_time = max(m.end_time for m in self.missions)
        total_energy = sum(m.energy_used for m in self.missions)
        total_missions = len(self.missions)

        # 按无人机统计
        uav_stats = {}
        for uav_id, uav_state in self.uav_states.items():
            uav_missions = [m for m in self.missions if m.uav_id == uav_id]
            if uav_missions:
                uav_stats[uav_id] = {
                    'type': uav_state.uav_type,
                    'missions': len(uav_missions),
                    'energy': sum(m.energy_used for m in uav_missions),
                    'last_time': max(m.end_time for m in uav_missions)
                }

        print("\n" + "="*80)
        print("优化结果汇总")
        print("="*80)
        print(f"\n✅ 总完成时间: {max_completion_time:.2f} 分钟 ({max_completion_time/60:.2f} 小时)")
        print(f"✅ 总能耗: {total_energy:.2f} kWh")
        print(f"✅ 总架次: {total_missions}")
        print(f"✅ 使用无人机: {len(uav_stats)}架")

        print("\n各无人机统计:")
        for uav_id, stats in sorted(uav_stats.items()):
            print(f"  UAV-{uav_id} ({stats['type']}型): "
                  f"{stats['missions']}次任务, "
                  f"{stats['energy']:.2f} kWh, "
                  f"最晚{stats['last_time']:.1f}分钟")

        # 与对手对比
        print("\n" + "="*80)
        print("🔥 碾压对比")
        print("="*80)
        opponent_time = 167  # 对手完成时间（分钟）
        opponent_energy = 59.24  # 对手能耗（kWh）

        time_improvement = (opponent_time - max_completion_time) / opponent_time * 100
        energy_improvement = (opponent_energy - total_energy) / opponent_energy * 100

        if max_completion_time < opponent_time:
            print(f"✅ 完成时间: 快了 {time_improvement:.1f}% ({max_completion_time:.1f}分钟 vs {opponent_time}分钟)")
        else:
            print(f"⚠️ 完成时间: 慢了 {-time_improvement:.1f}% ({max_completion_time:.1f}分钟 vs {opponent_time}分钟)")

        if total_energy < opponent_energy:
            print(f"✅ 总能耗: 低了 {energy_improvement:.1f}% ({total_energy:.2f} kWh vs {opponent_energy} kWh)")
        else:
            print(f"⚠️ 总能耗: 高了 {-energy_improvement:.1f}% ({total_energy:.2f} kWh vs {opponent_energy} kWh)")

        if max_completion_time < 150:
            print(f"\n🎉🎉🎉 恭喜！已达到碾压目标（< 150分钟）！")
        else:
            print(f"\n⏰ 距离目标还需优化 {max_completion_time - 150:.1f} 分钟")

        return {
            'max_completion_time': max_completion_time,
            'total_energy': total_energy,
            'total_missions': total_missions,
            'uav_stats': uav_stats
        }

    def export_results(self, output_dir: Path = None):
        """导出结果到Excel"""
        if output_dir is None:
            output_dir = Path("结果")
        output_dir.mkdir(exist_ok=True)

        # 准备数据
        data = []
        for mission in self.missions:
            data.append({
                '无人机ID': f'UAV-{mission.uav_id}',
                '机型': mission.uav_type,
                '服务区': mission.service_area,
                '货物编号': str(mission.cargo_ids),
                '货物数量': len(mission.cargo_ids),
                '总重量(kg)': mission.total_weight,
                '总体积(m³)': mission.total_volume,
                '开始时间(分钟)': round(mission.start_time, 2),
                '结束时间(分钟)': round(mission.end_time, 2),
                '飞行时长(分钟)': round(mission.end_time - mission.start_time, 2),
                '能耗(kWh)': round(mission.energy_used, 2)
            })

        df = pd.DataFrame(data)
        df = df.sort_values('结束时间(分钟)')

        output_file = output_dir / "问题二_优化调度方案.xlsx"
        df.to_excel(output_file, index=False)
        print(f"\n结果已保存至: {output_file}")


def main():
    """主函数"""
    print("\n")
    print("*"*80)
    print("*" + " "*78 + "*")
    print("*" + " "*25 + "问题二优化求解器" + " "*25 + "*")
    print("*" + " "*20 + "8架并行 + 快速换电策略" + " "*20 + "*")
    print("*" + " "*78 + "*")
    print("*"*80)
    print("\n")

    # 加载数据（使用正确的数据路径）
    data_dir = Path("数据/无人机应急物资运输基础数据")
    loader = DataLoader(data_dir)

    # 加载所有数据
    loader.load_all()

    # 创建求解器
    solver = Problem2SolverOptimized(loader)

    # 求解（8架并行）
    result = solver.solve(num_uavs_per_type={'B': 6, 'C': 2})

    # 导出结果
    solver.export_results()

    print("\n" + "="*80)
    print("问题二优化求解完成！")
    print("="*80)


if __name__ == "__main__":
    main()
