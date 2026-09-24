#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为杯D题 - 能耗计算模块
实现无人机飞行能耗模型 (根据题目公式)
"""

import numpy as np
from typing import Tuple, Dict


class EnergyModel:
    """无人机能耗计算模型"""

    def __init__(self, uav_params: Dict):
        """
        初始化能耗模型

        Args:
            uav_params: 无人机参数字典，包含:
                - cruise_power_kw: 巡航功率 (kW)
                - cruise_speed_ms: 巡航速度 (m/s)
                - ascent_speed_ms: 爬升速度 (m/s)
                - descent_speed_ms: 下降速度 (m/s)
                - ascent_efficiency: 爬升能耗效率
                - descent_efficiency: 下降能耗效率
                - battery_capacity_kwh: 电池容量 (kWh)
                - battery_reserve_pct: 电量储备百分比
                - takeoff_time_s: 起飞时间 (s)
                - landing_time_s: 降落时间 (s)
        """
        self.uav_params = uav_params

    def calculate_energy_consumption(
        self,
        horizontal_distance_m: float,
        altitude_start_m: float,
        altitude_end_m: float,
        payload_kg: float = 0.0
    ) -> Dict:
        """
        计算飞行能耗

        Args:
            horizontal_distance_m: 水平距离 (m)
            altitude_start_m: 起点海拔 (m)
            altitude_end_m: 终点海拔 (m)
            payload_kg: 载荷重量 (kg)

        Returns:
            包含能耗详情的字典
        """
        payload_kg = max(0.0, float(payload_kg))
        # 1. 爬升/下降距离
        altitude_diff = altitude_end_m - altitude_start_m

        # 2. 爬升阶段
        if altitude_diff > 0:
            ascent_time_h = altitude_diff / (self.uav_params['ascent_speed_ms'] * 3600)
            ascent_energy_kwh = (
                self.uav_params['cruise_power_kw'] *
                self.uav_params['ascent_efficiency'] *
                ascent_time_h
            )
        else:
            ascent_time_h = 0
            ascent_energy_kwh = 0

        # 3. 下降阶段
        if altitude_diff < 0:
            descent_time_h = abs(altitude_diff) / (self.uav_params['descent_speed_ms'] * 3600)
            descent_energy_kwh = (
                self.uav_params['cruise_power_kw'] *
                self.uav_params['descent_efficiency'] *
                descent_time_h
            )
        else:
            descent_time_h = 0
            descent_energy_kwh = 0

        # 4. 水平巡航阶段
        cruise_time_h = horizontal_distance_m / (self.uav_params['cruise_speed_ms'] * 3600)
        # Appendix 2 supplies empty/full-load equivalent ranges. Use linear
        # interpolation by current payload so payload is not silently ignored.
        usable_capacity = self.uav_params['battery_capacity_kwh'] * (1.0 - self.uav_params['battery_reserve_pct'])
        equivalent_range_m = self.equivalent_range_m(payload_kg)
        cruise_energy_kwh = (horizontal_distance_m / equivalent_range_m * usable_capacity
                             if equivalent_range_m > 0 else float('inf'))

        # 5. 起飞和降落能耗 (按巡航功率的一定比例估算)
        takeoff_energy_kwh = (
            self.uav_params['cruise_power_kw'] *
            self.uav_params.get('takeoff_time_s', 30) / 3600
        )
        landing_energy_kwh = (
            self.uav_params['cruise_power_kw'] *
            self.uav_params.get('landing_time_s', 30) / 3600
        )

        # 6. 总能耗
        total_energy_kwh = (
            ascent_energy_kwh +
            descent_energy_kwh +
            cruise_energy_kwh +
            takeoff_energy_kwh +
            landing_energy_kwh
        )

        # 7. 总时间
        total_time_h = (
            ascent_time_h +
            descent_time_h +
            cruise_time_h +
            self.uav_params.get('takeoff_time_s', 30) / 3600 +
            self.uav_params.get('landing_time_s', 30) / 3600
        )

        return {
            'total_energy_kwh': total_energy_kwh,
            'total_time_h': total_time_h,
            'total_time_min': total_time_h * 60,
            'ascent_energy_kwh': ascent_energy_kwh,
            'descent_energy_kwh': descent_energy_kwh,
            'cruise_energy_kwh': cruise_energy_kwh,
            'takeoff_energy_kwh': takeoff_energy_kwh,
            'landing_energy_kwh': landing_energy_kwh,
            'ascent_time_h': ascent_time_h,
            'descent_time_h': descent_time_h,
            'cruise_time_h': cruise_time_h,
            'payload_kg': payload_kg,
        }

    def equivalent_range_m(self, payload_kg: float) -> float:
        """Interpolate the supplied empty/full-load range data."""
        empty = self.uav_params.get('empty_range_km', self.uav_params.get('max_range_km', 0.0)) * 1000.0
        full = self.uav_params.get('full_range_km', empty / 1000.0) * 1000.0
        max_payload = float(self.uav_params.get('max_load_kg', 0.0))
        if max_payload <= 0:
            return empty
        ratio = min(1.0, max(0.0, float(payload_kg) / max_payload))
        return empty + (full - empty) * ratio

    def calculate_round_trip_energy(
        self,
        depot_alt_m: float,
        service_area_alt_m: float,
        horizontal_distance_m: float,
        payload_kg: float = 0.0
    ) -> Dict:
        """
        计算往返能耗

        Args:
            depot_alt_m: 调度中心海拔 (m)
            service_area_alt_m: 服务区海拔 (m)
            horizontal_distance_m: 水平距离 (m)
            payload_kg: 载荷重量 (kg)

        Returns:
            往返能耗详情
        """
        # 去程 (带载荷)
        outbound = self.calculate_energy_consumption(
            horizontal_distance_m,
            depot_alt_m,
            service_area_alt_m,
            payload_kg
        )

        # 返程 (空载)
        inbound = self.calculate_energy_consumption(
            horizontal_distance_m,
            service_area_alt_m,
            depot_alt_m,
            0.0
        )

        # 总计
        total_energy = outbound['total_energy_kwh'] + inbound['total_energy_kwh']
        total_time = outbound['total_time_h'] + inbound['total_time_h']

        outbound_range_ok = 2.0 * horizontal_distance_m <= self.equivalent_range_m(payload_kg)
        inbound_range_ok = 2.0 * horizontal_distance_m <= self.equivalent_range_m(0.0)
        return {
            'total_energy_kwh': total_energy,
            'total_time_h': total_time,
            'total_time_min': total_time * 60,
            'outbound': outbound,
            'inbound': inbound,
            'battery_soc_used': total_energy / self.uav_params['battery_capacity_kwh'],
            'is_feasible': self.check_energy_feasibility(total_energy) and outbound_range_ok and inbound_range_ok,
            'outbound_range_m': self.equivalent_range_m(payload_kg),
            'inbound_range_m': self.equivalent_range_m(0.0),
            'outbound_range_feasible': outbound_range_ok,
            'inbound_range_feasible': inbound_range_ok,
        }

    def check_energy_feasibility(self, energy_required_kwh: float) -> bool:
        """
        检查能量可行性 (考虑电池储备)

        Args:
            energy_required_kwh: 所需能量

        Returns:
            是否可行
        """
        battery_capacity = self.uav_params['battery_capacity_kwh']
        reserve_pct = float(self.uav_params['battery_reserve_pct'])
        if reserve_pct > 1.0:
            reserve_pct /= 100.0
        usable_capacity = battery_capacity * (1 - reserve_pct)

        return energy_required_kwh <= usable_capacity

    def max_range_with_payload(self, payload_kg: float, altitude_diff_m: float = 0) -> float:
        """
        计算给定载荷下的最大航程

        Args:
            payload_kg: 载荷重量 (kg)
            altitude_diff_m: 高度差 (m)

        Returns:
            最大航程 (m)
        """
        battery_capacity = self.uav_params['battery_capacity_kwh']
        reserve_pct = float(self.uav_params['battery_reserve_pct'])
        if reserve_pct > 1.0:
            reserve_pct /= 100.0
        usable_capacity = battery_capacity * (1 - reserve_pct)

        # 简化模型: 假设能耗主要来自水平巡航
        # E = P * t = P * (d / v)
        # d = E * v / P

        cruise_power = self.uav_params['cruise_power_kw']
        cruise_speed = self.uav_params['cruise_speed_ms']

        # 扣除爬升/下降能耗
        if altitude_diff_m > 0:
            ascent_energy = (
                cruise_power *
                self.uav_params['ascent_efficiency'] *
                altitude_diff_m / (self.uav_params['ascent_speed_ms'] * 3600)
            )
        else:
            ascent_energy = (
                cruise_power *
                self.uav_params['descent_efficiency'] *
                abs(altitude_diff_m) / (self.uav_params['descent_speed_ms'] * 3600)
            )

        # 扣除起降能耗
        takeoff_landing_energy = (
            cruise_power *
            (self.uav_params.get('takeoff_time_s', 30) +
             self.uav_params.get('landing_time_s', 30)) / 3600
        )

        # 剩余能量用于巡航
        cruise_energy = usable_capacity - ascent_energy - takeoff_landing_energy

        if cruise_energy <= 0:
            return 0.0

        # 最大航程
        max_range_m = cruise_energy * cruise_speed * 3600 / cruise_power

        return max_range_m


def calculate_3d_distance(
    lon1: float, lat1: float, alt1: float,
    lon2: float, lat2: float, alt2: float
) -> Tuple[float, float]:
    """
    计算两点之间的3D距离

    Args:
        lon1, lat1, alt1: 点1的经纬度和海拔
        lon2, lat2, alt2: 点2的经纬度和海拔

    Returns:
        (水平距离(m), 3D直线距离(m))
    """
    # 地球平均半径 (m)
    R = 6371000

    # 转换为弧度
    lat1_rad = np.radians(lat1)
    lat2_rad = np.radians(lat2)
    delta_lat = np.radians(lat2 - lat1)
    delta_lon = np.radians(lon2 - lon1)

    # Haversine公式计算水平距离
    a = (np.sin(delta_lat / 2) ** 2 +
         np.cos(lat1_rad) * np.cos(lat2_rad) *
         np.sin(delta_lon / 2) ** 2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    horizontal_distance = R * c

    # 3D直线距离
    altitude_diff = alt2 - alt1
    distance_3d = np.sqrt(horizontal_distance ** 2 + altitude_diff ** 2)

    return horizontal_distance, distance_3d


def test_energy_model():
    """测试能耗模型"""
    print("="*60)
    print("能耗模型测试")
    print("="*60)

    # 示例无人机参数 (A型)
    uav_params = {
        'cruise_power_kw': 1.5,
        'cruise_speed_ms': 12.0,
        'ascent_speed_ms': 3.0,
        'descent_speed_ms': 2.0,
        'ascent_efficiency': 0.7,
        'descent_efficiency': 0.0,
        'battery_capacity_kwh': 3.2,
        'battery_reserve_pct': 20.0,
        'takeoff_time_s': 30,
        'landing_time_s': 30
    }

    model = EnergyModel(uav_params)

    # 测试1: 计算往返能耗
    print("\n测试1: 往返能耗计算")
    print("-" * 60)
    depot_alt = 127.7
    service_alt = 260.0
    horizontal_dist = 5000  # 5km

    result = model.calculate_round_trip_energy(
        depot_alt, service_alt, horizontal_dist, payload_kg=50
    )

    print(f"调度中心海拔: {depot_alt}m")
    print(f"服务区海拔: {service_alt}m")
    print(f"水平距离: {horizontal_dist}m")
    print(f"载荷: 50kg")
    print()
    print(f"总能耗: {result['total_energy_kwh']:.4f} kWh")
    print(f"总时间: {result['total_time_min']:.2f} 分钟")
    print(f"电池SOC使用: {result['battery_soc_used']*100:.1f}%")
    print(f"是否可行: {result['is_feasible']}")

    # 测试2: 3D距离计算
    print("\n\n测试2: 3D距离计算")
    print("-" * 60)
    lon1, lat1, alt1 = 109.230852, 23.008509, 127.7
    lon2, lat2, alt2 = 109.2432319, 23.0335927, 154.0

    h_dist, d_3d = calculate_3d_distance(lon1, lat1, alt1, lon2, lat2, alt2)

    print(f"点1: ({lon1}, {lat1}, {alt1}m)")
    print(f"点2: ({lon2}, {lat2}, {alt2}m)")
    print(f"水平距离: {h_dist:.2f}m")
    print(f"3D距离: {d_3d:.2f}m")

    # 测试3: 最大航程
    print("\n\n测试3: 最大航程计算")
    print("-" * 60)
    for payload in [0, 25, 50, 70]:
        max_range = model.max_range_with_payload(payload, altitude_diff_m=100)
        print(f"载荷 {payload}kg: 最大航程 {max_range/1000:.2f}km")

    print("\n" + "="*60)


if __name__ == "__main__":
    test_energy_model()
