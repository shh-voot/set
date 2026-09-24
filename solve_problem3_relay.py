#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题三：通信约束下的运输与中继联合调度
基于符合赛题规则的问题二结果（126.39分钟）
目标：实现100%通信覆盖
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
from itertools import combinations

# 添加路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader


def calculate_distance_3d(coord1, coord2):
    """
    计算三维空间距离（考虑海拔）

    Args:
        coord1: (lon, lat, alt)
        coord2: (lon, lat, alt)

    Returns:
        距离（m）
    """
    lon1, lat1, alt1 = coord1
    lon2, lat2, alt2 = coord2

    # 地表距离
    R = 6371000  # 地球半径(m)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (np.sin(dlat/2)**2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon/2)**2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    horizontal_dist = R * c

    # 高度差
    vertical_dist = abs(alt2 - alt1)

    # 三维距离
    distance_3d = np.sqrt(horizontal_dist**2 + vertical_dist**2)

    return distance_3d


def calculate_link_budget(tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
                          distance_m, frequency_mhz,
                          system_loss_db=3, obstacle_loss_db=10):
    """
    计算链路预算

    Returns:
        received_power_dbm: 接收功率(dBm)
    """
    # 自由空间路径损耗 (Friis公式)
    # FSPL(dB) = 20*log10(d_km) + 20*log10(f_MHz) + 32.45
    distance_km = distance_m / 1000
    fspl_db = 20 * np.log10(distance_km) + 20 * np.log10(frequency_mhz) + 32.45

    # 接收功率 = 发射功率 + 发射增益 + 接收增益 - 路径损耗 - 系统损耗 - 障碍损耗
    rx_power_dbm = (tx_power_dbm + tx_gain_dbi + rx_gain_dbi -
                    fspl_db - system_loss_db - obstacle_loss_db)

    return rx_power_dbm


def check_communication_link(point1, point2, comm_params,
                            tx_power_dbm, tx_gain_dbi, rx_gain_dbi):
    """
    检查两点之间的通信链路是否可用

    Args:
        point1: (lon, lat, alt)
        point2: (lon, lat, alt)
        comm_params: 通信参数
        tx_power_dbm: 发射功率
        tx_gain_dbi: 发射天线增益
        rx_gain_dbi: 接收天线增益

    Returns:
        (is_connected, margin_db): 是否连通，余量(dB)
    """
    distance = calculate_distance_3d(point1, point2)

    rx_power = calculate_link_budget(
        tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
        distance, comm_params['carrier_frequency_mhz'],
        comm_params['system_loss_db'],
        comm_params['obstacle_loss_db']
    )

    sensitivity = comm_params['sensitivity_dbm']
    margin_db = comm_params['margin_db']

    # 判断是否满足接收灵敏度 + 余量
    threshold = sensitivity + margin_db
    is_connected = rx_power >= threshold
    margin = rx_power - sensitivity

    return is_connected, margin


def evaluate_relay_position(relay_pos, depot_pos, service_area_positions,
                           comm_params, relay_specs, transport_specs):
    """
    评估中继位置的覆盖性能

    Returns:
        coverage_rate: 覆盖率 [0, 1]
        covered_services: 覆盖的服务区列表
        total_links_ok: 通过的链路数
    """
    lon_r, lat_r, alt_r = relay_pos

    # 中继UAV参数
    relay_tx_power = comm_params['relay_tx_power_dbm']
    relay_tx_gain = comm_params['relay_tx_antenna_gain_dbi']
    relay_rx_gain = comm_params['relay_rx_antenna_gain_dbi']

    # 运输UAV参数
    transport_tx_power = comm_params['transport_tx_power_dbm']
    transport_tx_gain = comm_params['transport_tx_antenna_gain_dbi']

    covered_services = []
    link_details = []

    for area_id, (lon_s, lat_s, alt_s) in service_area_positions.items():
        # 链路1: 中继 <-> 调度中心G01
        link1_ok, link1_margin = check_communication_link(
            relay_pos, depot_pos,
            comm_params,
            relay_tx_power, relay_tx_gain, comm_params['ground_station_antenna_gain_dbi']
        )

        # 链路2: 运输UAV <-> 中继
        service_pos = (lon_s, lat_s, alt_s)
        link2_ok, link2_margin = check_communication_link(
            service_pos, relay_pos,
            comm_params,
            transport_tx_power, transport_tx_gain, relay_rx_gain
        )

        # 双向链路都通才算覆盖
        if link1_ok and link2_ok:
            covered_services.append(area_id)
            link_details.append({
                'area_id': area_id,
                'link1_margin': link1_margin,
                'link2_margin': link2_margin,
                'min_margin': min(link1_margin, link2_margin)
            })

    coverage_rate = len(covered_services) / len(service_area_positions)

    return coverage_rate, covered_services, link_details


