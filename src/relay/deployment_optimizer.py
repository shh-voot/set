#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中继模块 - 候选位置生成与部署优化
基于Set Cover的中继部署优化
"""

import numpy as np
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.communication.los_model import Position, LOSCommunicationModel


@dataclass
class RelayCandidate:
    """中继候选位置"""
    id: int
    position: Position
    coverage_area: List[Position] = field(default_factory=list)
    covered_missions: Set[int] = field(default_factory=set)
    hover_power_kw: float = 6.0  # 悬停功率
    comm_power_kw: float = 0.1   # 通信功率

    def compute_energy(self, service_duration_min: float) -> float:
        """计算服务期间的能耗"""
        return (self.hover_power_kw + self.comm_power_kw) * (service_duration_min / 60)


@dataclass
class RelayDeployment:
    """中继部署方案"""
    relay_id: int
    position: Position
    service_start_time: float  # 分钟
    service_end_time: float    # 分钟
    covered_missions: Set[int]
    total_energy: float


class RelayCandidateGenerator:
    """
    中继候选位置生成器
    在通信盲区附近搜索最优悬停位置
    """

    def __init__(self, los_model: LOSCommunicationModel,
                 max_hover_height: float = 200,
                 hover_power_kw: float = 6.0):
        """
        Args:
            los_model: LoS通信模型
            max_hover_height: 最大悬停离地高度（米）
            hover_power_kw: 悬停功率（kW）
        """
        self.los_model = los_model
        self.max_hover_height = max_hover_height
        self.hover_power_kw = hover_power_kw

    def generate_candidates(self, blind_zones: List[Tuple[List[Position], int]],
                          search_grid_size: float = 500,
                          height_levels: List[float] = None) -> List[RelayCandidate]:
        """
        生成中继候选位置

        Args:
            blind_zones: 通信盲区列表 [(路径点列表, 任务ID), ...]
            search_grid_size: 搜索网格大小（米）
            height_levels: 尝试的悬停高度列表（米）

        Returns:
            候选位置列表
        """
        if height_levels is None:
            height_levels = [50, 100, 150, 200]

        candidates = []
        candidate_id = 0

        for zone_points, mission_id in blind_zones:
            if not zone_points:
                continue

            # 计算盲区中心
            center_x = np.mean([p.x for p in zone_points])
            center_y = np.mean([p.y for p in zone_points])

            # 在中心附近网格搜索
            for dx in np.arange(-search_grid_size, search_grid_size + 1, search_grid_size):
                for dy in np.arange(-search_grid_size, search_grid_size + 1, search_grid_size):
                    x = center_x + dx
                    y = center_y + dy

                    # 获取地形高度
                    terrain_height = self.los_model._get_terrain_height(x, y)
                    if terrain_height is None:
                        continue

                    # 尝试不同的悬停高度
                    for hover_height in height_levels:
                        if hover_height > self.max_hover_height:
                            continue

                        z = terrain_height + hover_height
                        position = Position(x, y, z)

                        # 检查是否能覆盖该盲区
                        coverage_count = 0
                        for point in zone_points:
                            is_los, _ = self.los_model.check_los(position, point)
                            if is_los:
                                coverage_count += 1

                        # 如果覆盖率足够高，加入候选
                        if coverage_count >= len(zone_points) * 0.8:  # 80%覆盖率
                            candidate = RelayCandidate(
                                id=candidate_id,
                                position=position,
                                covered_missions={mission_id},
                                hover_power_kw=self.hover_power_kw
                            )
                            candidates.append(candidate)
                            candidate_id += 1

        return candidates

    def compute_candidate_coverage(self, candidate: RelayCandidate,
                                  all_missions: List[Tuple[List[Position], int]]) -> RelayCandidate:
        """
        计算候选位置对所有任务的覆盖情况

        Args:
            candidate: 候选位置
            all_missions: 所有任务 [(路径点列表, 任务ID), ...]

        Returns:
            更新后的候选（包含完整的covered_missions）
        """
        candidate.covered_missions = set()

        for mission_points, mission_id in all_missions:
            # 检查是否能覆盖该任务的大部分点
            coverage_count = 0
            for point in mission_points:
                is_los, _ = self.los_model.check_los(candidate.position, point)
                if is_los:
                    coverage_count += 1

            if coverage_count >= len(mission_points) * 0.8:
                candidate.covered_missions.add(mission_id)

        return candidate


class RelayDeploymentOptimizer:
    """
    中继部署优化器
    基于Set Cover问题的贪心求解
    """

    def __init__(self, max_relays: int = 10):
        """
        Args:
            max_relays: 最大中继机数量
        """
        self.max_relays = max_relays

    def optimize_deployment(self, candidates: List[RelayCandidate],
                          all_mission_ids: Set[int]) -> List[RelayCandidate]:
        """
        优化中继部署方案（Set Cover贪心算法）

        Args:
            candidates: 候选位置列表
            all_mission_ids: 所有需要覆盖的任务ID

        Returns:
            选中的中继位置列表
        """
        selected_relays = []
        uncovered_missions = all_mission_ids.copy()

        print(f"\n开始Set Cover优化:")
        print(f"  候选位置数: {len(candidates)}")
        print(f"  需要覆盖的任务数: {len(all_mission_ids)}")

        iteration = 0
        while uncovered_missions and len(selected_relays) < self.max_relays:
            iteration += 1

            # 选择覆盖最多未覆盖任务的候选
            best_candidate = None
            max_new_coverage = 0

            for candidate in candidates:
                # 计算该候选能新覆盖的任务数
                newly_covered = candidate.covered_missions & uncovered_missions
                if len(newly_covered) > max_new_coverage:
                    max_new_coverage = len(newly_covered)
                    best_candidate = candidate

            if best_candidate is None or max_new_coverage == 0:
                print(f"  警告: 无法继续覆盖剩余 {len(uncovered_missions)} 个任务")
                break

            # 选中该候选
            selected_relays.append(best_candidate)
            newly_covered = best_candidate.covered_missions & uncovered_missions
            uncovered_missions -= newly_covered

            print(f"  迭代{iteration}: 选中中继{best_candidate.id}, "
                  f"新覆盖{len(newly_covered)}个任务, "
                  f"剩余{len(uncovered_missions)}个未覆盖")

        print(f"\nSet Cover优化完成:")
        print(f"  选中中继数: {len(selected_relays)}")
        print(f"  覆盖率: {(len(all_mission_ids) - len(uncovered_missions)) / len(all_mission_ids) * 100:.1f}%")

        return selected_relays

    def coordinate_time_windows(self, selected_relays: List[RelayCandidate],
                               mission_schedules: Dict[int, Tuple[float, float]]) -> List[RelayDeployment]:
        """
        协调中继机与运输机的时间窗

        Args:
            selected_relays: 选中的中继位置
            mission_schedules: 任务时间表 {mission_id: (start_time, end_time)}

        Returns:
            完整的中继部署方案（含时间窗和能耗）
        """
        deployments = []

        for relay in selected_relays:
            # 找到该中继服务的所有任务的时间范围
            if not relay.covered_missions:
                continue

            start_times = []
            end_times = []

            for mission_id in relay.covered_missions:
                if mission_id in mission_schedules:
                    start, end = mission_schedules[mission_id]
                    start_times.append(start)
                    end_times.append(end)

            if not start_times:
                continue

            # 中继需要提前到达（部署时间）
            deploy_advance = 10  # 提前10分钟
            service_start = min(start_times) - deploy_advance
            service_end = max(end_times)

            # 计算能耗
            service_duration = service_end - service_start
            total_energy = relay.compute_energy(service_duration)

            deployment = RelayDeployment(
                relay_id=relay.id,
                position=relay.position,
                service_start_time=service_start,
                service_end_time=service_end,
                covered_missions=relay.covered_missions,
                total_energy=total_energy
            )

            deployments.append(deployment)

        return deployments


def test_relay_module():
    """测试中继模块"""
    print("="*80)
    print("测试中继模块")
    print("="*80)

    # 创建LoS模型
    los_model = LOSCommunicationModel()

    # 模拟通信盲区
    blind_zone1 = [
        Position(1000, 1000, 500),
        Position(1100, 1100, 550),
        Position(1200, 1200, 600),
    ]

    blind_zone2 = [
        Position(2000, 2000, 700),
        Position(2100, 2100, 750),
    ]

    blind_zones = [(blind_zone1, 1), (blind_zone2, 2)]

    # 生成候选
    print("\n[步骤1] 生成中继候选位置...")
    generator = RelayCandidateGenerator(los_model, max_hover_height=200)
    candidates = generator.generate_candidates(blind_zones, search_grid_size=300)
    print(f"生成候选数: {len(candidates)}")

    if len(candidates) == 0:
        print("警告: 未生成候选位置（可能因为缺少DEM数据）")
        print("使用简化模拟数据继续测试...")
        # 手动创建一些候选
        candidates = [
            RelayCandidate(0, Position(1100, 1100, 650), covered_missions={1}),
            RelayCandidate(1, Position(2050, 2050, 800), covered_missions={2}),
            RelayCandidate(2, Position(1500, 1500, 700), covered_missions={1, 2}),
        ]
        print(f"模拟候选数: {len(candidates)}")

    # 优化部署
    print("\n[步骤2] 优化中继部署...")
    optimizer = RelayDeploymentOptimizer(max_relays=5)
    selected = optimizer.optimize_deployment(candidates, {1, 2})
    print(f"选中中继数: {len(selected)}")

    # 时间窗协调
    print("\n[步骤3] 协调时间窗...")
    mission_schedules = {
        1: (60, 120),   # 任务1: 60-120分钟
        2: (90, 150),   # 任务2: 90-150分钟
    }
    deployments = optimizer.coordinate_time_windows(selected, mission_schedules)

    print(f"\n最终部署方案:")
    for dep in deployments:
        print(f"  中继{dep.relay_id}:")
        print(f"    位置: ({dep.position.x:.0f}, {dep.position.y:.0f}, {dep.position.z:.0f})")
        print(f"    服务时段: {dep.service_start_time:.0f} - {dep.service_end_time:.0f} 分钟")
        print(f"    覆盖任务: {dep.covered_missions}")
        print(f"    总能耗: {dep.total_energy:.2f} kWh")

    print("\n" + "="*80)
    print("中继模块测试完成")
    print("="*80)


if __name__ == "__main__":
    test_relay_module()
