#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NSGA-II外层优化器 - 多目标遗传算法

优化目标：
1. 最小化架次数
2. 最小化总能耗
3. 最小化完成时间

编码方式：
- 染色体 = [货箱分组方案, 访问顺序, 机型选择]
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Individual:
    """个体（候选解）"""
    groups: List[List[str]]  # 货箱分组，每组是一个架次携带的货箱ID列表
    routes: List[List[str]]  # 每个架次的服务区访问顺序
    types: List[str]  # 每个架次的机型

    # 评估结果
    objectives: Optional[Tuple[float, float, float]] = None  # (架次数, 能耗, 时间)
    feasible: bool = False
    rank: int = 0  # 非支配排序等级
    crowding_distance: float = 0.0  # 拥挤度

    # 详细信息（用于输出）
    missions: Optional[List] = None
    cargo_deliveries: Optional[List] = None


class NSGAIIOptimizer:
    """NSGA-II多目标遗传算法优化器"""

    def __init__(
        self,
        cargo_by_id,
        types: Dict,
        areas: Dict,
        depot: Dict,
        dem,
        direct_mission_func,
        cpsat_scheduler,
        pop_size: int = 50,
        max_generations: int = 100,
        crossover_prob: float = 0.9,
        mutation_prob: float = 0.2,
        seed: int = 42
    ):
        self.cargo_by_id = cargo_by_id
        self.types = types
        self.areas = areas
        self.depot = depot
        self.dem = dem
        self.direct_mission_func = direct_mission_func
        self.cpsat_scheduler = cpsat_scheduler

        self.pop_size = pop_size
        self.max_generations = max_generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.rng = random.Random(seed)
        np.random.seed(seed)

        # 输出货箱统计信息
        print("\n货箱统计信息:")
        print(f"  总货箱数: {len(cargo_by_id)}")
        print(f"  单箱质量范围: {cargo_by_id['单箱质量（kg）'].min():.1f} - {cargo_by_id['单箱质量（kg）'].max():.1f} kg")
        print(f"  平均单箱质量: {cargo_by_id['单箱质量（kg）'].mean():.1f} kg")
        print(f"  总重量: {cargo_by_id['单箱质量（kg）'].sum():.1f} kg")

        # 按服务区统计
        area_stats = {}
        for cid, row in cargo_by_id.iterrows():
            area = row['服务区编号']
            if area not in area_stats:
                area_stats[area] = {'count': 0, 'weight': 0.0}
            area_stats[area]['count'] += 1
            area_stats[area]['weight'] += row['单箱质量（kg）']

        print("\n各服务区货箱统计:")
        for area in sorted(area_stats.keys()):
            stats = area_stats[area]
            print(f"  {area}: {stats['count']}箱, 总重{stats['weight']:.1f}kg, 平均{stats['weight']/stats['count']:.1f}kg/箱")

        print("\n无人机载重限制:")
        for uav_type, params in types.items():
            print(f"  {uav_type}型: 最大载重{params['max_load_kg']}kg, 最大体积{params['max_volume_m3']}立方米")
        print()

        # 按服务区组织货箱
        self.cargo_by_area = self._group_cargo_by_area()

    def _group_cargo_by_area(self) -> Dict[str, List]:
        """按服务区组织货箱"""
        area_cargo = {}
        for cargo_id, row in self.cargo_by_id.iterrows():
            area_id = row['服务区编号']
            if area_id not in area_cargo:
                area_cargo[area_id] = []
            area_cargo[area_id].append({
                '货箱编号': cargo_id,
                '质量（kg）': row['单箱质量（kg）'],
                '体积（m³）': row['单箱体积（m³）'],
                '服务区编号': area_id,
                '是否首批保障': row.get('是否首批保障', '否'),
                '首批截止时间（s）': row.get('首批截止时间（s）', None),
                '期望送达时间（s）': row['期望送达时间（s）']
            })
        return area_cargo

    def _get_deadline_minutes(self, cargo_info) -> float:
        """获取货箱截止时间（分钟）"""
        if cargo_info.get('是否首批保障') == '是' and cargo_info.get('首批截止时间（s）'):
            return float(cargo_info['首批截止时间（s）']) / 60.0
        return float(cargo_info['期望送达时间（s）']) / 60.0

    def _calculate_mission_metrics(
        self, cargo_group: List[str], area_route: List[str], uav_type: str
    ) -> Optional[Dict]:
        """计算架次的能耗和时间（使用官方DEM模型）

        对于多点访问，需要累加所有航段
        """
        if not cargo_group or not area_route:
            return None

        params = self.types[uav_type]
        total_energy = 0.0
        total_time = 0.0
        total_delivery_time = 0.0

        # 计算当前载荷（所有货箱的质量）
        current_load = sum(
            self.cargo_by_id.loc[cid]['单箱质量（kg）'] for cid in cargo_group
        )

        # 检查载重和体积约束
        total_volume = sum(
            self.cargo_by_id.loc[cid]['单箱体积（m³）'] for cid in cargo_group
        )
        if current_load > float(params['max_load_kg']) + 1e-9:
            print(f"      [超载] 机型={uav_type}, 载荷={current_load:.1f}kg > 最大载重={params['max_load_kg']}kg")
            return None
        if total_volume > float(params['max_volume_m3']) + 1e-9:
            print(f"      [超体积] 机型={uav_type}, 体积={total_volume:.2f}m^3 > 最大体积={params['max_volume_m3']}m^3")
            return None

        # 路线: O01 -> A1 -> A2 -> ... -> An -> O01
        route_nodes = ['O01'] + area_route + ['O01']

        for i in range(len(route_nodes) - 1):
            from_node = route_nodes[i]
            to_node = route_nodes[i + 1]

            # 确定起点和终点
            if from_node == 'O01':
                origin = self.depot
            else:
                origin = self.areas[from_node]

            if to_node == 'O01':
                destination = self.depot
            else:
                destination = self.areas[to_node]

            # 构建该航段携带的货箱（用于能耗计算）
            # 注意：卸货后载荷减少
            if i == 0:
                # 从O01出发，携带所有货箱
                segment_cargo = [
                    self.cargo_by_id.loc[cid] for cid in cargo_group
                ]
            else:
                # 中途航段，去除已卸货的
                delivered_areas = set(area_route[:i])
                segment_cargo = [
                    self.cargo_by_id.loc[cid] for cid in cargo_group
                    if self.cargo_by_id.loc[cid]['服务区编号'] not in delivered_areas
                ]

            # 调用官方能耗模型
            metrics = self.direct_mission_func(
                destination, origin, params, segment_cargo, self.dem
            )

            if not metrics['feasible']:
                print(f"      [能耗不可行] 机型={uav_type}, 航段={origin.get('编号', 'O01')}→{destination.get('编号', '?')}, "
                      f"载荷={sum(c['单箱质量（kg）'] for c in segment_cargo):.1f}kg, "
                      f"原因={metrics.get('reason', '未知')}")
                return None

            total_energy += metrics['energy_kwh']
            total_time += metrics['total_time_min']

            # 如果是交付点，记录交付时间
            if to_node in area_route:
                total_delivery_time = total_time

        # 检查返航安全余量
        capacity = float(params['battery_capacity_kwh'])
        reserve = float(params['battery_reserve_pct'])
        usable = capacity * (1.0 - reserve)

        if total_energy > usable + 1e-9:
            return None

        # 计算最早和最晚交付时间偏移
        # 简化：假设所有货箱在最后一个服务区统一交付
        # 实际应该按route顺序计算每个服务区的交付时间
        delivery_offset = total_delivery_time

        return {
            'feasible': True,
            'energy_kwh': total_energy,
            'duration_min': total_time,
            'delivery_offset_min': delivery_offset,
            'current_load': current_load
        }

    def initialize_population(self) -> List[Individual]:
        """初始化种群

        策略：
        1. 按服务区地理位置聚类
        2. 按货箱时限分层
        3. 随机组合生成多样化初始解
        """
        population = []

        for _ in range(self.pop_size):
            # 策略1: 基于地理位置的贪心组批
            if self.rng.random() < 0.4:
                ind = self._create_geographic_individual()
            # 策略2: 基于时限的组批
            elif self.rng.random() < 0.7:
                ind = self._create_deadline_individual()
            # 策略3: 完全随机
            else:
                ind = self._create_random_individual()

            population.append(ind)

        return population

    def _create_geographic_individual(self) -> Individual:
        """基于地理位置的贪心组批（支持多点访问）"""
        groups = []
        routes = []
        types_list = []

        remaining_cargo = set(self.cargo_by_id.index)

        while remaining_cargo:
            # 随机选择一个起始服务区
            available_areas = [
                area for area in self.cargo_by_area.keys()
                if any(c['货箱编号'] in remaining_cargo for c in self.cargo_by_area[area])
            ]
            if not available_areas:
                break

            start_area = self.rng.choice(available_areas)

            # 选择机型
            uav_type = self.rng.choice(list(self.types.keys()))
            params = self.types[uav_type]
            max_load = float(params['max_load_kg'])
            max_volume = float(params['max_volume_m3'])

            # 贪心添加货箱和服务区
            group = []
            route = []
            current_weight = 0.0
            current_volume = 0.0
            visited_areas = set()

            # 先添加start_area的货箱
            area_boxes = [
                c['货箱编号'] for c in self.cargo_by_area.get(start_area, [])
                if c['货箱编号'] in remaining_cargo
            ]

            for cid in area_boxes:
                box = self.cargo_by_id.loc[cid]
                w = box['单箱质量（kg）']
                v = box['单箱体积（m³）']

                if (current_weight + w <= max_load and
                    current_volume + v <= max_volume):
                    group.append(cid)
                    current_weight += w
                    current_volume += v
                    remaining_cargo.discard(cid)

            if group:
                route.append(start_area)
                visited_areas.add(start_area)

            # 尝试添加附近其他服务区的货箱（多点访问）
            max_stops = 3  # 最多访问3个服务区
            while len(route) < max_stops and current_weight < max_load * 0.8:
                # 找到未访问且有剩余货箱的服务区
                candidate_areas = [
                    area for area in self.cargo_by_area.keys()
                    if area not in visited_areas
                    and any(c['货箱编号'] in remaining_cargo for c in self.cargo_by_area[area])
                ]

                if not candidate_areas:
                    break

                # 随机选择一个服务区
                next_area = self.rng.choice(candidate_areas)

                # 尝试添加该服务区的货箱
                area_boxes = [
                    c['货箱编号'] for c in self.cargo_by_area.get(next_area, [])
                    if c['货箱编号'] in remaining_cargo
                ]

                added_any = False
                for cid in area_boxes:
                    box = self.cargo_by_id.loc[cid]
                    w = box['单箱质量（kg）']
                    v = box['单箱体积（m³）']

                    if (current_weight + w <= max_load and
                        current_volume + v <= max_volume):
                        group.append(cid)
                        current_weight += w
                        current_volume += v
                        remaining_cargo.discard(cid)
                        added_any = True

                if added_any:
                    route.append(next_area)
                    visited_areas.add(next_area)
                else:
                    break  # 无法再添加货箱

            if group:
                groups.append(group)
                routes.append(route)
                types_list.append(uav_type)

        return Individual(groups=groups, routes=routes, types=types_list)

    def _create_deadline_individual(self) -> Individual:
        """基于时限的组批（急件优先）"""
        groups = []
        routes = []
        types_list = []

        # 按截止时间排序货箱
        cargo_list = []
        for cid, row in self.cargo_by_id.iterrows():
            deadline = self._get_deadline_minutes(row)
            cargo_list.append((cid, deadline, row['服务区编号']))

        cargo_list.sort(key=lambda x: x[1])  # 按deadline排序

        remaining = set(c[0] for c in cargo_list)

        while remaining:
            # 选择最急的货箱
            urgent_cargo = [c for c in cargo_list if c[0] in remaining]
            if not urgent_cargo:
                break

            first_cid, first_deadline, first_area = urgent_cargo[0]

            # 选择合适机型
            uav_type = self.rng.choice(list(self.types.keys()))
            params = self.types[uav_type]

            group = [first_cid]
            route = [first_area]
            current_weight = self.cargo_by_id.loc[first_cid]['单箱质量（kg）']
            current_volume = self.cargo_by_id.loc[first_cid]['单箱体积（m³）']
            remaining.discard(first_cid)

            # 添加同服务区或相近deadline的货箱
            for cid, deadline, area in urgent_cargo[1:]:
                if cid not in remaining:
                    continue

                box = self.cargo_by_id.loc[cid]
                w = box['单箱质量（kg）']
                v = box['单箱体积（m³）']

                # deadline相近且容量允许
                if (abs(deadline - first_deadline) < 30 and  # 30分钟内
                    current_weight + w <= float(params['max_load_kg']) and
                    current_volume + v <= float(params['max_volume_m3'])):
                    group.append(cid)
                    if area not in route:
                        route.append(area)
                    current_weight += w
                    current_volume += v
                    remaining.discard(cid)

            groups.append(group)
            routes.append(route)
            types_list.append(uav_type)

        return Individual(groups=groups, routes=routes, types=types_list)

    def _create_random_individual(self) -> Individual:
        """完全随机生成个体（确保不超载）"""
        groups = []
        routes = []
        types_list = []

        remaining_cargo = set(self.cargo_by_id.index)

        while remaining_cargo:
            # 随机选择机型
            uav_type = self.rng.choice(list(self.types.keys()))
            params = self.types[uav_type]
            max_load = float(params['max_load_kg'])
            max_volume = float(params['max_volume_m3'])

            # 随机选择起始货箱
            available = list(remaining_cargo)
            self.rng.shuffle(available)

            group = []
            current_weight = 0.0
            current_volume = 0.0

            # 贪心添加货箱，直到满载或无法再添加
            for cid in available:
                box = self.cargo_by_id.loc[cid]
                w = box['单箱质量（kg）']
                v = box['单箱体积（m³）']

                if (current_weight + w <= max_load and
                    current_volume + v <= max_volume):
                    group.append(cid)
                    current_weight += w
                    current_volume += v
                    remaining_cargo.discard(cid)

                    # 随机决定是否继续添加（避免总是满载）
                    if self.rng.random() < 0.3 and len(group) >= 2:
                        break

            if group:
                # 获取涉及的服务区
                areas_set = set(
                    self.cargo_by_id.loc[cid]['服务区编号'] for cid in group
                )
                route = list(areas_set)
                self.rng.shuffle(route)

                groups.append(group)
                routes.append(route)
                types_list.append(uav_type)

        return Individual(groups=groups, routes=routes, types=types_list)

    def evaluate(self, individual: Individual) -> Individual:
        """评估个体

        步骤：
        1. 验证每个架次的物理可行性（DEM模型）
        2. 调用CP-SAT求解精确调度
        3. 计算三个目标函数值
        """
        missions = []

        for idx, (group, route, uav_type) in enumerate(
            zip(individual.groups, individual.routes, individual.types)
        ):
            # 计算架次指标
            metrics = self._calculate_mission_metrics(group, route, uav_type)

            if metrics is None:
                print(f"    [评估失败] 架次{idx+1}: 机型={uav_type}, 路线={route}, 货箱数={len(group)}")
                individual.feasible = False
                individual.objectives = (float('inf'), float('inf'), float('inf'))
                return individual

            # 计算该架次的截止时间（取最紧的）
            deadline_min = min(
                self._get_deadline_minutes(self.cargo_by_id.loc[cid])
                for cid in group
            )

            missions.append({
                'mission_id': idx + 1,
                'area_id': route[0] if len(route) == 1 else f"Multi_{len(route)}",
                'uav_type': uav_type,
                'cargo_ids': group,
                'energy_kwh': metrics['energy_kwh'],
                'duration_min': metrics['duration_min'],
                'delivery_offset_min': metrics['delivery_offset_min'],
                'deadline_min': deadline_min
            })

        # 调用CP-SAT求解调度
        from cpsat_scheduler import Mission
        mission_objects = [
            Mission(
                mission_id=m['mission_id'],
                area_id=m['area_id'],
                uav_type=m['uav_type'],
                cargo_ids=m['cargo_ids'],
                energy_kwh=m['energy_kwh'],
                duration_min=m['duration_min'],
                delivery_offset_min=m['delivery_offset_min'],
                deadline_min=m['deadline_min']
            )
            for m in missions
        ]

        result = self.cpsat_scheduler.schedule(mission_objects)

        if not result.success:
            individual.feasible = False
            individual.objectives = (float('inf'), float('inf'), float('inf'))
            return individual

        # 计算目标函数
        num_missions = len(missions)
        total_energy = sum(m['energy_kwh'] for m in missions)
        makespan = result.makespan_min

        individual.feasible = True
        individual.objectives = (num_missions, total_energy, makespan)
        individual.missions = result.missions
        individual.cargo_deliveries = result.cargo_deliveries

        return individual

    def fast_non_dominated_sort(self, population: List[Individual]) -> List[List[Individual]]:
        """快速非支配排序"""
        fronts = [[]]

        for p in population:
            p.domination_count = 0
            p.dominated_solutions = []

            for q in population:
                if self._dominates(p, q):
                    p.dominated_solutions.append(q)
                elif self._dominates(q, p):
                    p.domination_count += 1

            if p.domination_count == 0:
                p.rank = 0
                fronts[0].append(p)

        i = 0
        while i < len(fronts) and fronts[i]:
            next_front = []
            for p in fronts[i]:
                for q in p.dominated_solutions:
                    q.domination_count -= 1
                    if q.domination_count == 0:
                        q.rank = i + 1
                        next_front.append(q)
            i += 1
            if next_front:
                fronts.append(next_front)

        return [f for f in fronts if f]

    def _dominates(self, p: Individual, q: Individual) -> bool:
        """判断p是否支配q（所有目标不劣，至少一个目标更优）"""
        if not p.feasible:
            return False
        if not q.feasible:
            return True

        p_obj = p.objectives
        q_obj = q.objectives

        better_in_any = False
        for i in range(len(p_obj)):
            if p_obj[i] > q_obj[i]:
                return False
            if p_obj[i] < q_obj[i]:
                better_in_any = True

        return better_in_any

    def calculate_crowding_distance(self, front: List[Individual]):
        """计算拥挤度距离"""
        if len(front) == 0:
            return

        num_objectives = 3
        for ind in front:
            ind.crowding_distance = 0.0

        for m in range(num_objectives):
            front.sort(key=lambda x: x.objectives[m] if x.feasible else float('inf'))

            front[0].crowding_distance = float('inf')
            front[-1].crowding_distance = float('inf')

            obj_min = front[0].objectives[m]
            obj_max = front[-1].objectives[m]

            if obj_max - obj_min == 0:
                continue

            for i in range(1, len(front) - 1):
                if front[i].crowding_distance != float('inf'):
                    distance = (front[i + 1].objectives[m] - front[i - 1].objectives[m]) / (obj_max - obj_min)
                    front[i].crowding_distance += distance

    def tournament_selection(self, population: List[Individual], k: int = 2) -> Individual:
        """锦标赛选择"""
        candidates = self.rng.sample(population, k)
        candidates.sort(key=lambda x: (x.rank, -x.crowding_distance))
        return candidates[0]

    def crossover(self, parent1: Individual, parent2: Individual) -> Tuple[Individual, Individual]:
        """交叉操作（两点交叉）"""
        if self.rng.random() > self.crossover_prob:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        # 简化版本：在架次层面进行交叉
        n1 = len(parent1.groups)
        n2 = len(parent2.groups)

        if n1 < 2 or n2 < 2:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        # 单点交叉
        cut1 = self.rng.randint(1, n1 - 1)
        cut2 = self.rng.randint(1, n2 - 1)

        child1_groups = parent1.groups[:cut1] + parent2.groups[cut2:]
        child1_routes = parent1.routes[:cut1] + parent2.routes[cut2:]
        child1_types = parent1.types[:cut1] + parent2.types[cut2:]

        child2_groups = parent2.groups[:cut2] + parent1.groups[cut1:]
        child2_routes = parent2.routes[:cut2] + parent1.routes[cut1:]
        child2_types = parent2.types[:cut2] + parent1.types[cut1:]

        # 修复：确保每个货箱只出现一次
        child1 = self._repair_individual(Individual(child1_groups, child1_routes, child1_types))
        child2 = self._repair_individual(Individual(child2_groups, child2_routes, child2_types))

        return child1, child2

    def _repair_individual(self, individual: Individual) -> Individual:
        """修复个体（确保每个货箱恰好出现一次）"""
        all_cargo = set(self.cargo_by_id.index)
        seen = set()

        new_groups = []
        new_routes = []
        new_types = []

        for group, route, typ in zip(individual.groups, individual.routes, individual.types):
            new_group = [cid for cid in group if cid not in seen and cid in all_cargo]
            if new_group:
                seen.update(new_group)
                # 更新route（只保留实际包含货箱的服务区）
                areas = set(self.cargo_by_id.loc[cid]['服务区编号'] for cid in new_group)
                new_route = [a for a in route if a in areas]
                if not new_route:
                    new_route = list(areas)

                new_groups.append(new_group)
                new_routes.append(new_route)
                new_types.append(typ)

        # 添加缺失的货箱
        missing = all_cargo - seen
        if missing:
            missing_list = list(missing)
            # 为缺失货箱创建新架次
            for cid in missing_list:
                area = self.cargo_by_id.loc[cid]['服务区编号']
                typ = self.rng.choice(list(self.types.keys()))
                new_groups.append([cid])
                new_routes.append([area])
                new_types.append(typ)

        return Individual(groups=new_groups, routes=new_routes, types=new_types)

    def mutate(self, individual: Individual) -> Individual:
        """变异操作"""
        if self.rng.random() > self.mutation_prob:
            return individual

        ind = copy.deepcopy(individual)

        if not ind.groups:
            return ind

        # 多种变异策略
        mutation_type = self.rng.randint(0, 3)

        if mutation_type == 0:
            # 合并两个架次
            if len(ind.groups) >= 2:
                i, j = self.rng.sample(range(len(ind.groups)), 2)
                ind.groups[i].extend(ind.groups[j])
                ind.routes[i] = list(set(ind.routes[i] + ind.routes[j]))
                del ind.groups[j]
                del ind.routes[j]
                del ind.types[j]

        elif mutation_type == 1:
            # 拆分一个架次
            if len(ind.groups) > 0:
                i = self.rng.randint(0, len(ind.groups) - 1)
                if len(ind.groups[i]) >= 2:
                    split_point = self.rng.randint(1, len(ind.groups[i]) - 1)
                    group1 = ind.groups[i][:split_point]
                    group2 = ind.groups[i][split_point:]

                    areas1 = set(self.cargo_by_id.loc[cid]['服务区编号'] for cid in group1)
                    areas2 = set(self.cargo_by_id.loc[cid]['服务区编号'] for cid in group2)

                    ind.groups[i] = group1
                    ind.routes[i] = list(areas1)
                    ind.groups.append(group2)
                    ind.routes.append(list(areas2))
                    ind.types.append(self.rng.choice(list(self.types.keys())))

        elif mutation_type == 2:
            # 改变机型
            if len(ind.types) > 0:
                i = self.rng.randint(0, len(ind.types) - 1)
                ind.types[i] = self.rng.choice(list(self.types.keys()))

        else:
            # 改变访问顺序
            if len(ind.routes) > 0:
                i = self.rng.randint(0, len(ind.routes) - 1)
                if len(ind.routes[i]) > 1:
                    self.rng.shuffle(ind.routes[i])

        return ind

    def optimize(self) -> List[Individual]:
        """执行NSGA-II优化"""
        print(f"初始化种群（大小={self.pop_size}）...")
        population = self.initialize_population()

        print("评估初始种群...")
        for i, ind in enumerate(population):
            self.evaluate(ind)
            if (i + 1) % 10 == 0:
                print(f"  已评估 {i + 1}/{len(population)} 个个体")

        for gen in range(self.max_generations):
            print(f"\n第 {gen + 1}/{self.max_generations} 代")

            # 非支配排序
            fronts = self.fast_non_dominated_sort(population)

            # 计算拥挤度
            for front in fronts:
                self.calculate_crowding_distance(front)

            # 输出当前最优前沿
            if fronts[0]:
                best_objs = [ind.objectives for ind in fronts[0] if ind.feasible]
                if best_objs:
                    print(f"  帕累托前沿大小: {len(best_objs)}")
                    print(f"  最佳架次数: {min(obj[0] for obj in best_objs):.0f}")
                    print(f"  最佳能耗: {min(obj[1] for obj in best_objs):.2f} kWh")
                    print(f"  最佳时间: {min(obj[2] for obj in best_objs):.2f} min")

            # 生成子代
            offspring = []
            while len(offspring) < self.pop_size:
                parent1 = self.tournament_selection(population)
                parent2 = self.tournament_selection(population)

                child1, child2 = self.crossover(parent1, parent2)
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)

                offspring.extend([child1, child2])

            # 评估子代
            print(f"  评估子代...")
            for i, ind in enumerate(offspring):
                self.evaluate(ind)

            # 合并父代和子代，选择下一代
            combined = population + offspring
            fronts = self.fast_non_dominated_sort(combined)

            next_population = []
            for front in fronts:
                if len(next_population) + len(front) <= self.pop_size:
                    next_population.extend(front)
                else:
                    self.calculate_crowding_distance(front)
                    front.sort(key=lambda x: x.crowding_distance, reverse=True)
                    next_population.extend(front[:self.pop_size - len(next_population)])
                    break

            population = next_population

        # 返回最终的帕累托前沿
        fronts = self.fast_non_dominated_sort(population)
        return fronts[0] if fronts else []
