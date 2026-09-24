#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断通信模型 - 检查为什么覆盖率为0
"""

import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader


def calculate_distance_3d(coord1, coord2):
    """计算三维距离"""
    lon1, lat1, alt1 = coord1
    lon2, lat2, alt2 = coord2

    R = 6371000
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)

    a = (np.sin(dlat/2)**2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon/2)**2)
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    horizontal_dist = R * c
    vertical_dist = abs(alt2 - alt1)
    distance_3d = np.sqrt(horizontal_dist**2 + vertical_dist**2)

    return distance_3d


def calculate_link_budget(tx_power_dbm, tx_gain_dbi, rx_gain_dbi,
                          distance_m, frequency_mhz,
                          system_loss_db=3, obstacle_loss_db=10):
    """计算链路预算"""
    # 自由空间路径损耗 (Friis公式)
    # FSPL(dB) = 20*log10(d_km) + 20*log10(f_MHz) + 32.45
    distance_km = distance_m / 1000
    fspl_db = 20 * np.log10(distance_km) + 20 * np.log10(frequency_mhz) + 32.45

    # 接收功率
    rx_power_dbm = (tx_power_dbm + tx_gain_dbi + rx_gain_dbi -
                    fspl_db - system_loss_db - obstacle_loss_db)

    return rx_power_dbm, fspl_db


def main():
    print("="*80)
    print("通信模型诊断")
    print("="*80)

    # 加载数据
    loader = DataLoader()
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    comm_params_loaded = loader.get_comm_params()

    # 通信参数
    comm_params = {
        'carrier_frequency_mhz': comm_params_loaded.get('f', 2400),
        'system_loss_db': comm_params_loaded.get('Lsys', 3),
        'obstacle_loss_db': comm_params_loaded.get('Lobs', 10),
        'sensitivity_dbm': comm_params_loaded.get('Psens', -98),
        'margin_db': comm_params_loaded.get('M', 8),
        'ground_station_tx_power_dbm': comm_params_loaded.get('Pt', 27),
        'ground_station_antenna_gain_dbi': comm_params_loaded.get('G', 12),
    }

    print("\n通信参数:")
    for key, val in comm_params.items():
        print(f"  {key}: {val}")

    # 测试：调度中心G01 -> 中继位置 -> 服务区S001
    print("\n" + "="*80)
    print("测试场景: G01 -> 中继 -> S001")
    print("="*80)

    # 位置
    depot_pos = (depot['longitude'], depot['latitude'], depot['altitude'])
    s001 = service_areas[service_areas['id'] == 'S001'].iloc[0]
    s001_pos = (s001['longitude'], s001['latitude'], s001['altitude'] + 50)

    # 中继位置：在两者中间，高度250m
    relay_lon = (depot_pos[0] + s001_pos[0]) / 2
    relay_lat = (depot_pos[1] + s001_pos[1]) / 2
    relay_alt = 250
    relay_pos = (relay_lon, relay_lat, relay_alt)

    print(f"\n位置信息:")
    print(f"  G01 (调度中心): {depot_pos}")
    print(f"  中继位置: {relay_pos}")
    print(f"  S001 (服务区): {s001_pos}")

    # 计算距离
    dist_g01_relay = calculate_distance_3d(depot_pos, relay_pos)
    dist_relay_s001 = calculate_distance_3d(relay_pos, s001_pos)
    dist_g01_s001 = calculate_distance_3d(depot_pos, s001_pos)

    print(f"\n距离:")
    print(f"  G01 -> 中继: {dist_g01_relay:.0f} m ({dist_g01_relay/1000:.2f} km)")
    print(f"  中继 -> S001: {dist_relay_s001:.0f} m ({dist_relay_s001/1000:.2f} km)")
    print(f"  G01 -> S001 (直连): {dist_g01_s001:.0f} m ({dist_g01_s001/1000:.2f} km)")

    # 链路1: G01 -> 中继
    print(f"\n链路1: G01 -> 中继")
    tx_power_1 = comm_params['ground_station_tx_power_dbm']
    tx_gain_1 = comm_params['ground_station_antenna_gain_dbi']
    rx_gain_1 = 8  # 中继接收增益

    rx_power_1, fspl_1 = calculate_link_budget(
        tx_power_1, tx_gain_1, rx_gain_1,
        dist_g01_relay, comm_params['carrier_frequency_mhz'],
        comm_params['system_loss_db'], comm_params['obstacle_loss_db']
    )

    print(f"  发射功率: {tx_power_1} dBm")
    print(f"  发射增益: {tx_gain_1} dBi")
    print(f"  接收增益: {rx_gain_1} dBi")
    print(f"  自由空间损耗: {fspl_1:.2f} dB")
    print(f"  系统损耗: {comm_params['system_loss_db']} dB")
    print(f"  障碍损耗: {comm_params['obstacle_loss_db']} dB")
    print(f"  接收功率: {rx_power_1:.2f} dBm")
    print(f"  接收灵敏度: {comm_params['sensitivity_dbm']} dBm")
    print(f"  余量要求: {comm_params['margin_db']} dB")
    print(f"  实际余量: {rx_power_1 - comm_params['sensitivity_dbm']:.2f} dB")

    threshold_1 = comm_params['sensitivity_dbm'] + comm_params['margin_db']
    link1_ok = rx_power_1 >= threshold_1
    print(f"  链路状态: {'[OK] 通' if link1_ok else '[FAIL] 断'} (需要 >= {threshold_1} dBm)")

    # 链路2: 中继 -> S001 (运输UAV)
    print(f"\n链路2: 中继 -> S001")
    tx_power_2 = 20  # 中继发射功率
    tx_gain_2 = 6    # 中继发射增益
    rx_gain_2 = 3    # 运输UAV接收增益

    rx_power_2, fspl_2 = calculate_link_budget(
        tx_power_2, tx_gain_2, rx_gain_2,
        dist_relay_s001, comm_params['carrier_frequency_mhz'],
        comm_params['system_loss_db'], comm_params['obstacle_loss_db']
    )

    print(f"  发射功率: {tx_power_2} dBm")
    print(f"  发射增益: {tx_gain_2} dBi")
    print(f"  接收增益: {rx_gain_2} dBi")
    print(f"  自由空间损耗: {fspl_2:.2f} dB")
    print(f"  系统损耗: {comm_params['system_loss_db']} dB")
    print(f"  障碍损耗: {comm_params['obstacle_loss_db']} dB")
    print(f"  接收功率: {rx_power_2:.2f} dBm")
    print(f"  接收灵敏度: {comm_params['sensitivity_dbm']} dBm")
    print(f"  余量要求: {comm_params['margin_db']} dB")
    print(f"  实际余量: {rx_power_2 - comm_params['sensitivity_dbm']:.2f} dB")

    threshold_2 = comm_params['sensitivity_dbm'] + comm_params['margin_db']
    link2_ok = rx_power_2 >= threshold_2
    print(f"  链路状态: {'[OK] 通' if link2_ok else '[FAIL] 断'} (需要 >= {threshold_2} dBm)")

    # 总体评估
    print("\n" + "="*80)
    both_ok = link1_ok and link2_ok
    print(f"总体评估: {'[OK] S001可以通过中继与G01通信' if both_ok else '[FAIL] 通信不可用'}")
    print("="*80)

    if not both_ok:
        print("\n问题诊断:")
        if not link1_ok:
            shortage = threshold_1 - rx_power_1
            print(f"  [FAIL] 链路1不足 {shortage:.2f} dB")
        if not link2_ok:
            shortage = threshold_2 - rx_power_2
            print(f"  [FAIL] 链路2不足 {shortage:.2f} dB")

        print("\n可能的解决方案:")
        print("  1. 增加中继发射功率")
        print("  2. 减小中继到服务区的距离（调整中继位置）")
        print("  3. 减小障碍损耗（选择更好的中继高度）")
        print("  4. 降低余量要求（风险较大）")


if __name__ == "__main__":
    main()