def optimize_relay_placement_grid_search(depot_pos, service_area_positions,
                                        comm_params, relay_specs, transport_specs,
                                        num_relays=1):
    """
    使用网格搜索优化中继位置

    Returns:
        best_relays: 最优中继位置列表
        best_coverage: 最优覆盖率
    """
    print(f"\n[网格搜索] 优化{num_relays}架中继UAV的位置...")

    # 确定搜索范围
    lon_depot, lat_depot, alt_depot = depot_pos
    all_lons = [lon_depot] + [pos[0] for pos in service_area_positions.values()]
    all_lats = [lat_depot] + [pos[1] for pos in service_area_positions.values()]

    lon_min, lon_max = min(all_lons), max(all_lons)
    lat_min, lat_max = min(all_lats), max(all_lats)

    # 扩展搜索边界（增加到50%以覆盖边缘服务区）
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    lon_min -= lon_range * 0.25
    lon_max += lon_range * 0.25
    lat_min -= lat_range * 0.25
    lat_max += lat_range * 0.25

    # 高度范围：150m - 500m（增加高度以应对复杂地形）
    alt_min = 150
    alt_max = 500

    # 网格密度（增加以提高精度）
    grid_size_lon = 25
    grid_size_lat = 25
    grid_size_alt = 12

    lons = np.linspace(lon_min, lon_max, grid_size_lon)
    lats = np.linspace(lat_min, lat_max, grid_size_lat)
    alts = np.linspace(alt_min, alt_max, grid_size_alt)

    print(f"  搜索空间: {len(lons)}×{len(lats)}×{len(alts)} = {len(lons)*len(lats)*len(alts)} 个候选位置")

    if num_relays == 1:
        # 单中继优化
        best_coverage = 0
        best_relay = None
        best_covered = []
        best_details = []

        total_candidates = len(lons) * len(lats) * len(alts)
        evaluated = 0

        for lon in lons:
            for lat in lats:
                for alt in alts:
                    relay_pos = (lon, lat, alt)

                    coverage, covered, details = evaluate_relay_position(
                        relay_pos, depot_pos, service_area_positions,
                        comm_params, relay_specs, transport_specs
                    )

                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_relay = relay_pos
                        best_covered = covered
                        best_details = details

                    evaluated += 1
                    if evaluated % 500 == 0:
                        print(f"  进度: {evaluated}/{total_candidates} ({evaluated/total_candidates*100:.1f}%) "
                              f"- 当前最优覆盖率: {best_coverage*100:.1f}%")

        return [best_relay], best_coverage, best_covered, best_details

    else:
        # 多中继优化（贪心算法：逐个添加中继直到100%覆盖）
        print(f"  [多中继贪心算法] 目标覆盖率100%")

        relay_positions = []
        all_covered = set()
        all_details = []

        total_candidates = len(lons) * len(lats) * len(alts)

        for relay_idx in range(num_relays):
            print(f"\n  优化第{relay_idx+1}个中继...")

            best_new_coverage = 0
            best_relay = None
            best_covered = set()
            best_details_this = []

            evaluated = 0

            for lon in lons:
                for lat in lats:
                    for alt in alts:
                        relay_pos = (lon, lat, alt)

                        # 计算这个中继能新增覆盖多少服务区
                        coverage, covered, details = evaluate_relay_position(
                            relay_pos, depot_pos, service_area_positions,
                            comm_params, relay_specs, transport_specs
                        )

                        # 计算新增覆盖（covered是列表，需转为集合）
                        covered_set = set(covered)
                        new_covered = covered_set - all_covered
                        new_coverage_count = len(new_covered)

                        if new_coverage_count > best_new_coverage:
                            best_new_coverage = new_coverage_count
                            best_relay = relay_pos
                            best_covered = covered_set
                            best_details_this = details

                        evaluated += 1
                        if evaluated % 1000 == 0:
                            print(f"    进度: {evaluated}/{total_candidates} ({evaluated/total_candidates*100:.1f}%) "
                                  f"- 当前最优新增: {best_new_coverage}个服务区")

            if best_relay is None or best_new_coverage == 0:
                print(f"  [完成] 无法找到更多有效中继位置")
                break

            # 添加这个中继
            relay_positions.append(best_relay)
            all_covered.update(best_covered)
            all_details.extend(best_details_this)

            current_coverage = len(all_covered) / len(service_area_positions)
            print(f"  第{relay_idx+1}个中继: 位置{best_relay}, 新增{best_new_coverage}个, 总覆盖{len(all_covered)}/{len(service_area_positions)} ({current_coverage*100:.1f}%)")

            # 如果已达到100%，提前结束
            if current_coverage >= 1.0:
                print(f"  [成功] 已达到100%覆盖率!")
                break

        final_coverage = len(all_covered) / len(service_area_positions)
        return relay_positions, final_coverage, list(all_covered), all_details


