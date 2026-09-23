#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为杯D题 - 电池管理模块
实现电池充电调度和SOC管理
"""

import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum


class BatteryState(Enum):
    """电池状态"""
    IDLE = "idle"           # 待机，可用
    CHARGING = "charging"   # 充电中
    IN_USE = "in_use"      # 使用中
    DEPLETED = "depleted"   # 待充电


@dataclass
class Battery:
    """电池类"""
    battery_id: int
    capacity_kwh: float
    soc: float = 1.0  # State of Charge [0.0, 1.0]
    state: BatteryState = BatteryState.IDLE
    charge_start_time: Optional[float] = None
    charge_end_time: Optional[float] = None
    cycles: int = 0  # 充电循环次数

    def energy_available(self) -> float:
        """可用能量 (kWh)"""
        return self.capacity_kwh * self.soc

    def energy_needed(self, target_soc: float = 1.0) -> float:
        """充满所需能量 (kWh)"""
        return self.capacity_kwh * (target_soc - self.soc)

    def update_soc(self, energy_change_kwh: float) -> None:
        """更新SOC"""
        self.soc += energy_change_kwh / self.capacity_kwh
        self.soc = max(0.0, min(1.0, self.soc))  # 限制在[0, 1]


class BatteryManager:
    """电池管理器 - 处理充电调度"""

    def __init__(
        self,
        num_batteries: int,
        battery_capacity_kwh: float,
        charge_power_kw: float = 5.0,
        num_chargers: int = None
    ):
        """
        初始化电池管理器

        Args:
            num_batteries: 电池总数
            battery_capacity_kwh: 单块电池容量 (kWh)
            charge_power_kw: 充电功率 (kW)
            num_chargers: 充电器数量 (None表示无限制)
        """
        self.batteries = [
            Battery(i, battery_capacity_kwh)
            for i in range(num_batteries)
        ]
        self.charge_power_kw = charge_power_kw
        self.num_chargers = num_chargers if num_chargers is not None else num_batteries

        # 充电队列
        self.charging_batteries: List[Battery] = []
        self.charge_queue: List[Battery] = []

    def get_available_battery(self, min_soc: float = 0.95) -> Optional[Battery]:
        """
        获取一块可用电池

        Args:
            min_soc: 最低SOC要求

        Returns:
            可用电池，如果没有则返回None
        """
        available = [
            b for b in self.batteries
            if b.state == BatteryState.IDLE and b.soc >= min_soc
        ]

        if available:
            battery = available[0]
            battery.state = BatteryState.IN_USE
            return battery

        return None

    def return_battery(self, battery: Battery, current_time: float) -> None:
        """
        归还使用过的电池

        Args:
            battery: 电池对象
            current_time: 当前时间
        """
        battery.state = BatteryState.DEPLETED

        # 检查是否需要充电
        if battery.soc < 0.95:
            self.add_to_charge(battery, current_time)
        else:
            battery.state = BatteryState.IDLE

    def add_to_charge(self, battery: Battery, current_time: float) -> bool:
        """
        将电池加入充电队列

        Args:
            battery: 电池对象
            current_time: 当前时间

        Returns:
            是否立即开始充电
        """
        # 检查充电器是否有空位
        if len(self.charging_batteries) < self.num_chargers:
            # 立即开始充电
            battery.state = BatteryState.CHARGING
            battery.charge_start_time = current_time

            # 计算充电时间 (两阶段模型)
            charge_time_h = self.calculate_charging_time(
                battery.soc, 1.0, battery.capacity_kwh
            )
            battery.charge_end_time = current_time + charge_time_h

            self.charging_batteries.append(battery)
            return True
        else:
            # 加入队列等待
            self.charge_queue.append(battery)
            return False

    def calculate_charging_time(
        self,
        soc_start: float,
        soc_target: float,
        capacity_kwh: float
    ) -> float:
        """
        两阶段充电模型 (来自文献)

        Args:
            soc_start: 起始SOC
            soc_target: 目标SOC
            capacity_kwh: 电池容量

        Returns:
            充电时间 (小时)
        """
        FAST_THRESHOLD = 0.80  # 80% SOC以下快充
        TAPER_RATE = 0.4       # 涓流充电功率比例
        EFFICIENCY = 0.85      # 充电效率

        energy_needed = capacity_kwh * (soc_target - soc_start)

        if soc_target <= FAST_THRESHOLD:
            # 全程快充
            return energy_needed / (self.charge_power_kw * EFFICIENCY)

        elif soc_start >= FAST_THRESHOLD:
            # 全程涓流
            avg_power = self.charge_power_kw * (1 + TAPER_RATE) / 2
            return energy_needed / (avg_power * EFFICIENCY)

        else:
            # 跨越两阶段
            fast_energy = capacity_kwh * (FAST_THRESHOLD - soc_start)
            taper_energy = capacity_kwh * (soc_target - FAST_THRESHOLD)

            t_fast = fast_energy / (self.charge_power_kw * EFFICIENCY)
            t_taper = taper_energy / (self.charge_power_kw * TAPER_RATE * EFFICIENCY)

            return t_fast + t_taper

    def update(self, current_time: float) -> List[Battery]:
        """
        更新电池状态 (处理充电完成事件)

        Args:
            current_time: 当前时间

        Returns:
            充电完成的电池列表
        """
        completed = []

        # 检查充电完成
        for battery in self.charging_batteries[:]:
            if battery.charge_end_time <= current_time:
                # 充电完成
                battery.soc = 1.0
                battery.state = BatteryState.IDLE
                battery.cycles += 1

                self.charging_batteries.remove(battery)
                completed.append(battery)

                # 从队列中取下一块电池充电
                if self.charge_queue:
                    next_battery = self.charge_queue.pop(0)
                    self.add_to_charge(next_battery, current_time)

        return completed

    def get_next_completion_time(self) -> Optional[float]:
        """
        获取下一个充电完成时间 (用于事件调度)

        Returns:
            下一个完成时间，如果没有则返回None
        """
        if self.charging_batteries:
            return min(b.charge_end_time for b in self.charging_batteries)
        return None

    def get_status(self) -> Dict:
        """
        获取电池管理状态

        Returns:
            状态字典
        """
        idle_batteries = [b for b in self.batteries if b.state == BatteryState.IDLE]
        in_use = [b for b in self.batteries if b.state == BatteryState.IN_USE]

        return {
            'total_batteries': len(self.batteries),
            'available': len([b for b in idle_batteries if b.soc >= 0.95]),
            'charging': len(self.charging_batteries),
            'in_queue': len(self.charge_queue),
            'in_use': len(in_use),
            'avg_soc': np.mean([b.soc for b in self.batteries]),
            'min_soc': min(b.soc for b in self.batteries),
            'max_cycles': max(b.cycles for b in self.batteries)
        }


class BatteryPool:
    """
    电池池 - 用于无人机群的电池管理
    支持换电操作
    """

    def __init__(
        self,
        num_batteries: int,
        battery_capacity_kwh: float,
        charge_power_kw: float = 5.0,
        num_chargers: int = None
    ):
        self.manager = BatteryManager(
            num_batteries,
            battery_capacity_kwh,
            charge_power_kw,
            num_chargers
        )

    def request_battery(self, min_soc: float = 0.95) -> Optional[Battery]:
        """请求一块电池 (换电)"""
        return self.manager.get_available_battery(min_soc)

    def return_battery(self, battery: Battery, current_time: float) -> None:
        """归还电池"""
        self.manager.return_battery(battery, current_time)

    def update(self, current_time: float) -> List[Battery]:
        """更新状态"""
        return self.manager.update(current_time)

    def get_status(self) -> Dict:
        """获取状态"""
        return self.manager.get_status()


def test_battery_manager():
    """测试电池管理器"""
    print("="*60)
    print("电池管理器测试")
    print("="*60)

    # 创建电池管理器
    # 10块电池，每块3.2kWh，5kW充电功率，2个充电器
    manager = BatteryManager(
        num_batteries=10,
        battery_capacity_kwh=3.2,
        charge_power_kw=5.0,
        num_chargers=2
    )

    print(f"\n初始状态:")
    status = manager.get_status()
    print(f"  总电池数: {status['total_batteries']}")
    print(f"  可用: {status['available']}")
    print(f"  平均SOC: {status['avg_soc']:.2%}")

    # 模拟使用场景
    current_time = 0.0

    print(f"\n\n模拟1: 获取电池并使用")
    print("-" * 60)

    # 获取3块电池
    batteries_in_use = []
    for i in range(3):
        battery = manager.get_available_battery()
        if battery:
            print(f"获取电池 #{battery.battery_id}, SOC={battery.soc:.2%}")
            batteries_in_use.append(battery)

    # 使用后归还 (消耗50%电量)
    current_time += 0.5  # 30分钟后

    print(f"\n归还电池 (消耗50%电量):")
    for battery in batteries_in_use:
        battery.update_soc(-0.5 * battery.capacity_kwh)
        print(f"  电池 #{battery.battery_id}, SOC={battery.soc:.2%}")
        manager.return_battery(battery, current_time)

    status = manager.get_status()
    print(f"\n当前状态:")
    print(f"  可用: {status['available']}")
    print(f"  充电中: {status['charging']}")
    print(f"  队列中: {status['in_queue']}")

    # 推进时间到充电完成
    print(f"\n\n模拟2: 充电过程")
    print("-" * 60)

    for t in np.arange(current_time, current_time + 3, 0.5):
        completed = manager.update(t)
        if completed:
            print(f"时间 {t:.1f}h: {len(completed)} 块电池充电完成")
            for b in completed:
                print(f"  电池 #{b.battery_id}, SOC={b.soc:.2%}, 循环次数={b.cycles}")

        status = manager.get_status()
        if status['charging'] > 0 or status['in_queue'] > 0:
            print(f"时间 {t:.1f}h: 充电中={status['charging']}, 队列={status['in_queue']}")

    print(f"\n\n最终状态:")
    status = manager.get_status()
    print(f"  可用: {status['available']}")
    print(f"  平均SOC: {status['avg_soc']:.2%}")
    print(f"  最大循环次数: {status['max_cycles']}")

    print("\n" + "="*60)


if __name__ == "__main__":
    test_battery_manager()
