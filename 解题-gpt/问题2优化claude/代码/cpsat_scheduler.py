#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CP-SAT精确调度模块 - 内层优化器

给定架次列表（包含货箱、路线、机型），求解：
1. 每个架次分配的具体无人机ID
2. 每个架次使用的电池ID
3. 每个架次的起飞时刻
4. 电池充电周转时序

使用Google OR-Tools CP-SAT求解器进行精确建模。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ortools.sat.python import cp_model


@dataclass
class Mission:
    """架次信息"""
    mission_id: int
    area_id: str
    uav_type: str
    cargo_ids: List[str]
    energy_kwh: float
    duration_min: float
    delivery_offset_min: float
    deadline_min: float


@dataclass
class ScheduleResult:
    """调度结果"""
    success: bool
    makespan_min: float
    missions: List[Dict]
    cargo_deliveries: List[Dict]
    objective_value: Optional[float] = None
    solve_time_sec: Optional[float] = None


def calculate_charging_time_minutes(soc_after: float, full_charge_min: float) -> float:
    """计算充电时间（分钟）

    两阶段充电模型：
    - 0% -> 90%: 占总时间的65%
    - 90% -> 100%: 占总时间的35%
    """
    if soc_after >= 1.0:
        return 0.0
    elif soc_after >= 0.90:
        return full_charge_min * 0.35 * (1.0 - soc_after) / 0.10
    else:
        return full_charge_min * (0.65 * (0.90 - soc_after) / 0.90 + 0.35)