def calculate_relay_energy(relay_pos, depot_pos, mission_duration_min, relay_specs):
    """
    计算中继UAV的总能耗

    Returns:
        total_energy_kwh: 总能耗(kWh)
        flight_energy_kwh: 飞行能耗
        hover_energy_kwh: 悬停能耗
        comm_energy_kwh: 通信能耗
    """
    # 飞往中继位置的距离
    distance_m = calculate_distance_3d(depot_pos, relay_pos)
    distance_km = distance_m / 1000

    # 飞行时间（往返）
    cruise_speed_ms = relay_specs['cruise_speed_ms']
    flight_time_one_way_h = (distance_m / cruise_speed_ms) / 3600
    flight_time_total_h = flight_time_one_way_h * 2  # 往返

    # 飞行能耗（使用巡航功率）
    flight_energy_kwh = relay_specs['cruise_power_kw'] * flight_time_total_h

    # 悬停时间
    hover_time_h = mission_duration_min / 60

    # 悬停能耗（包括通信功率）
    hover_power = relay_specs['hover_power_kw']
    comm_power = relay_specs['comm_power_kw']
    hover_energy_kwh = hover_power * hover_time_h
    comm_energy_kwh = comm_power * hover_time_h

    # 总能耗
    total_energy_kwh = flight_energy_kwh + hover_energy_kwh + comm_energy_kwh

    return total_energy_kwh, flight_energy_kwh, hover_energy_kwh, comm_energy_kwh


