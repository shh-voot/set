#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为杯D题 - 问题一求解器
单架次最优装载问题 (3D背包问题)
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data.data_loader import DataLoader
from energy.energy_model import EnergyModel, calculate_3d_distance


class Problem1Solver:
    """问题一求解器 - 单架次最优装载"""

    def __init__(self, data_loader: DataLoader):
        """
        初始化求解器

        Args:
            data_loader: 数据加载器
        """
        self.data_loader = data_loader
        self.depot = data_loader.get_depot()
        self.service_areas = data_loader.get_service_areas()
        self.uav_types = data_loader.get_uav_types()
        self.cargos = data_loader.get_cargos()

        # 预计算距离矩阵
        self.distance_matrix = self._compute_distance_matrix()

    def _compute_distance_matrix(self) -> Dict:
        """预计算调度中心到各服务区的距离"""
        distances = {}

        depot_lon = self.depot['longitude']
        depot_lat = self.depot['latitude']
        depot_alt = self.depot['altitude']

        for _, sa in self.service_areas.iterrows():
            h_dist, d_3d = calculate_3d_distance(
                depot_lon, depot_lat, depot_alt,
                sa['longitude'], sa['latitude'], sa['altitude']
            )
            distances[sa['id']] = {
                'horizontal_m': h_dist,
                'distance_3d_m': d_3d,
                'altitude_diff_m': sa['altitude'] - depot_alt
            }

        return distances

    def solve_single_trip(
        self,
        service_area_id: str,
        uav_type: str,
        method: str = 'greedy'
    ) -> Dict:
        """
        求解单次飞行的最优装载

        Args:
            service_area_id: 服务区ID
            uav_type: 无人机类型 (A/B/C)
            method: 求解方法 ('greedy', 'dp')

        Returns:
            求解结果字典
        """
        # 获取参数
        uav_params = self.data_loader.get_uav_type(uav_type)
        if uav_params is None:
            return {'error': f'未找到无人机类型 {uav_type}'}

        distance_info = self.distance_matrix.get(service_area_id)
        if distance_info is None:
            return {'error': f'未找到服务区 {service_area_id}'}

        # 获取该服务区的货物需求
        # 注意: 这里假设cargos数据中有destination字段
        # 如果没有，需要从题目数据中获取每个服务区的需求货物
        service_area_cargos = self._get_service_area_cargos(service_area_id)

        if len(service_area_cargos) == 0:
            return {'error': f'服务区 {service_area_id} 无货物需求'}

        # 计算能耗约束
        energy_model = EnergyModel(uav_params)
        energy_info = energy_model.calculate_round_trip_energy(
            self.depot['altitude'],
            self.service_areas[self.service_areas['id'] == service_area_id].iloc[0]['altitude'],
            distance_info['horizontal_m'],
            payload_kg=0  # 先用0计算基础能耗
        )

        # 可用电池容量
        battery_capacity = uav_params['battery_capacity_kwh']
        reserve_pct = uav_params['battery_reserve_pct'] / 100.0
        usable_energy = battery_capacity * (1 - reserve_pct)

        # 预留能量 (扣除空载往返能耗)
        empty_energy = energy_info['total_energy_kwh']
        available_energy = usable_energy - empty_energy

        # 约束条件
        constraints = {
            'max_weight_kg': uav_params['max_load_kg'],
            'max_volume_m3': uav_params['max_volume_m3'],
            'max_energy_kwh': available_energy
        }

        # 根据方法求解
        if method == 'greedy':
            solution = self._solve_greedy(service_area_cargos, constraints, uav_params)
        elif method == 'dp':
            solution = self._solve_dp(service_area_cargos, constraints, uav_params)
        else:
            return {'error': f'未知求解方法: {method}'}

        # 计算实际能耗 (考虑载重)
        total_payload = sum(c['weight'] for c in solution['selected_cargos'])
        actual_energy_info = energy_model.calculate_round_trip_energy(
            self.depot['altitude'],
            self.service_areas[self.service_areas['id'] == service_area_id].iloc[0]['altitude'],
            distance_info['horizontal_m'],
            payload_kg=total_payload
        )

        # 汇总结果
        result = {
            'service_area_id': service_area_id,
            'uav_type': uav_type,
            'method': method,
            'selected_cargos': solution['selected_cargos'],
            'num_cargos': len(solution['selected_cargos']),
            'total_weight_kg': solution['total_weight'],
            'total_volume_m3': solution['total_volume'],
            'total_value': solution['total_value'],
            'weight_utilization': solution['total_weight'] / constraints['max_weight_kg'],
            'volume_utilization': solution['total_volume'] / constraints['max_volume_m3'],
            'energy_kwh': actual_energy_info['total_energy_kwh'],
            'energy_utilization': actual_energy_info['total_energy_kwh'] / usable_energy,
            'flight_time_min': actual_energy_info['total_time_min'],
            'distance_km': distance_info['horizontal_m'] / 1000,
            'is_feasible': actual_energy_info['is_feasible']
        }

        return result

    def _get_service_area_cargos(self, service_area_id: str) -> List[Dict]:
        """
        获取指定服务区的货物列表

        根据实际数据格式:
        - 货箱编号 (如 S001-MED-01)
        - 目的地 (服务区ID)
        - 物资类别
        - 单箱重量(kg)
        - 单箱体积(m³) 或类似列名
        """
        cargo_list = []

        # 筛选目标服务区的货物
        if self.cargos is None or len(self.cargos) == 0:
            return cargo_list

        # 获取列名 (处理可能的编码问题)
        cols = self.cargos.columns.tolist()

        # 查找关键列的索引
        dest_col = None
        weight_col = None
        volume_col = None
        id_col = None

        for i, col in enumerate(cols):
            col_str = str(col).lower()
            if 'dest' in col_str or '目的' in col_str or cols[i] == cols[1]:
                dest_col = i
            elif 'weight' in col_str or '重量' in col_str or 'kg' in col_str:
                weight_col = i
            elif 'volume' in col_str or '体积' in col_str or 'm' in col_str:
                volume_col = i
            elif i == 0:  # 第一列通常是ID
                id_col = i

        # 如果找不到列，使用默认位置
        if dest_col is None:
            dest_col = 1  # 第二列
        if weight_col is None:
            weight_col = 3  # 第四列
        if volume_col is None:
            volume_col = 4  # 第五列
        if id_col is None:
            id_col = 0  # 第一列

        # 遍历所有货物
        for idx, row in self.cargos.iterrows():
            try:
                # 检查目的地
                destination = str(row.iloc[dest_col]) if dest_col < len(row) else ''

                if destination.startswith(service_area_id):
                    cargo = {
                        'id': str(row.iloc[id_col]) if id_col < len(row) else f'CARGO_{idx}',
                        'weight': float(row.iloc[weight_col]) if weight_col < len(row) else 0.0,
                        'volume': float(row.iloc[volume_col]) if volume_col < len(row) else 0.0,
                        'value': float(row.iloc[weight_col]) if weight_col < len(row) else 0.0  # 价值=重量
                    }

                    # 验证数据有效性
                    if cargo['weight'] > 0 and cargo['volume'] > 0:
                        cargo_list.append(cargo)

            except Exception as e:
                # 跳过无效行
                continue

        return cargo_list

    def _solve_greedy(
        self,
        cargos: List[Dict],
        constraints: Dict,
        uav_params: Dict
    ) -> Dict:
        """
        贪心算法求解

        策略: 按价值密度 (value/weight) 降序选择
        """
        # 计算价值密度
        for cargo in cargos:
            cargo['density'] = cargo['value'] / max(cargo['weight'], 0.01)

        # 按密度排序
        sorted_cargos = sorted(cargos, key=lambda x: x['density'], reverse=True)

        # 贪心选择
        selected = []
        total_weight = 0
        total_volume = 0
        total_value = 0

        for cargo in sorted_cargos:
            # 检查约束
            if (total_weight + cargo['weight'] <= constraints['max_weight_kg'] and
                total_volume + cargo['volume'] <= constraints['max_volume_m3']):

                selected.append(cargo)
                total_weight += cargo['weight']
                total_volume += cargo['volume']
                total_value += cargo['value']

        return {
            'selected_cargos': selected,
            'total_weight': total_weight,
            'total_volume': total_volume,
            'total_value': total_value
        }

    def _solve_dp(
        self,
        cargos: List[Dict],
        constraints: Dict,
        uav_params: Dict
    ) -> Dict:
        """
        动态规划求解 (3D背包)

        注意: 由于是3D背包问题(重量+体积+能量)，复杂度较高
        这里简化为2D背包(重量+体积)
        """
        n = len(cargos)
        W = int(constraints['max_weight_kg'] * 10)  # 离散化到0.1kg
        V = int(constraints['max_volume_m3'] * 100)  # 离散化到0.01m³

        # DP表: dp[i][w][v] = 前i个物品，重量不超过w，体积不超过v的最大价值
        # 由于内存限制，使用滚动数组优化
        dp = np.zeros((W + 1, V + 1), dtype=float)
        selected_items = [[[] for _ in range(V + 1)] for _ in range(W + 1)]

        for i, cargo in enumerate(cargos):
            w = int(cargo['weight'] * 10)
            v = int(cargo['volume'] * 100)
            value = cargo['value']

            # 逆序遍历，避免重复选择
            for wi in range(W, w - 1, -1):
                for vi in range(V, v - 1, -1):
                    if dp[wi][vi] < dp[wi - w][vi - v] + value:
                        dp[wi][vi] = dp[wi - w][vi - v] + value
                        selected_items[wi][vi] = selected_items[wi - w][vi - v] + [i]

        # 回溯找到选中的物品
        best_w, best_v = W, V
        selected_indices = selected_items[best_w][best_v]
        selected_cargos = [cargos[i] for i in selected_indices]

        total_weight = sum(c['weight'] for c in selected_cargos)
        total_volume = sum(c['volume'] for c in selected_cargos)
        total_value = sum(c['value'] for c in selected_cargos)

        return {
            'selected_cargos': selected_cargos,
            'total_weight': total_weight,
            'total_volume': total_volume,
            'total_value': total_value
        }

    def solve_all_combinations(self, method: str = 'greedy') -> pd.DataFrame:
        """
        求解所有服务区和机型的组合

        Returns:
            结果DataFrame
        """
        results = []

        for _, sa in self.service_areas.iterrows():
            for _, uav in self.uav_types.iterrows():
                result = self.solve_single_trip(sa['id'], uav['type'], method)

                if 'error' not in result:
                    results.append(result)

        return pd.DataFrame(results)


