#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题三可视化模块 - 通信覆盖与中继部署
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader

# 学术配色方案
COLORS = {
    'gateway': '#DD9F95',      # 暖橙 - 网关
    'relay': '#568BC1',        # 深蓝 - 中继
    'service': '#AAD498',      # 草绿 - 服务区
    'blind': '#CC5536',        # 深橙 - 盲区
    'covered': '#A6C9C1',      # 浅青 - 已覆盖
    'path': '#E6E6E6',         # 浅灰 - 路径
    'text': '#2B2B2B',         # 深灰 - 文字
}

matplotlib.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


def plot_communication_coverage_3d(loader: DataLoader, dem_file: str,
                                   relay_deployment: list, output_dir: Path):
    """
    绘制3D通信覆盖图
    """
    print("\n生成3D通信覆盖图...")

    # 加载DEM
    dem_loader = DEMLoader(dem_file)
    dem_data, dem_bounds = dem_loader.load()

    # 创建3D图
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')

    # 创建网格
    x = np.linspace(dem_bounds['min_x'], dem_bounds['max_x'], dem_data.shape[1])
    y = np.linspace(dem_bounds['max_y'], dem_bounds['min_y'], dem_data.shape[0])
    X, Y = np.meshgrid(x, y)

    # 绘制地形（下采样以提高性能）
    step = 10
    X_plot = X[::step, ::step]
    Y_plot = Y[::step, ::step]
    Z_plot = dem_data[::step, ::step]

    ax.plot_surface(X_plot, Y_plot, Z_plot, cmap='terrain', alpha=0.6,
                   linewidth=0, antialiased=True, vmin=0, vmax=1200)

    # 绘制网关
    depot = loader.get_depot()
    gateway_z = dem_loader.get_height(depot['longitude'], depot['latitude'])
    if gateway_z:
        ax.scatter([depot['longitude']], [depot['latitude']], [gateway_z + 50],
                  c=COLORS['gateway'], s=500, marker='*',
                  edgecolors='black', linewidths=2,
                  label='Gateway O01', zorder=10)

    # 绘制中继机
    for relay in relay_deployment:
        pos = relay['position']
        ax.scatter([pos[0]], [pos[1]], [pos[2]],
                  c=COLORS['relay'], s=300, marker='^',
                  edgecolors='black', linewidths=1.5,
                  label=f'Relay {relay["relay_id"]}', zorder=9)

    # 绘制服务区
    service_areas = loader.get_service_areas()
    for _, area in service_areas.iterrows():
        area_z = dem_loader.get_height(area['longitude'], area['latitude'])
        if area_z:
            ax.scatter([area['longitude']], [area['latitude']], [area_z + 20],
                      c=COLORS['service'], s=100, alpha=0.7,
                      edgecolors='black', linewidths=1)

    ax.set_xlabel('Longitude (°E)', fontsize=11, labelpad=10)
    ax.set_ylabel('Latitude (°N)', fontsize=11, labelpad=10)
    ax.set_zlabel('Altitude (m)', fontsize=11, labelpad=10)
    ax.set_title('3D Communication Coverage with Terrain',
                fontsize=14, fontweight='bold', pad=20)

    # 设置视角
    ax.view_init(elev=25, azim=45)

    # 图例（去重）
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(),
             loc='upper left', fontsize=9)

    plt.tight_layout()

    output_file = output_dir / "问题三_3D通信覆盖图.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"  已保存: {output_file}")
    plt.close()


