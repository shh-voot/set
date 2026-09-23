#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电池管理模块
包括电池池管理、充电调度、SOC追踪
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class BatteryState(Enum):
    """电池状态"""
    IDLE = "idle"              # 空闲可用
    IN_USE = "in_use"          # 使用中
    CHARGING = "charging"      # 充电中
    DEPLETED = "depleted"      # 耗尽待充


@dataclass
class Battery:
    """电池对象"""
    battery_id: int
    capacity_kwh: float         # 容量 (kWh)
    soc: float = 1.0           # 当前SOC [0, 1]
    state: BatteryState = BatteryState.IDLE
    charge_start_time: Optional[float] = None
    charge_end_time: Optional[float] = None
    cycles: int = 0            # 充电循环次数


def calculate_charging_time(
    current_soc: float,
    target_soc: float,
    capacity_kwh: float,
    charger_power_kw: float,
    efficiency: float = 0.90
) -> float:
    """
    计算充电时间（两阶段模型）

    Args:
        current_soc: 当前SOC
        target_soc: 目标SOC
        capacity_kwh: 电池容量
        charger_power_kw: 充电功率
        efficiency: 充电效率

    Returns:
        充电时间（小时）
    """
    if current_soc >= target_soc:
        return 0.0

    energy_needed = capacity_kwh * (target_soc - current_soc)

    # 两阶段模型：0-80% 快充，80-100% 涓流
    FAST_CHARGE_THRESHOLD = 0.80
    TAPER_POWER_RATIO = 0.3  # 涓流阶段功率降至30%

    if target_soc <= FAST_CHARGE_THRESHOLD:
        # 全程快充
        avg_power = charger_power_kw
    elif current_soc >= FAST_CHARGE_THRESHOLD:
        # 全程涓流
        avg_power = charger_power_kw * TAPER_POWER_RATIO
    else:
        # 跨越两个阶段
        fast_portion = FAST_CHARGE_THRESHOLD - current_soc
        taper_portion = target_soc - FAST_CHARGE_THRESHOLD
        total_portion = target_soc - current_soc

        avg_power = (
            (fast_portion * charger_power_kw +
             taper_portion * charger_power_kw * TAPER_POWER_RATIO)
            / total_portion
        )

    charge_time = energy_needed / (avg_power * efficiency)
    return charge_time


class ChargerStation:
    """充电站"""

    def __init__(self, num_chargers: int, power_per_charger_kw: float):
        """
        初始化充电站

        Args:
            num_chargers: 充电桩数量
            power_per_charger_kw: 每个充电桩功率
        """
        self.num_chargers = num_chargers
        self.power_per_charger = power_per_charger_kw
        self.charging_batteries: List[Battery] = []
        self.charge_queue: List[Battery] = []

    def is_full(self) -> bool:
        """充电桩是否全部占用"""
        return len(self.charging_batteries) >= self.num_chargers

    def add_to_charge(self, battery: Battery, current_time: float) -> bool:
        """
        开始充电

        Args:
            battery: 电池对象
            current_time: 当前时间

        Returns:
            是否成功开始充电
        """
        if not self.is_full():
            battery.state = BatteryState.CHARGING
            battery.charge_start_time = current_time

            # 计算完成时间
            charge_time = calculate_charging_time(
                battery.soc, 1.0,
                battery.capacity_kwh,
                self.power_per_charger
            )
            battery.charge_end_time = current_time + charge_time * 60  # 转换为分钟

            self.charging_batteries.append(battery)
            return True
        else:
            # 排队
            self.charge_queue.append(battery)
            battery.state = BatteryState.DEPLETED
            return False

    def complete_charging(self, current_time: float) -> List[Battery]:
        """
        完成充电并开始排队的下一个

        Args:
            current_time: 当前时间

        Returns:
            完成充电的电池列表
        """
        completed = [
            b for b in self.charging_batteries
            if b.charge_end_time <= current_time
        ]

        for battery in completed:
            battery.soc = 1.0
            battery.state = BatteryState.IDLE
            battery.cycles += 1
            self.charging_batteries.remove(battery)

            # 开始排队的下一个
            if self.charge_queue:
                next_battery = self.charge_queue.pop(0)
                self.add_to_charge(next_battery, current_time)

        return completed

    def get_next_completion_time(self) -> Optional[float]:
        """获取下一个充电完成时间"""
        if self.charging_batteries:
            return min(b.charge_end_time for b in self.charging_batteries)
        return None

    def get_queue_length(self) -> int:
        """获取排队长度"""
        return len(self.charge_queue)