def test_problem1_solver():
    """测试问题一求解器"""
    print("="*80)
    print("问题一求解器测试")
    print("="*80)

    # 加载数据
    print("\n加载数据...")
    loader = DataLoader()
    loader.load_all()

    # 创建求解器
    print("\n创建求解器...")
    solver = Problem1Solver(loader)

    # 测试单次求解
    print("\n\n测试1: 单次求解 (S001服务区, A型无人机, 贪心算法)")
    print("-" * 80)

    result = solver.solve_single_trip('S001', 'A', method='greedy')

    if 'error' in result:
        print(f"错误: {result['error']}")
    else:
        print(f"服务区: {result['service_area_id']}")
        print(f"无人机: {result['uav_type']}型")
        print(f"选中货箱数: {result['num_cargos']}")
        print(f"总重量: {result['total_weight_kg']:.2f} kg")
        print(f"总体积: {result['total_volume_m3']:.4f} m3")
        print(f"总价值: {result['total_value']:.2f}")
        print(f"重量利用率: {result['weight_utilization']:.1%}")
        print(f"体积利用率: {result['volume_utilization']:.1%}")
        print(f"能耗: {result['energy_kwh']:.4f} kWh")
        print(f"能量利用率: {result['energy_utilization']:.1%}")
        print(f"飞行时间: {result['flight_time_min']:.2f} 分钟")
        print(f"可行性: {'可行' if result['is_feasible'] else '不可行'}")

    print("\n" + "="*80)


if __name__ == "__main__":
    test_problem1_solver()