def plot_relay_deployment_map(loader: DataLoader, relay_deployment: list,
                              blind_zones: list, output_dir: Path):
    """
    绘制中继部署平面图
    """
    print("\n生成中继部署图...")

    fig, ax = plt.subplots(figsize=(12, 10))

    # 获取网关
    depot = loader.get_depot()

    # 绘制网关
    ax.scatter(depot['longitude'], depot['latitude'],
              c=COLORS['gateway'], s=600, marker='*',
              edgecolors='black', linewidths=2.5,
              label='Gateway O01', zorder=10)

    # 绘制中继机及其覆盖范围
    for relay in relay_deployment:
        pos = relay['position']

        # 中继位置
        ax.scatter(pos[0], pos[1],
                  c=COLORS['relay'], s=400, marker='^',
                  edgecolors='black', linewidths=2,
                  label=f'Relay {relay["relay_id"]}', zorder=9)

        # 覆盖范围（简化为圆形）
        coverage_radius = 0.05  # 约5km
        circle = plt.Circle((pos[0], pos[1]), coverage_radius,
                          color=COLORS['relay'], alpha=0.15, zorder=1)
        ax.add_patch(circle)

        # 标注
        ax.text(pos[0], pos[1] + 0.01, f'R{relay["relay_id"]}',
               fontsize=10, ha='center', fontweight='bold',
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor=COLORS['relay'], linewidth=1.5))

    # 绘制服务区
    service_areas = loader.get_service_areas()

    # 标记盲区服务区
    blind_area_ids = set()
    for zone_points, mission_id in blind_zones:
        # 从mission_id获取服务区ID（简化处理）
        if mission_id < len(service_areas):
            blind_area_ids.add(service_areas.iloc[mission_id]['id'])

    for _, area in service_areas.iterrows():
        if area['id'] in blind_area_ids:
            # 盲区
            ax.scatter(area['longitude'], area['latitude'],
                      c=COLORS['blind'], s=200, alpha=0.8,
                      edgecolors='black', linewidths=1.5,
                      marker='s', label='Blind Zone' if area['id'] == list(blind_area_ids)[0] else '')
        else:
            # 直连区
            ax.scatter(area['longitude'], area['latitude'],
                      c=COLORS['covered'], s=150, alpha=0.7,
                      edgecolors='black', linewidths=1,
                      marker='o', label='Direct Link' if area['id'] == 'S001' else '')

    ax.set_xlabel('Longitude (°E)', fontsize=12, fontweight='medium')
    ax.set_ylabel('Latitude (°N)', fontsize=12, fontweight='medium')
    ax.set_title('Relay Deployment and Coverage Map',
                fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.legend(loc='upper right', fontsize=10, framealpha=0.95)

    plt.tight_layout()

    output_file = output_dir / "问题三_中继部署图.png"
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"  已保存: {output_file}")
    plt.close()


def plot_energy_breakdown(objectives: dict, output_dir: Path):
    """
    绘制能耗分解图
    """
    print("\n生成能耗分解图...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 左图：能耗组成
    categories = ['Transport\nUAVs', 'Relay\nUAVs']
    energies = [objectives['transport_energy'], objectives['relay_energy']]
    colors_list = [COLORS['service'], COLORS['relay']]

    bars = ax1.bar(categories, energies, color=colors_list,
                   edgecolor='black', linewidth=1.5, alpha=0.85)

    ax1.set_ylabel('Energy Consumption (kWh)', fontsize=12, fontweight='medium')
    ax1.set_title('(a) Energy Breakdown', fontsize=13, fontweight='bold', pad=10)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_ylim(0, max(energies) * 1.2)

    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{height:.1f} kWh\n({height/sum(energies)*100:.1f}%)',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    # 右图：饼图
    ax2.pie(energies, labels=categories, autopct='%1.1f%%',
           colors=colors_list, startangle=90,
           wedgeprops={'edgecolor': 'black', 'linewidth': 1.5})
    ax2.set_title('(b) Energy Distribution', fontsize=13, fontweight='bold', pad=10)

    plt.tight_layout()

    output_file = output_dir / "问题三_能耗分解图.png"
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"  已保存: {output_file}")
    plt.close()