class BatteryPool:
    """电池池管理器"""

    def __init__(
        self,
        num_batteries: int,
        capacity_per_battery_kwh: float,
        charger_station: ChargerStation
    ):
        """
        初始化电池池

        Args:
            num_batteries: 电池数量
            capacity_per_battery_kwh: 每个电池容量
            charger_station: 充电站
        """
        self.batteries = [
            Battery(i, capacity_per_battery_kwh)
            for i in range(num_batteries)
        ]
        self.charger = charger_station
        self.available_batteries: List[Battery] = list(self.batteries)
        self.in_use_batteries: List[Battery] = []

    def get_available_battery(self, min_soc: float = 0.95) -> Optional[Battery]:
        """
        获取可用电池

        Args:
            min_soc: 最小SOC要求

        Returns:
            电池对象，如果无可用电池返回None
        """
        charged = [b for b in self.available_batteries if b.soc >= min_soc]
        if charged:
            battery = charged[0]
            self.available_batteries.remove(battery)
            self.in_use_batteries.append(battery)
            battery.state = BatteryState.IN_USE
            return battery
        return None

    def return_battery(self, battery: Battery, current_time: float):
        """
        归还电池

        Args:
            battery: 电池对象
            current_time: 当前时间
        """
        if battery in self.in_use_batteries:
            self.in_use_batteries.remove(battery)

        if battery.soc < 1.0:
            # 需要充电
            battery.state = BatteryState.DEPLETED
            self.charger.add_to_charge(battery, current_time)
        else:
            # 已满电，直接可用
            battery.state = BatteryState.IDLE
            self.available_batteries.append(battery)

    def process_charge_completions(self, current_time: float):
        """
        处理充电完成事件

        Args:
            current_time: 当前时间
        """
        completed = self.charger.complete_charging(current_time)
        self.available_batteries.extend(completed)

    def get_status(self) -> Dict:
        """获取电池池状态"""
        return {
            'total': len(self.batteries),
            'available': len([b for b in self.available_batteries if b.soc >= 0.95]),
            'charging': len(self.charger.charging_batteries),
            'in_queue': self.charger.get_queue_length(),
            'in_use': len(self.in_use_batteries),
            'avg_soc': np.mean([b.soc for b in self.batteries]),
            'min_soc': min([b.soc for b in self.batteries]),
        }

    def has_stockout(self, min_soc: float = 0.95) -> bool:
        """
        检查是否缺货（无可用电池）

        Args:
            min_soc: 最小SOC要求

        Returns:
            是否缺货
        """
        return len([b for b in self.available_batteries if b.soc >= min_soc]) == 0


def test_battery_manager():
    """测试电池管理模块"""
    print("="*80)
    print("测试电池管理模块")
    print("="*80)

    # 创建充电站（2个充电桩，每个5kW）
    charger = ChargerStation(num_chargers=2, power_per_charger_kw=5.0)

    # 创建电池池（5个电池，每个4kWh）
    battery_pool = BatteryPool(
        num_batteries=5,
        capacity_per_battery_kwh=4.0,
        charger_station=charger
    )

    print("\n初始状态:")
    status = battery_pool.get_status()
    for k, v in status.items():
        print(f"  {k}: {v}")

    # 模拟使用电池
    print("\n模拟使用3个电池:")
    batteries_in_use = []
    for i in range(3):
        battery = battery_pool.get_available_battery()
        if battery:
            print(f"  获取电池 {battery.battery_id}")
            # 模拟消耗到30% SOC
            battery.soc = 0.30
            batteries_in_use.append(battery)

    # 归还电池并充电
    print("\n归还电池并开始充电:")
    current_time = 0.0
    for battery in batteries_in_use:
        battery_pool.return_battery(battery, current_time)
        print(f"  归还电池 {battery.battery_id}, SOC={battery.soc:.1%}")

    status = battery_pool.get_status()
    print(f"\n当前状态:")
    for k, v in status.items():
        print(f"  {k}: {v}")

    # 检查下一个完成时间
    next_time = charger.get_next_completion_time()
    if next_time:
        print(f"\n下一个充电完成时间: {next_time:.1f} 分钟")

        # 模拟时间推进
        print(f"\n时间推进到 {next_time:.1f} 分钟...")
        battery_pool.process_charge_completions(next_time)

        status = battery_pool.get_status()
        print(f"\n完成后状态:")
        for k, v in status.items():
            print(f"  {k}: {v}")

    print("\n" + "="*80)
    print("电池管理模块测试完成")
    print("="*80)


if __name__ == "__main__":
    test_battery_manager()
