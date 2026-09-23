#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通信模块 - LoS通信判定与覆盖分析
基于DEM地形的视距通信模型
"""

import numpy as np
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.data.data_loader import DataLoader


@dataclass
class Position:
    """3D位置"""
    x: float  # 经度或UTM-X
    y: float  # 纬度或UTM-Y
    z: float  # 海拔高度（米）

    def distance_to(self, other: 'Position') -> float:
        """计算到另一点的3D距离"""
        return np.sqrt(
            (self.x - other.x)**2 +
            (self.y - other.y)**2 +
            (self.z - other.z)**2
        )

    def horizontal_distance_to(self, other: 'Position') -> float:
        """计算水平距离（忽略高度）"""
        return np.sqrt(
            (self.x - other.x)**2 +
            (self.y - other.y)**2
        )


@dataclass
class CommParams:
    """通信参数"""
    max_range_m: float = 30000  # 最大通信距离（米）
    min_height_m: float = 50     # 最小离地高度
    safety_margin_m: float = 10  # 地形安全余量


class LOSCommunicationModel:
    """
    LoS通信模型
    基于DEM地形的视距通信判定
    """

    def __init__(self, dem_data: Optional[np.ndarray] = None,
                 dem_bounds: Optional[Dict] = None,
                 comm_params: Optional[CommParams] = None):
        """
        初始化LoS通信模型

        Args:
            dem_data: DEM高程数据矩阵
            dem_bounds: DEM边界 {'min_x', 'max_x', 'min_y', 'max_y', 'resolution'}
            comm_params: 通信参数
        """
        self.dem_data = dem_data
        self.dem_bounds = dem_bounds
        self.comm_params = comm_params or CommParams()

        # 如果没有DEM数据，使用简化模型
        self.use_simplified = (dem_data is None)

    def check_los(self, pos1: Position, pos2: Position) -> Tuple[bool, Optional[str]]:
        """
        检查两点之间是否存在LoS通信

        Args:
            pos1: 发送端位置
            pos2: 接收端位置

        Returns:
            (is_los, reason): 是否可通信，以及不可通信的原因
        """
        # 1. 距离检查
        distance = pos1.distance_to(pos2)
        if distance > self.comm_params.max_range_m:
            return False, f"距离超限 ({distance:.0f}m > {self.comm_params.max_range_m}m)"

        # 2. 如果使用简化模型（无DEM），只检查距离
        if self.use_simplified:
            return True, None

        # 3. 地形遮挡检查（射线追踪）
        is_blocked, block_point = self._ray_trace_terrain(pos1, pos2)
        if is_blocked:
            return False, f"地形遮挡 at ({block_point[0]:.2f}, {block_point[1]:.2f})"

        return True, None

    def _ray_trace_terrain(self, pos1: Position, pos2: Position) -> Tuple[bool, Optional[Tuple]]:
        """
        射线追踪检测地形遮挡

        Args:
            pos1: 起点
            pos2: 终点

        Returns:
            (is_blocked, block_point): 是否被阻挡，阻挡点坐标
        """
        if self.dem_data is None:
            return False, None

        # 计算采样点数（每10米一个采样点）
        horizontal_dist = pos1.horizontal_distance_to(pos2)
        num_samples = max(10, int(horizontal_dist / 10))

        # 在两点之间均匀采样
        for i in range(1, num_samples):
            t = i / num_samples

            # 线性插值计算采样点位置
            sample_x = pos1.x + t * (pos2.x - pos1.x)
            sample_y = pos1.y + t * (pos2.y - pos1.y)
            sample_z = pos1.z + t * (pos2.z - pos1.z)

            # 获取该点的地形高度
            terrain_height = self._get_terrain_height(sample_x, sample_y)

            if terrain_height is None:
                continue  # 超出DEM范围

            # 检查是否被地形阻挡（考虑安全余量）
            if sample_z < terrain_height + self.comm_params.safety_margin_m:
                return True, (sample_x, sample_y)

        return False, None

    def _get_terrain_height(self, x: float, y: float) -> Optional[float]:
        """
        获取指定位置的地形高度（双线性插值）

        Args:
            x: 经度或UTM-X
            y: 纬度或UTM-Y

        Returns:
            地形高度（米），如果超出范围则返回None
        """
        if self.dem_data is None or self.dem_bounds is None:
            return None

        # 检查是否在DEM范围内
        if (x < self.dem_bounds['min_x'] or x > self.dem_bounds['max_x'] or
            y < self.dem_bounds['min_y'] or y > self.dem_bounds['max_y']):
            return None

        # 计算DEM矩阵索引
        resolution = self.dem_bounds['resolution']
        col = (x - self.dem_bounds['min_x']) / resolution
        row = (self.dem_bounds['max_y'] - y) / resolution

        # 边界检查
        if row < 0 or row >= self.dem_data.shape[0] - 1:
            return None
        if col < 0 or col >= self.dem_data.shape[1] - 1:
            return None

        # 双线性插值
        row_floor = int(np.floor(row))
        col_floor = int(np.floor(col))

        row_frac = row - row_floor
        col_frac = col - col_floor

        # 获取四个角点的高度
        h00 = self.dem_data[row_floor, col_floor]
        h01 = self.dem_data[row_floor, col_floor + 1]
        h10 = self.dem_data[row_floor + 1, col_floor]
        h11 = self.dem_data[row_floor + 1, col_floor + 1]

        # 双线性插值
        h0 = h00 * (1 - col_frac) + h01 * col_frac
        h1 = h10 * (1 - col_frac) + h11 * col_frac
        height = h0 * (1 - row_frac) + h1 * row_frac

        return float(height)

    def compute_coverage_area(self, transmitter: Position,
                             search_radius: Optional[float] = None,
                             grid_resolution: float = 100) -> List[Position]:
        """
        计算发射点的通信覆盖区域（Viewshed分析）

        Args:
            transmitter: 发射点位置
            search_radius: 搜索半径（米），默认使用max_range
            grid_resolution: 网格分辨率（米）

        Returns:
            覆盖区域内的点列表
        """
        if search_radius is None:
            search_radius = self.comm_params.max_range_m

        coverage_points = []

        # 在搜索半径内进行网格搜索
        x_min = transmitter.x - search_radius
        x_max = transmitter.x + search_radius
        y_min = transmitter.y - search_radius
        y_max = transmitter.y + search_radius

        x_range = np.arange(x_min, x_max, grid_resolution)
        y_range = np.arange(y_min, y_max, grid_resolution)

        for x in x_range:
            for y in y_range:
                # 获取地形高度
                terrain_height = self._get_terrain_height(x, y)
                if terrain_height is None:
                    continue

                # 假设接收端离地一定高度
                receiver_height = 10  # 运输机典型高度
                receiver = Position(x, y, terrain_height + receiver_height)

                # 检查LoS
                is_los, _ = self.check_los(transmitter, receiver)
                if is_los:
                    coverage_points.append(receiver)

        return coverage_points

    def identify_blind_zones(self, transport_path: List[Position],
                            gateway: Position) -> List[Tuple[int, int]]:
        """
        识别运输路径中的通信盲区

        Args:
            transport_path: 运输机飞行路径（位置序列）
            gateway: 固定网关位置

        Returns:
            通信盲区段列表 [(起始索引, 结束索引), ...]
        """
        blind_zones = []
        in_blind_zone = False
        blind_start = 0

        for i, pos in enumerate(transport_path):
            is_los, _ = self.check_los(pos, gateway)

            if not is_los and not in_blind_zone:
                # 进入盲区
                in_blind_zone = True
                blind_start = i
            elif is_los and in_blind_zone:
                # 离开盲区
                in_blind_zone = False
                blind_zones.append((blind_start, i - 1))

        # 如果路径结束时仍在盲区
        if in_blind_zone:
            blind_zones.append((blind_start, len(transport_path) - 1))

        return blind_zones


def test_los_model():
    """测试LoS通信模型"""
    print("="*80)
    print("测试LoS通信模型")
    print("="*80)

    # 创建简化模型（无DEM）
    model = LOSCommunicationModel()

    # 测试1：距离内通信
    pos1 = Position(0, 0, 100)
    pos2 = Position(1000, 1000, 150)
    is_los, reason = model.check_los(pos1, pos2)
    print(f"\n测试1 - 距离内通信:")
    print(f"  位置1: ({pos1.x}, {pos1.y}, {pos1.z})")
    print(f"  位置2: ({pos2.x}, {pos2.y}, {pos2.z})")
    print(f"  距离: {pos1.distance_to(pos2):.0f}m")
    print(f"  结果: {'可通信' if is_los else '不可通信'}")
    if reason:
        print(f"  原因: {reason}")

    # 测试2：距离超限
    pos3 = Position(0, 0, 100)
    pos4 = Position(50000, 50000, 150)
    is_los, reason = model.check_los(pos3, pos4)
    print(f"\n测试2 - 距离超限:")
    print(f"  位置1: ({pos3.x}, {pos3.y}, {pos3.z})")
    print(f"  位置2: ({pos4.x}, {pos4.y}, {pos4.z})")
    print(f"  距离: {pos3.distance_to(pos4):.0f}m")
    print(f"  结果: {'可通信' if is_los else '不可通信'}")
    if reason:
        print(f"  原因: {reason}")

    print("\n" + "="*80)
    print("LoS模型测试完成")
    print("="*80)


if __name__ == "__main__":
    test_los_model()