class CPSATScheduler:
    """CP-SAT约束规划调度器"""

    def __init__(self, types: Dict, cargo_by_id, time_limit_sec: int = 300):
        self.types = types
        self.cargo_by_id = cargo_by_id
        self.time_limit_sec = time_limit_sec

        # 时间精度：使用整数表示0.1分钟
        self.TIME_SCALE = 10  # 1分钟 = 10个单位
        self.MAX_TIME = 500 * self.TIME_SCALE  # 最大500分钟

    def _time_to_int(self, minutes: float) -> int:
        """将浮点分钟转换为整数时间单位"""
        return int(minutes * self.TIME_SCALE)

    def _int_to_time(self, units: int) -> float:
        """将整数时间单位转换为浮点分钟"""
        return units / self.TIME_SCALE

    def schedule(self, missions: List[Mission]) -> ScheduleResult:
        """求解架次调度问题

        决策变量：
        - start[m]: 架次m的起飞时间
        - uav[m]: 架次m分配的无人机编号
        - battery[m]: 架次m使用的电池编号
        - battery_available[b]: 电池b的下次可用时间

        约束：
        1. 每个架次必须分配一架同型号无人机
        2. 每个架次必须分配一组同型号电池
        3. 无人机在执行任务时不可用
        4. 电池在使用和充电时不可用
        5. 货箱必须在deadline前送达
        """
        model = cp_model.CpModel()

        # 按机型组织资源
        uav_fleet = {}
        battery_pool = {}
        for typ, params in self.types.items():
            uav_count = int(params['count'])
            battery_count = int(params['battery_count'])
            uav_fleet[typ] = list(range(uav_count))
            battery_pool[typ] = list(range(battery_count))

        # 决策变量
        start = {}  # start[m] = 架次m的起飞时间（整数单位）
        end = {}    # end[m] = 架次m的结束时间
        uav_assign = {}  # uav_assign[m] = 分配的无人机编号
        battery_assign = {}  # battery_assign[m] = 分配的电池编号

        for m in missions:
            mid = m.mission_id
            duration_int = self._time_to_int(m.duration_min)

            # 起飞时间变量
            start[mid] = model.NewIntVar(0, self.MAX_TIME, f'start_{mid}')
            end[mid] = model.NewIntVar(0, self.MAX_TIME, f'end_{mid}')
            model.Add(end[mid] == start[mid] + duration_int)

            # 无人机分配（同型号内选择）
            typ = m.uav_type
            uav_assign[mid] = model.NewIntVar(
                0, len(uav_fleet[typ]) - 1, f'uav_{mid}'
            )

            # 电池分配（同型号内选择）
            battery_assign[mid] = model.NewIntVar(
                0, len(battery_pool[typ]) - 1, f'bat_{mid}'
            )

        # 约束1: 无人机不能同时执行多个任务
        for typ in uav_fleet:
            typ_missions = [m for m in missions if m.uav_type == typ]
            for uav_idx in range(len(uav_fleet[typ])):
                intervals = []
                for m in typ_missions:
                    mid = m.mission_id
                    # 创建可选区间：当且仅当该任务分配给这架无人机
                    is_assigned = model.NewBoolVar(f'uav_{mid}_is_{uav_idx}')
                    model.Add(uav_assign[mid] == uav_idx).OnlyEnforceIf(is_assigned)
                    model.Add(uav_assign[mid] != uav_idx).OnlyEnforceIf(is_assigned.Not())

                    duration_int = self._time_to_int(m.duration_min)
                    interval = model.NewOptionalIntervalVar(
                        start[mid], duration_int, end[mid],
                        is_assigned, f'uav_interval_{mid}_{uav_idx}'
                    )
                    intervals.append(interval)

                # 无重叠约束
                if intervals:
                    model.AddNoOverlap(intervals)

        # 约束2: 电池不能同时被使用或充电
        for typ in battery_pool:
            typ_missions = [m for m in missions if m.uav_type == typ]
            params = self.types[typ]
            capacity = float(params['battery_capacity_kwh'])
            full_charge_min = float(params['full_charge_time_min'])

            for bat_idx in range(len(battery_pool[typ])):
                intervals = []
                for m in typ_missions:
                    mid = m.mission_id
                    # 创建可选区间：当且仅当该任务使用这块电池
                    is_assigned = model.NewBoolVar(f'bat_{mid}_is_{bat_idx}')
                    model.Add(battery_assign[mid] == bat_idx).OnlyEnforceIf(is_assigned)
                    model.Add(battery_assign[mid] != bat_idx).OnlyEnforceIf(is_assigned.Not())

                    # 电池占用时间 = 任务时间 + 充电时间
                    soc_after = 1.0 - m.energy_kwh / capacity
                    charge_min = calculate_charging_time_minutes(soc_after, full_charge_min)
                    total_min = m.duration_min + charge_min
                    total_int = self._time_to_int(total_min)

                    bat_end = model.NewIntVar(0, self.MAX_TIME, f'bat_end_{mid}')
                    model.Add(bat_end == start[mid] + total_int).OnlyEnforceIf(is_assigned)

                    interval = model.NewOptionalIntervalVar(
                        start[mid], total_int, bat_end,
                        is_assigned, f'bat_interval_{mid}_{bat_idx}'
                    )
                    intervals.append(interval)

                # 无重叠约束
                if intervals:
                    model.AddNoOverlap(intervals)

        # 约束3: 货箱时限约束
        for m in missions:
            mid = m.mission_id
            delivery_offset_int = self._time_to_int(m.delivery_offset_min)
            deadline_int = self._time_to_int(m.deadline_min)

            delivery_time = model.NewIntVar(0, self.MAX_TIME, f'delivery_{mid}')
            model.Add(delivery_time == start[mid] + delivery_offset_int)
            model.Add(delivery_time <= deadline_int)

        # 目标：最小化完成时间（makespan）
        makespan = model.NewIntVar(0, self.MAX_TIME, 'makespan')
        for mid in end:
            model.Add(makespan >= end[mid])

        model.Minimize(makespan)

        # 求解
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_sec
        solver.parameters.log_search_progress = False

        status = solver.Solve(model)

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return self._extract_solution(
                missions, solver, start, end, uav_assign, battery_assign, makespan
            )
        else:
            status_name = solver.StatusName(status)
            print(f"    [CP-SAT] 调度失败: {status_name}, 任务数={len(missions)}")
            if len(missions) <= 5:
                print(f"    任务详情: {[(m.mission_id, m.uav_type, m.route) for m in missions]}")
            return ScheduleResult(
                success=False, makespan_min=float('inf'),
                missions=[], cargo_deliveries=[]
            )

    def _extract_solution(
        self, missions: List[Mission], solver, start, end,
        uav_assign, battery_assign, makespan
    ) -> ScheduleResult:
        """提取求解结果"""
        mission_results = []
        cargo_results = []

        for m in missions:
            mid = m.mission_id
            typ = m.uav_type
            params = self.types[typ]

            start_min = self._int_to_time(solver.Value(start[mid]))
            end_min = self._int_to_time(solver.Value(end[mid]))
            delivery_min = start_min + m.delivery_offset_min

            uav_idx = solver.Value(uav_assign[mid])
            bat_idx = solver.Value(battery_assign[mid])

            uav_id = f"U{typ}{uav_idx + 1:02d}"
            battery_id = f"{typ}-BAT-{bat_idx + 1:02d}"

            # 计算SOC和充电时间
            capacity = float(params['battery_capacity_kwh'])
            soc_after = 1.0 - m.energy_kwh / capacity
            charge_min = calculate_charging_time_minutes(
                soc_after, float(params['full_charge_time_min'])
            )

            mission_results.append({
                'mission_id': mid,
                'area_id': m.area_id,
                'uav_type': typ,
                'cargo_ids': m.cargo_ids,
                'cargo_count': len(m.cargo_ids),
                'energy_kwh': m.energy_kwh,
                'duration_min': m.duration_min,
                'delivery_offset_min': m.delivery_offset_min,
                'deadline_min': m.deadline_min,
                'uav_id': uav_id,
                'battery_id': battery_id,
                'start_min': start_min,
                'delivery_min': delivery_min,
                'end_min': end_min,
                'on_time': delivery_min <= m.deadline_min + 1e-9,
                'soc_after': soc_after,
                'charge_min': charge_min
            })

            # 逐箱送达信息
            for cargo_id in m.cargo_ids:
                cargo_results.append({
                    'cargo_id': cargo_id,
                    'mission_id': mid,
                    'area_id': m.area_id,
                    'delivery_min': delivery_min,
                    'deadline_min': m.deadline_min,
                    'on_time': delivery_min <= m.deadline_min + 1e-9
                })

        makespan_min = self._int_to_time(solver.Value(makespan))

        return ScheduleResult(
            success=True,
            makespan_min=makespan_min,
            missions=mission_results,
            cargo_deliveries=cargo_results,
            objective_value=solver.ObjectiveValue(),
            solve_time_sec=solver.WallTime()
        )