def plot_multi_objective_comparison(output_dir: Path):
    """
    绘制多目标对比图（问题二 vs 问题三）
    """
    print("\n生成多目标对比图...")

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Problem 2 vs Problem 3: Multi-Objective Comparison',
                fontsize=15, fontweight='bold', y=0.995)

    # 模拟数据（实际应从结果文件读取）
    categories = ['Problem 2\n(No Relay)', 'Problem 3\n(With Relay)']

    # (a) 完成时间
    ax = axes[0, 0]
    completion_times = [296.86, 296.86]  # 相同
    bars = ax.bar(categories, completion_times,
                  color=[COLORS['covered'], COLORS['relay']],
                  edgecolor='black', linewidth=1.5, alpha=0.85)
    ax.set_ylabel('Completion Time (min)', fontsize=11, fontweight='medium')
    ax.set_title('(a) Total Completion Time', fontsize=12, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    # (b) 总能耗
    ax = axes[0, 1]
    total_energies = [45.90, 76.59]
    bars = ax.bar(categories, total_energies,
                  color=[COLORS['covered'], COLORS['relay']],
                  edgecolor='black', linewidth=1.5, alpha=0.85)
    ax.set_ylabel('Total Energy (kWh)', fontsize=11, fontweight='medium')
    ax.set_title('(b) Total Energy Consumption', fontsize=12, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    # (c) 通信覆盖率
    ax = axes[1, 0]
    coverage_rates = [33.3, 100.0]  # 问题二无中继，部分盲区；问题三100%覆盖
    bars = ax.bar(categories, coverage_rates,
                  color=[COLORS['covered'], COLORS['relay']],
                  edgecolor='black', linewidth=1.5, alpha=0.85)
    ax.set_ylabel('Communication Coverage (%)', fontsize=11, fontweight='medium')
    ax.set_title('(c) Communication Coverage Rate', fontsize=12, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, 110)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=10, fontweight='bold')

    # (d) 使用架次
    ax = axes[1, 1]
    x = np.arange(len(categories))
    width = 0.35

    transport_trips = [15, 15]
    relay_trips = [0, 2]  # 假设优化后2架中继

    bars1 = ax.bar(x - width/2, transport_trips, width,
                   label='Transport UAVs', color=COLORS['service'],
                   edgecolor='black', linewidth=1.5, alpha=0.85)
    bars2 = ax.bar(x + width/2, relay_trips, width,
                   label='Relay UAVs', color=COLORS['relay'],
                   edgecolor='black', linewidth=1.5, alpha=0.85)

    ax.set_ylabel('Number of Missions', fontsize=11, fontweight='medium')
    ax.set_title('(d) Mission Count Comparison', fontsize=12, fontweight='bold', pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)

    # 添加数值标签
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height + 0.3,
                       f'{int(height)}',
                       ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()

    output_file = output_dir / "问题三_多目标对比图.png"
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"  已保存: {output_file}")
    plt.close()


def generate_all_visualizations():
    """生成所有可视化图表"""
    print("="*80)
    print("问题三 - 生成可视化图表")
    print("="*80)

    # 加载数据
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 读取中继部署结果
    relay_file = Path("结果/问题三_中继部署.xlsx")
    if relay_file.exists():
        df_relay = pd.read_excel(relay_file, engine='openpyxl')
        relay_deployment = []
        for _, row in df_relay.iterrows():
            # 解析position字符串 "(x, y, z)"
            pos_str = str(row['position']).strip('()')
            pos_parts = pos_str.split(',')
            pos = (float(pos_parts[0]), float(pos_parts[1]), float(pos_parts[2]))

            relay_deployment.append({
                'relay_id': row['relay_id'],
                'position': pos,
                'service_start': row['service_start'],
                'service_end': row['service_end'],
                'energy': row['energy']
            })
    else:
        print("警告: 未找到中继部署结果，使用模拟数据")
        relay_deployment = [
            {'relay_id': 0, 'position': (109.25, 23.02, 400),
             'service_start': 50, 'service_end': 250, 'energy': 30.69}
        ]

    # 创建输出目录
    output_dir = Path("结果/图表")
    output_dir.mkdir(parents=True, exist_ok=True)

    # DEM文件
    dem_file = "数据/镇龙乡地理空间数据/镇龙乡及周边地理数据/数字高程模型数据（DEM）/镇龙乡及周边30米DEM.mat"

    # 模拟盲区数据
    blind_zones = []

    # 生成图表
    plot_relay_deployment_map(loader, relay_deployment, blind_zones, output_dir)
    plot_energy_breakdown({'transport_energy': 45.90, 'relay_energy': 30.69}, output_dir)
    plot_multi_objective_comparison(output_dir)

    # 3D图（可选，较耗时）
    try:
        plot_communication_coverage_3d(loader, dem_file, relay_deployment, output_dir)
    except Exception as e:
        print(f"  警告: 3D图生成失败 ({e})")

    print("\n" + "="*80)
    print("问题三可视化完成！")
    print("="*80)


if __name__ == "__main__":
    generate_all_visualizations()
