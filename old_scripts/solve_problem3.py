#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题三主求解器 - 通信约束下的运输与中继联合调度
整合问题一、问题二成果，实现多目标优化
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Set
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader
from src.communication.los_model import Position, LOSCommunicationModel, CommParams
from src.relay.deployment_optimizer import (
    RelayCandidateGenerator, RelayDeploymentOptimizer, RelayCandidate
)
from src.terrain.dem_loader import DEMLoader


class Problem3Solver:
    """
    问题三求解器：通信约束下的运输与中继联合调度

    四层求解框架：
    1. 数据准备（复用问题一、二）
    2. 通信覆盖分析
    3. 中继部署优化
    4. 联合调度与多目标优化
    """

    def __init__(self, data_loader: DataLoader):
        self.loader = data_loader
        self.depot = data_loader.get_depot()

        # 加载DEM数据
        print("加载DEM地形数据...")
        dem_file = "数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）/镇龙乡及周边30米DEM.mat"
        try:
            dem_loader = DEMLoader(dem_file)
            dem_data, dem_bounds = dem_loader.load()
            print("DEM数据加载成功！")
        except Exception as e:
            print(f"警告: DEM加载失败 ({e})，使用简化通信模型")
            dem_data = None
            dem_bounds = None

        # 通信模型（集成DEM）
        self.los_model = LOSCommunicationModel(
            dem_data=dem_data,
            dem_bounds=dem_bounds,
            comm_params=CommParams()
        )

        # 中继生成器和优化器
        self.relay_generator = RelayCandidateGenerator(self.los_model, max_hover_height=200)
        self.relay_optimizer = RelayDeploymentOptimizer(max_relays=10)  # 增加到10架

    def solve(self, problem1_result_file: str, problem2_result_file: str) -> Dict:
        """
        求解问题三

        Args:
            problem1_result_file: 问题一结果文件
            problem2_result_file: 问题二结果文件

        Returns:
            求解结果字典
        """
        print("="*80)
        print("问题三求解器启动")
        print("="*80)

        # Layer 1: 加载问题一、二的结果
        print("\n[Layer 1] 加载基础数据...")
        df_problem1 = pd.read_excel(problem1_result_file, engine='openpyxl')
        df_problem2 = pd.read_excel(problem2_result_file, engine='openpyxl')

        print(f"  问题一方案数: {len(df_problem1)}")
        print(f"  问题二调度数: {len(df_problem2)}")

        # Layer 2: 通信覆盖分析
        print("\n[Layer 2] 通信覆盖分析...")
        gateway = Position(
            self.depot['longitude'],
            self.depot['latitude'],
            self.depot['altitude'] + 50  # 网关天线高度
        )

        # 分析每个任务的通信需求
        blind_zones = self._analyze_communication_coverage(df_problem2, gateway)
        print(f"  识别通信盲区: {len(blind_zones)} 个任务段需要中继支持")

        # Layer 3: 中继部署优化
        print("\n[Layer 3] 中继部署优化...")
        relay_deployment = self._optimize_relay_deployment(blind_zones, df_problem2)
        print(f"  部署中继机数: {len(relay_deployment)}")

        # Layer 4: 联合调度优化
        print("\n[Layer 4] 联合调度优化...")
        final_solution = self._joint_optimization(df_problem2, relay_deployment)

        # 计算多目标指标
        objectives = self._compute_objectives(final_solution)

        print("\n" + "="*80)
        print("问题三求解完成")
        print("="*80)

        return {
            'transport_schedule': final_solution['transport'],
            'relay_deployment': final_solution['relay'],
            'objectives': objectives,
            'blind_zones': blind_zones
        }

    def _analyze_communication_coverage(self, df_schedule: pd.DataFrame,
                                       gateway: Position) -> List[Tuple[List[Position], int]]:
        """
        分析通信覆盖，识别盲区

        Returns:
            [(路径点列表, 任务ID), ...] 需要中继的任务段
        """
        blind_zones = []

        for idx, row in df_schedule.iterrows():
            area_id = row['服务区']
            area = self.loader.get_service_area(area_id)

            if area is None:
                continue

            # 构造简化的飞行路径（往返直线）
            area_pos = Position(
                area['longitude'],
                area['latitude'],
                area['altitude'] + 100  # 巡航高度
            )

            # 检查网关是否能直接覆盖
            is_los, reason = self.los_model.check_los(gateway, area_pos)

            if not is_los:
                # 需要中继支持
                # 生成路径上的采样点
                path_points = self._generate_path_points(gateway, area_pos, num_points=10)
                blind_zones.append((path_points, idx))
                print(f"    任务{idx} ({area_id}): 需要中继 - {reason}")

        return blind_zones

    def _generate_path_points(self, start: Position, end: Position,
                             num_points: int = 10) -> List[Position]:
        """生成路径上的采样点"""
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            x = start.x + t * (end.x - start.x)
            y = start.y + t * (end.y - start.y)
            z = start.z + t * (end.z - start.z)
            points.append(Position(x, y, z))
        return points

    def _optimize_relay_deployment(self, blind_zones: List[Tuple[List[Position], int]],
                                   df_schedule: pd.DataFrame) -> List[Dict]:
        """优化中继部署"""
        if not blind_zones:
            print("  无需部署中继（所有任务可直连网关）")
            return []

        # 生成候选位置
        print("  生成中继候选位置...")
        candidates = self.relay_generator.generate_candidates(
            blind_zones,
            search_grid_size=500,
            height_levels=[100, 150, 200]
        )

        if not candidates:
            print("  警告: 无法生成有效候选，使用简化方案")
            # 简化方案：为每个盲区在中点部署中继
            candidates = []
            for i, (path_points, mission_id) in enumerate(blind_zones):
                if path_points:
                    mid_point = path_points[len(path_points) // 2]
                    candidate = RelayCandidate(
                        id=i,
                        position=Position(mid_point.x, mid_point.y, mid_point.z + 100),
                        covered_missions={mission_id}
                    )
                    candidates.append(candidate)

        # 计算每个候选的完整覆盖
        print("  计算候选覆盖范围...")
        for candidate in candidates:
            self.relay_generator.compute_candidate_coverage(candidate, blind_zones)

        # Set Cover优化
        print("  执行Set Cover优化...")
        all_mission_ids = {mission_id for _, mission_id in blind_zones}
        selected_relays = self.relay_optimizer.optimize_deployment(candidates, all_mission_ids)

        # 协调时间窗
        print("  协调时间窗...")
        mission_schedules = {}
        for idx, row in df_schedule.iterrows():
            mission_schedules[idx] = (
                row['开始时间(分钟)'],
                row['结束时间(分钟)']
            )

        deployments = self.relay_optimizer.coordinate_time_windows(
            selected_relays,
            mission_schedules
        )

        # 转换为字典格式
        deployment_list = []
        for dep in deployments:
            deployment_list.append({
                'relay_id': dep.relay_id,
                'position': (dep.position.x, dep.position.y, dep.position.z),
                'service_start': dep.service_start_time,
                'service_end': dep.service_end_time,
                'covered_missions': list(dep.covered_missions),
                'energy': dep.total_energy
            })

        return deployment_list

    def _joint_optimization(self, df_transport: pd.DataFrame,
                           relay_deployment: List[Dict]) -> Dict:
        """联合调度优化"""
        # 简化版：直接使用问题二的运输调度 + 中继部署
        return {
            'transport': df_transport,
            'relay': relay_deployment
        }

    def _compute_objectives(self, solution: Dict) -> Dict:
        """计算多目标指标"""
        df_transport = solution['transport']
        relay_deployment = solution['relay']

        # 目标1: 配送及时性（假设时限240分钟）
        time_limit = 240
        delays = df_transport['结束时间(分钟)'].apply(lambda x: max(0, x - time_limit))
        timeliness = delays.sum()

        # 目标2: 联合完成时间
        transport_completion = df_transport['结束时间(分钟)'].max()
        relay_completion = max([r['service_end'] for r in relay_deployment], default=0)
        completion_time = max(transport_completion, relay_completion)

        # 目标3: 总能耗
        transport_energy = df_transport['能耗(kWh)'].sum()
        relay_energy = sum([r['energy'] for r in relay_deployment])
        total_energy = transport_energy + relay_energy

        # 目标4: 使用架次
        transport_trips = len(df_transport)
        relay_trips = len(relay_deployment)
        total_trips = transport_trips + relay_trips

        objectives = {
            'timeliness': timeliness,
            'completion_time': completion_time,
            'total_energy': total_energy,
            'transport_energy': transport_energy,
            'relay_energy': relay_energy,
            'total_trips': total_trips,
            'transport_trips': transport_trips,
            'relay_trips': relay_trips
        }

        return objectives

    def generate_report(self, result: Dict, output_dir: Path):
        """生成结果报告"""
        output_dir.mkdir(parents=True, exist_ok=True)

        # 保存运输调度
        transport_file = output_dir / "问题三_运输调度.xlsx"
        result['transport_schedule'].to_excel(transport_file, index=False, engine='openpyxl')
        print(f"\n运输调度已保存: {transport_file}")

        # 保存中继部署
        if result['relay_deployment']:
            relay_df = pd.DataFrame(result['relay_deployment'])
            relay_file = output_dir / "问题三_中继部署.xlsx"
            relay_df.to_excel(relay_file, index=False, engine='openpyxl')
            print(f"中继部署已保存: {relay_file}")

        # 保存目标指标
        objectives = result['objectives']
        print("\n" + "="*80)
        print("多目标优化结果")
        print("="*80)
        print(f"目标1 - 配送及时性: {objectives['timeliness']:.2f} 分钟延迟")
        print(f"目标2 - 联合完成时间: {objectives['completion_time']:.2f} 分钟")
        print(f"目标3 - 总能耗: {objectives['total_energy']:.2f} kWh")
        print(f"  └ 运输机能耗: {objectives['transport_energy']:.2f} kWh")
        print(f"  └ 中继机能耗: {objectives['relay_energy']:.2f} kWh")
        print(f"目标4 - 总架次: {objectives['total_trips']}")
        print(f"  └ 运输机架次: {objectives['transport_trips']}")
        print(f"  └ 中继机架次: {objectives['relay_trips']}")
        print("="*80)


def main():
    """主函数"""
    print("="*80)
    print("问题三：通信约束下的运输与中继联合调度")
    print("="*80)

    # 加载数据
    print("\n[数据加载]")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 检查问题一、二结果
    problem1_file = Path("结果/问题一_配送方案.xlsx")
    problem2_file = Path("结果/问题二_调度方案.xlsx")

    if not problem1_file.exists():
        print(f"错误: 未找到问题一结果: {problem1_file}")
        return

    if not problem2_file.exists():
        print(f"错误: 未找到问题二结果: {problem2_file}")
        return

    # 创建求解器
    print("\n[创建求解器]")
    solver = Problem3Solver(loader)

    # 求解
    print("\n[开始求解]")
    result = solver.solve(str(problem1_file), str(problem2_file))

    # 生成报告
    print("\n[生成报告]")
    output_dir = Path("结果")
    solver.generate_report(result, output_dir)

    print("\n" + "="*80)
    print("问题三求解完成！")
    print("="*80)


if __name__ == "__main__":
    main()
