#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二：多架次调度优化
考虑时限约束、电池充电、多架次协同
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


class Problem2Solver:
    """
    问题二求解器：多架次调度

    核心功能:
    1. 多架无人机协同调度
    2. 考虑电池充电时间
    3. 满足时限约束
    4. 最小化总完成时间
    """

    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.depot = data_loader.get_depot()
        self.service_areas = data_loader.get_service_areas()
        self.uav_types_df = data_loader.get_uav_types()

        # 配置参数
        self.charging_time = 30  # 充电时间（分钟）
        self.preparation_time = 5  # 准备时间（分钟）

        # 结果
        self.missions: List[Mission] = []
        self.uav_states: Dict[int, UAVState] = {}

    def solve(self, num_uavs_per_type: Dict[str, int] = None):
        """
        求解多架次调度问题

        Args:
            num_uavs_per_type: 每种机型的数量，默认 {'A': 2, 'B': 3, 'C': 1}

        Returns:
            schedule: 调度方案
        """
        if num_uavs_per_type is None:
            num_uavs_per_type = {'A': 2, 'B': 3, 'C': 1}

        print("="*80)
        print("问题二求解器启动")
        print("="*80)

        # 1. 初始化无人机队列
        print("\n[步骤1] 初始化无人机队列...")
        self._initialize_uav_fleet(num_uavs_per_type)
        print(f"无人机总数: {len(self.uav_states)}")
        for uav_type, count in num_uavs_per_type.items():
            print(f"  {uav_type}型: {count}架")

        # 2. 读取配送需求和时限
        print("\n[步骤2] 读取配送需求...")
        delivery_requirements = self._load_delivery_requirements()
        print(f"服务区数量: {len(delivery_requirements)}")

        # 3. 生成初始任务分配（贪心）
        print("\n[步骤3] 生成初始任务分配...")
        self._greedy_task_assignment(delivery_requirements)

        # 4. 优化调度（局部搜索）
        print("\n[步骤4] 优化调度方案...")
        self._optimize_schedule()

        # 5. 生成结果
        print("\n[步骤5] 生成调度结果...")
        schedule_df = self._generate_schedule_dataframe()

        # 6. 统计分析
        print("\n[步骤6] 统计分析...")
        stats = self._compute_statistics()

        return schedule_df, stats

    def _initialize_uav_fleet(self, num_uavs_per_type: Dict[str, int]):
        """初始化无人机队列"""
        uav_id = 1
        for uav_type, count in num_uavs_per_type.items():
            uav_params = self.loader.get_uav_type(uav_type)
            for i in range(count):
                self.uav_states[uav_id] = UAVState(
                    uav_id=uav_id,
                    uav_type=uav_type,
                    available_time=0.0,
                    current_energy=uav_params['battery_capacity_kwh'],
                    total_missions=0,
                    total_distance=0.0
                )
                uav_id += 1

    def _load_delivery_requirements(self) -> List[Dict]:
        """加载配送需求和时限"""
        requirements = []

        # 获取所有货物
        all_cargos = self.loader.get_cargos()

        # 直接读取时限数据
        time_limit_file = Path("数据/无人机应急物资运输基础数据/物资需求与配送时限.xlsx")
        time_limits_df = None
        if time_limit_file.exists():
            try:
                time_limits_df = pd.read_excel(time_limit_file, engine='openpyxl', sheet_name=0)
            except:
                pass

        for _, area_row in self.service_areas.iterrows():
            # 兼容不同的列名
            area_id = area_row.get('服务区编号', area_row.get('area_id', area_row.get('编号')))
            area_name = area_row.get('服务区名称', area_row.get('name', area_row.get('名称', str(area_id))))

            # 从所有货物中筛选该服务区的货物
            # 尝试多种列名
            cargos = None
            for dest_col in ['目的地', '服务区', '服务区编号', 'destination']:
                if dest_col in all_cargos.columns:
                    cargos = all_cargos[all_cargos[dest_col] == area_id].copy()
                    if len(cargos) > 0:
                        break

            if cargos is None or len(cargos) == 0:
                continue

            # 获取时限（如果有）
            time_limit = 240  # 默认4小时（240分钟）
            if time_limits_df is not None and len(time_limits_df) > 0:
                # 尝试匹配服务区
                try:
                    first_col = time_limits_df.columns[0]
                    matching = time_limits_df[time_limits_df[first_col] == area_id]
                    if len(matching) == 0:
                        # 尝试按名称匹配
                        matching = time_limits_df[time_limits_df[first_col] == area_name]

                    if len(matching) > 0:
                        limit_row = matching.iloc[0]
                        # 尝试多种可能的列名
                        for col in limit_row.index:
                            if '时限' in str(col) or 'limit' in str(col).lower():
                                val = limit_row[col]
                                if pd.notna(val) and isinstance(val, (int, float)):
                                    time_limit = float(val)
                                    break
                except Exception as e:
                    pass

            requirements.append({
                'area_id': area_id,
                'area_name': area_name,
                'cargos': cargos,
                'time_limit': time_limit,
                'priority': 1  # 可根据需求设置优先级
            })

        # 按时限排序（紧急的优先）
        requirements.sort(key=lambda x: x['time_limit'])

        return requirements

    def _greedy_task_assignment(self, requirements: List[Dict]):
        """贪心任务分配"""
        unassigned = copy.deepcopy(requirements)

        iteration = 0
        while unassigned:
            iteration += 1
            print(f"\n  轮次 {iteration}: 剩余 {len(unassigned)} 个服务区")

            # 找到最早可用的无人机
            available_uav = min(self.uav_states.values(),
                               key=lambda u: u.available_time)

            if not unassigned:
                break

            # 选择最适合的任务
            best_task = None
            best_score = -np.inf

            for task in unassigned:
                area_id = task['area_id']
                cargos = task['cargos']

                # 计算这个任务的适合度
                score = self._evaluate_task_for_uav(
                    available_uav, area_id, cargos, task['time_limit']
                )

                if score > best_score:
                    best_score = score
                    best_task = task

            if best_task is None or best_score == -np.inf:
                print(f"  警告: 无法为剩余任务分配无人机")
                break

            # 分配任务
            self._assign_task_to_uav(available_uav, best_task)
            unassigned.remove(best_task)

        print(f"\n  总共完成 {len(self.missions)} 个任务分配")

    def _evaluate_task_for_uav(self, uav: UAVState, area_id: str,
                               cargos: pd.DataFrame, time_limit: float) -> float:
        """评估任务对无人机的适合度"""
        uav_params = self.loader.get_uav_type(uav.uav_type)
        area = self.loader.get_service_area(area_id)

        if area is None:
            return -np.inf

        # 计算能耗
        energy_model = EnergyModel(uav_params, self.depot, area)
        base_energy = energy_model.calculate_total_energy(0)

        # 检查能耗是否可行
        available_energy = uav_params['battery_capacity_kwh'] * \
                          (1 - uav_params['battery_reserve_pct'])

        if base_energy > available_energy:
            return -np.inf

        # 简化：假设装载所有货物
        total_weight = cargos['重量(kg)'].sum()
        total_volume = cargos['体积(m3)'].sum()

        # 检查重量和体积约束
        if total_weight > uav_params['max_load_kg']:
            return -np.inf
        if total_volume > uav_params['max_volume_m3']:
            return -np.inf

        # 计算装载能耗
        loaded_energy = energy_model.calculate_total_energy(total_weight)
        if loaded_energy > available_energy:
            return -np.inf

        # 计算飞行时间
        flight_time = energy_model.calculate_total_time() / 60  # 转为分钟

        # 计算预计完成时间
        start_time = uav.available_time
        if uav.current_energy < loaded_energy:
            start_time += self.charging_time
        start_time += self.preparation_time

        completion_time = start_time + flight_time

        # 检查时限
        if completion_time > time_limit:
            return -np.inf

        # 计算得分（优先时间紧迫的，其次考虑能效）
        time_urgency = time_limit - completion_time
        efficiency = len(cargos) / loaded_energy

        score = time_urgency * 0.7 + efficiency * 0.3

        return score

    def _assign_task_to_uav(self, uav: UAVState, task: Dict):
        """分配任务给无人机"""
        area_id = task['area_id']
        area_name = task['area_name']
        cargos = task['cargos']

        uav_params = self.loader.get_uav_type(uav.uav_type)
        area = self.loader.get_service_area(area_id)

        # 计算能耗和时间
        total_weight = cargos['重量(kg)'].sum()
        total_volume = cargos['体积(m3)'].sum()

        energy_model = EnergyModel(uav_params, self.depot, area)
        energy_needed = energy_model.calculate_total_energy(total_weight)
        flight_time = energy_model.calculate_total_time() / 60

        # 确定开始时间
        start_time = uav.available_time

        # 如果需要充电
        if uav.current_energy < energy_needed:
            start_time += self.charging_time
            uav.current_energy = uav_params['battery_capacity_kwh']

        start_time += self.preparation_time
        end_time = start_time + flight_time

        # 创建任务
        mission = Mission(
            uav_id=uav.uav_id,
            uav_type=uav.uav_type,
            service_area=area_id,
            cargo_ids=cargos['货箱编号'].tolist() if '货箱编号' in cargos.columns else [],
            start_time=start_time,
            end_time=end_time,
            energy_used=energy_needed,
            total_weight=total_weight,
            total_volume=total_volume
        )

        self.missions.append(mission)

        # 更新无人机状态
        uav.available_time = end_time
        uav.current_energy -= energy_needed
        uav.total_missions += 1
        uav.total_distance += energy_model.horizontal_distance / 1000

        print(f"  UAV-{uav.uav_id} ({uav.uav_type}型) -> {area_name}: "
              f"{start_time:.1f}-{end_time:.1f}分钟, "
              f"{len(cargos)}件货物")

    def _optimize_schedule(self):
        """优化调度方案（局部搜索）"""
        # TODO: 实现更复杂的优化算法（如NSGA-II）
        # 当前版本使用贪心结果
        print("  当前使用贪心结果，后续可引入NSGA-II优化")

    def _generate_schedule_dataframe(self) -> pd.DataFrame:
        """生成调度结果DataFrame"""
        records = []

        for mission in self.missions:
            records.append({
                '无人机ID': f'UAV-{mission.uav_id}',
                '机型': mission.uav_type,
                '服务区': mission.service_area,
                '货物数': len(mission.cargo_ids),
                '总重量(kg)': mission.total_weight,
                '总体积(m3)': mission.total_volume,
                '能耗(kWh)': mission.energy_used,
                '开始时间(分钟)': mission.start_time,
                '结束时间(分钟)': mission.end_time,
                '飞行时长(分钟)': mission.end_time - mission.start_time
            })

        df = pd.DataFrame(records)
        df = df.sort_values(['开始时间(分钟)', '无人机ID'])

        return df

    def _compute_statistics(self) -> Dict:
        """计算统计数据"""
        if not self.missions:
            return {}

        max_completion_time = max(m.end_time for m in self.missions)
        total_cargos = sum(len(m.cargo_ids) for m in self.missions)
        total_energy = sum(m.energy_used for m in self.missions)

        # 按机型统计
        type_stats = {}
        for uav_type in ['A', 'B', 'C']:
            type_missions = [m for m in self.missions if m.uav_type == uav_type]
            if type_missions:
                type_stats[uav_type] = {
                    'missions': len(type_missions),
                    'cargos': sum(len(m.cargo_ids) for m in type_missions),
                    'energy': sum(m.energy_used for m in type_missions)
                }

        stats = {
            'total_missions': len(self.missions),
            'total_cargos': total_cargos,
            'total_energy': total_energy,
            'max_completion_time': max_completion_time,
            'num_uavs': len(self.uav_states),
            'type_stats': type_stats
        }

        return stats


def main():
    """主函数"""
    print("="*80)
    print("问题二：多架次调度优化")
    print("="*80)

    # 加载数据
    print("\n[数据加载]")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 创建求解器
    print("\n[创建求解器]")
    solver = Problem2Solver(loader)

    # 求解
    print("\n[开始求解]")
    schedule_df, stats = solver.solve(num_uavs_per_type={'A': 0, 'B': 3, 'C': 1})

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
    print(f"总能耗: {stats['total_energy']:.2f} kWh")
    print(f"最大完成时间: {stats['max_completion_time']:.1f} 分钟 "
          f"({stats['max_completion_time']/60:.2f} 小时)")
    print(f"使用无人机数: {stats['num_uavs']}")

    print("\n各机型使用情况:")
    for uav_type, type_stat in stats['type_stats'].items():
        print(f"  {uav_type}型: {type_stat['missions']}次任务, "
              f"{type_stat['cargos']}件货物, "
              f"{type_stat['energy']:.2f} kWh")

    print("\n前10个任务:")
    print(schedule_df.head(10).to_string(index=False))

    print("\n" + "="*80)
    print("问题二求解完成！")
    print("="*80)


if __name__ == "__main__":
    main()
