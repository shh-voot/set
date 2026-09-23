#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批次划分优化器
基于通信覆盖约束的服务区分组
"""

import numpy as np
import networkx as nx
from typing import List, Tuple, Dict, Set
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from communication.los_model import LOSCommunicationModel, Position


class BatchOptimizer:
    """批次划分优化器"""

    def __init__(self, los_model: LOSCommunicationModel):
        """
        初始化批次优化器

        Args:
            los_model: LoS通信模型
        """
        self.los_model = los_model

    def build_communication_conflict_graph(
        self,
        service_areas: List[Dict],
        gateway: Dict,
        relay_positions: List[Tuple[float, float, float]] = None
    ) -> nx.Graph:
        """
        构建通信冲突图
        如果两个服务区不能同时通信（需要不同中继或时分复用），则连边

        Args:
            service_areas: 服务区列表
            gateway: 网关信息
            relay_positions: 中继位置列表

        Returns:
            冲突图（NetworkX Graph）
        """
        G = nx.Graph()

        # 添加节点
        for area in service_areas:
            G.add_node(area['id'], **area)

        # 检查通信冲突
        for i, area_i in enumerate(service_areas):
            pos_i = Position(area_i['longitude'], area_i['latitude'], area_i['altitude'])
            gateway_pos = Position(gateway['longitude'], gateway['latitude'], gateway['altitude'])

            # 检查area_i能否直连网关
            can_i_direct, _ = self.los_model.check_los(pos_i, gateway_pos)

            for j, area_j in enumerate(service_areas):
                if i >= j:
                    continue

                pos_j = Position(area_j['longitude'], area_j['latitude'], area_j['altitude'])

                # 检查area_j能否直连网关
                can_j_direct, _ = self.los_model.check_los(pos_j, gateway_pos)

                # 冲突条件：
                # 1. 都不能直连，且没有共同中继覆盖
                # 2. 或者需要时分复用同一中继
                has_conflict = False

                if not can_i_direct and not can_j_direct:
                    # 检查是否有共同的中继覆盖
                    if relay_positions is None:
                        # 没有中继信息，保守假设有冲突
                        has_conflict = True
                    else:
                        # 检查是否共享中继
                        relay_i = None
                        relay_j = None

                        for relay_pos in relay_positions:
                            relay = Position(*relay_pos)
                            can_i_reach_relay, _ = self.los_model.check_los(pos_i, relay)
                            can_j_reach_relay, _ = self.los_model.check_los(pos_j, relay)

                            if can_i_reach_relay:
                                relay_i = relay_pos
                            if can_j_reach_relay:
                                relay_j = relay_pos

                        # 如果共享同一个中继，可能有冲突（时分复用）
                        if relay_i == relay_j and relay_i is not None:
                            has_conflict = True

                if has_conflict:
                    G.add_edge(area_i['id'], area_j['id'])

        return G

    def partition_into_batches(
        self,
        service_areas: List[Dict],
        gateway: Dict,
        num_batches: int,
        relay_positions: List[Tuple[float, float, float]] = None
    ) -> List[List[str]]:
        """
        将服务区划分为多个批次

        Args:
            service_areas: 服务区列表
            gateway: 网关信息
            num_batches: 批次数量（2或3）
            relay_positions: 中继位置列表

        Returns:
            批次列表，每个批次包含服务区ID列表
        """
        # 构建冲突图
        G = self.build_communication_conflict_graph(service_areas, gateway, relay_positions)

        # 使用图着色算法
        if num_batches == 2:
            batches = self._two_batch_partition(G)
        elif num_batches == 3:
            batches = self._three_batch_partition(G)
        else:
            raise ValueError(f"不支持的批次数量: {num_batches}")

        return batches

    def _two_batch_partition(self, G: nx.Graph) -> List[List[str]]:
        """
        两批次划分（图2-着色）
        """
        # 尝试贪心着色
        coloring = nx.greedy_color(G, strategy='largest_first')

        # 按颜色分组
        batch1 = [node for node, color in coloring.items() if color == 0]
        batch2 = [node for node, color in coloring.items() if color == 1]

        # 如果着色数>2，尝试调整
        max_color = max(coloring.values())
        if max_color >= 2:
            # 将多余颜色合并到前两个批次
            for node, color in coloring.items():
                if color >= 2:
                    # 选择邻居较少的批次
                    neighbors_in_batch1 = sum(1 for n in G.neighbors(node) if n in batch1)
                    neighbors_in_batch2 = sum(1 for n in G.neighbors(node) if n in batch2)

                    if neighbors_in_batch1 <= neighbors_in_batch2:
                        batch1.append(node)
                    else:
                        batch2.append(node)

        return [batch1, batch2]

    def _three_batch_partition(self, G: nx.Graph) -> List[List[str]]:
        """
        三批次划分（图3-着色）
        """
        # 尝试贪心着色
        coloring = nx.greedy_color(G, strategy='largest_first')

        # 按颜色分组
        batch1 = [node for node, color in coloring.items() if color == 0]
        batch2 = [node for node, color in coloring.items() if color == 1]
        batch3 = [node for node, color in coloring.items() if color == 2]

        # 如果着色数>3，尝试调整
        max_color = max(coloring.values())
        if max_color >= 3:
            for node, color in coloring.items():
                if color >= 3:
                    # 选择邻居最少的批次
                    neighbors_counts = [
                        sum(1 for n in G.neighbors(node) if n in batch1),
                        sum(1 for n in G.neighbors(node) if n in batch2),
                        sum(1 for n in G.neighbors(node) if n in batch3)
                    ]
                    min_batch_idx = np.argmin(neighbors_counts)

                    if min_batch_idx == 0:
                        batch1.append(node)
                    elif min_batch_idx == 1:
                        batch2.append(node)
                    else:
                        batch3.append(node)

        return [batch1, batch2, batch3]

    def balance_batches(self, batches: List[List[str]], workload_weights: Dict[str, float]) -> List[List[str]]:
        """
        平衡批次工作量（可选优化）

        Args:
            batches: 初始批次划分
            workload_weights: 每个服务区的工作量权重（如货物重量、任务数量）

        Returns:
            平衡后的批次
        """
        # 简单的贪心平衡策略
        # TODO: 实现更复杂的平衡算法
        return batches

    def evaluate_partition(
        self,
        batches: List[List[str]],
        service_areas: List[Dict],
        gateway: Dict
    ) -> Dict:
        """
        评估批次划分质量

        Args:
            batches: 批次划分方案
            service_areas: 服务区列表
            gateway: 网关信息

        Returns:
            评估指标字典
        """
        metrics = {
            'num_batches': len(batches),
            'batch_sizes': [len(b) for b in batches],
            'batch_balance': np.std([len(b) for b in batches]),
            'conflicts': 0,  # 批次内冲突数量
            'direct_link_ratio': []  # 每个批次的直连比例
        }

        # 计算每个批次的直连比例
        for batch in batches:
            direct_count = 0
            for area_id in batch:
                area = next(a for a in service_areas if a['id'] == area_id)
                pos = Position(area['longitude'], area['latitude'], area['altitude'])
                gateway_pos = Position(gateway['longitude'], gateway['latitude'], gateway['altitude'])

                can_direct, _ = self.los_model.check_los(pos, gateway_pos)
                if can_direct:
                    direct_count += 1

            metrics['direct_link_ratio'].append(direct_count / len(batch) if len(batch) > 0 else 0)

        return metrics


def test_batch_optimizer():
    """测试批次优化器"""
    print("="*80)
    print("测试批次优化器")
    print("="*80)

    # 创建模拟数据
    service_areas = [
        {'id': 'S001', 'longitude': 109.23, 'latitude': 23.01, 'altitude': 100},
        {'id': 'S002', 'longitude': 109.24, 'latitude': 23.02, 'altitude': 150},
        {'id': 'S003', 'longitude': 109.22, 'latitude': 23.00, 'altitude': 120},
        {'id': 'S004', 'longitude': 109.25, 'latitude': 23.03, 'altitude': 180},
        {'id': 'S005', 'longitude': 109.21, 'latitude': 23.01, 'altitude': 110},
    ]

    gateway = {'longitude': 109.230852, 'latitude': 23.008509, 'altitude': 127.7}

    # 创建通信模型（简化版，无DEM）
    from communication.los_model import CommParams
    los_model = LOSCommunicationModel(comm_params=CommParams())

    # 创建批次优化器
    optimizer = BatchOptimizer(los_model)

    # 测试2批次划分
    print("\n测试2批次划分:")
    batches_2 = optimizer.partition_into_batches(service_areas, gateway, num_batches=2)
    for i, batch in enumerate(batches_2, 1):
        print(f"  批次{i}: {batch}")

    # 评估
    metrics = optimizer.evaluate_partition(batches_2, service_areas, gateway)
    print(f"\n评估指标:")
    print(f"  批次大小: {metrics['batch_sizes']}")
    print(f"  平衡度: {metrics['batch_balance']:.2f}")
    print(f"  直连比例: {[f'{r:.1%}' for r in metrics['direct_link_ratio']]}")

    # 测试3批次划分
    print("\n测试3批次划分:")
    batches_3 = optimizer.partition_into_batches(service_areas, gateway, num_batches=3)
    for i, batch in enumerate(batches_3, 1):
        print(f"  批次{i}: {batch}")

    metrics = optimizer.evaluate_partition(batches_3, service_areas, gateway)
    print(f"\n评估指标:")
    print(f"  批次大小: {metrics['batch_sizes']}")
    print(f"  平衡度: {metrics['batch_balance']:.2f}")
    print(f"  直连比例: {[f'{r:.1%}' for r in metrics['direct_link_ratio']]}")

    print("\n" + "="*80)
    print("批次优化器测试完成")
    print("="*80)


if __name__ == "__main__":
    test_batch_optimizer()