def main():
    """主函数"""
    print("\n" + "="*80)
    print("问题三：通信约束下的运输与中继联合调度")
    print("="*80)

    # 1. 加载数据
    print("\n[步骤1] 加载数据...")
    loader = DataLoader()
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    relay_specs = loader.get_relay_uav()
    transport_types = loader.get_uav_types()
    comm_params_loaded = loader.get_comm_params()

    # 调度中心位置（使用实际海拔）
    depot_pos = (depot['longitude'], depot['latitude'], depot['altitude'])

    # 服务区位置（使用实际海拔+飞行高度）
    service_area_positions = {}
    for _, sa in service_areas.iterrows():
        # 运输UAV飞行高度约50-100m
        service_area_positions[sa['id']] = (sa['longitude'], sa['latitude'], sa['altitude'] + 50)

    print(f"  调度中心: ({depot_pos[0]:.4f}, {depot_pos[1]:.4f}, {depot_pos[2]}m)")
    print(f"  服务区数量: {len(service_area_positions)}")

    # 通信参数（从loader获取并补充）
    # 原始参数: f(频率), Lsys(系统损耗), Lobs(障碍损耗), Psens(灵敏度), M(衰落余量)
    # Pt(地面站发射功率), G(地面站天线增益), hG(地面站高度)
    comm_params = {
        'carrier_frequency_mhz': comm_params_loaded.get('f', 2400),
        'system_loss_db': comm_params_loaded.get('Lsys', 3),
        'obstacle_loss_db': comm_params_loaded.get('Lobs', 10),
        'sensitivity_dbm': comm_params_loaded.get('Psens', -98),
        'margin_db': comm_params_loaded.get('M', 8),
        'ground_station_tx_power_dbm': comm_params_loaded.get('Pt', 27),
        'ground_station_antenna_gain_dbi': comm_params_loaded.get('G', 12),
        'ground_station_height_m': comm_params_loaded.get('hG', 20),
        # 运输UAV参数（从数据推断）
        'transport_tx_power_dbm': 20,
        'transport_tx_antenna_gain_dbi': 3,
        # 中继UAV参数（从数据推断）
        'relay_tx_power_dbm': 20,
        'relay_tx_antenna_gain_dbi': 6,
        'relay_rx_antenna_gain_dbi': 8
    }

    # 2. 读取问题二的调度方案
    print("\n[步骤2] 读取问题二的调度方案...")
    df_problem2 = pd.read_excel('结果/问题二_符合赛题规则方案.xlsx',
                                 sheet_name='调度方案')
    mission_duration = df_problem2.iloc[:, -3].max()  # 结束时间列
    print(f"  总调度时间: {mission_duration:.2f} 分钟")

    # 3. 优化中继位置
    print("\n[步骤3] 优化中继位置...")

    # 先尝试单中继
    relays, coverage, covered, details = optimize_relay_placement_grid_search(
        depot_pos, service_area_positions,
        comm_params, relay_specs, transport_types,
        num_relays=1
    )

    print(f"\n[结果] 单中继方案:")
    print(f"  覆盖率: {coverage*100:.1f}% ({len(covered)}/{len(service_area_positions)}个服务区)")
    if relays:
        print(f"  中继位置: ({relays[0][0]:.4f}, {relays[0][1]:.4f}, {relays[0][2]:.0f}m)")
        print(f"  覆盖的服务区: {sorted(covered)}")

    uncovered = set(service_area_positions.keys()) - set(covered)
    if uncovered:
        print(f"  未覆盖服务区: {sorted(uncovered)}")
        print(f"\n  [需要多中继] 单中继覆盖率不足，自动增加中继数量...")

        # 尝试多中继（最多5个）
        for num_relays in range(2, 6):
            print(f"\n[尝试] {num_relays}个中继方案:")
            relays, coverage, covered, details = optimize_relay_placement_grid_search(
                depot_pos, service_area_positions,
                comm_params, relay_specs, transport_types,
                num_relays=num_relays
            )

            print(f"  覆盖率: {coverage*100:.1f}% ({len(covered)}/{len(service_area_positions)}个服务区)")

            if coverage >= 1.0:
                print(f"  [成功] 达到100%覆盖!")
                break

            uncovered = set(service_area_positions.keys()) - set(covered)
            if uncovered:
                print(f"  仍未覆盖: {sorted(uncovered)}")

    # 4. 计算能耗
    print("\n[步骤4] 计算能耗...")

    # 计算所有中继的总能耗
    total_relay_energy = 0
    total_flight_energy = 0
    total_hover_energy = 0
    total_comm_energy = 0

    for idx, relay_pos in enumerate(relays):
        relay_energy, flight_energy, hover_energy, comm_energy = calculate_relay_energy(
            relay_pos, depot_pos, mission_duration, relay_specs
        )
        total_relay_energy += relay_energy
        total_flight_energy += flight_energy
        total_hover_energy += hover_energy
        total_comm_energy += comm_energy

        print(f"  中继{idx+1}: 总能耗{relay_energy:.2f}kWh (飞行{flight_energy:.2f} + 悬停{hover_energy:.2f} + 通信{comm_energy:.2f})")

    # 读取问题二的运输能耗
    summary = pd.read_excel('结果/问题二_符合赛题规则方案.xlsx',
                           sheet_name='关键指标')
    transport_energy = summary[summary.iloc[:, 0].str.contains('能耗', na=False)].iloc[0, 1]

    total_energy = transport_energy + total_relay_energy
    energy_increase = (total_relay_energy / transport_energy) * 100

    print(f"\n  运输能耗: {transport_energy:.2f} kWh")
    print(f"  中继总能耗: {total_relay_energy:.2f} kWh")
    print(f"    - 飞行: {total_flight_energy:.2f} kWh")
    print(f"    - 悬停: {total_hover_energy:.2f} kWh")
    print(f"    - 通信: {total_comm_energy:.2f} kWh")
    print(f"  总能耗: {total_energy:.2f} kWh")
    print(f"  中继能耗增幅: {energy_increase:.1f}%")

    # 5. 保存结果
    print("\n[步骤5] 保存结果...")

    # 中继部署方案（支持多中继）
    relay_data = []
    for idx, relay_pos in enumerate(relays):
        relay_energy_single, flight_energy_single, hover_energy_single, comm_energy_single = calculate_relay_energy(
            relay_pos, depot_pos, mission_duration, relay_specs
        )
        relay_data.append({
            '中继ID': f'R{idx+1:02d}',
            '经度': relay_pos[0],
            '纬度': relay_pos[1],
            '悬停高度(m)': relay_pos[2],
            '悬停时长(分钟)': mission_duration,
            '飞行能耗(kWh)': flight_energy_single,
            '悬停能耗(kWh)': hover_energy_single,
            '通信能耗(kWh)': comm_energy_single,
            '总能耗(kWh)': relay_energy_single
        })

    relay_df = pd.DataFrame(relay_data)

    # 覆盖详情
    coverage_df = pd.DataFrame([{
        '服务区': area_id,
        '是否覆盖': '是' if area_id in covered else '否'
    } for area_id in sorted(service_area_positions.keys())])

    # 链路详情
    link_df = pd.DataFrame(details)

    # 保存到Excel
    output_file = Path('结果/问题三_中继部署方案_新.xlsx')
    with pd.ExcelWriter(output_file) as writer:
        relay_df.to_excel(writer, sheet_name='中继部署', index=False)
        coverage_df.to_excel(writer, sheet_name='覆盖详情', index=False)
        if not link_df.empty:
            link_df.to_excel(writer, sheet_name='链路余量', index=False)

    print(f"  结果已保存: {output_file}")

    print("\n" + "="*80)
    print("问题三求解完成!")
    print("="*80)

    if coverage < 1.0:
        print("\n[WARN] 警告: 当前方案覆盖率<100%，不符合赛题要求")
        print("   建议: 增加中继数量或调整部署策略")
    else:
        print(f"\n[成功] 达到100%覆盖率，使用{len(relays)}个中继!")

    return {
        'coverage': coverage,
        'num_relays': len(relays),
        'relay_energy': total_relay_energy,
        'total_energy': total_energy
    }


if __name__ == "__main__":
    result = main()
