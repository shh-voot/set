#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二 - 高级可视化（3D甘特图、并行坐标图、树状图）
展示多架次调度的多维度特征
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Rectangle
import squarify  # 用于树状图
from pathlib import Path
import sys

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader

# ============================================================================
# 学术配色方案
# ============================================================================

PALETTE_CATEGORICAL = {
    'A': '#80D0E4',
    'B': '#568BC1',
    'C': '#AAD498',
    'depot': '#DD9F95',
    'highlight': '#BC9DA8',
}

PALETTE_STATUS = {
    'flying': '#568BC1',
    'charging': '#EBA48F',
    'preparing': '#EED5BE',
    'idle': '#A6C9C1',
    'service': '#61847D',
}

PALETTE_SEQUENTIAL = {
    'low': '#A6C9C1',
    'medium': '#EED5BE',
    'high': '#EBA48F',
    'critical': '#CC5536',
    'context': '#61847D',
}

COLORS = {
    'background': '#FFFFFF',
    'text_main': '#2B2B2B',
    'text_secondary': '#666666',
    'grid': '#E6E6E6',
    'outline': '#4A4A4A',
}

matplotlib.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.facecolor'] = COLORS['background']
matplotlib.rcParams['axes.facecolor'] = COLORS['background']


def load_data():
    """加载数据和结果"""
    loader = DataLoader()
    loader.load_all()

    result_file = Path("结果/问题二_调度方案.xlsx")
    if not result_file.exists():
        raise FileNotFoundError(f"请先运行问题二求解器: {result_file}")

    df_schedule = pd.read_excel(result_file, engine='openpyxl')

    return loader, df_schedule


def plot_3d_gantt(df_schedule):
    """
    3D甘特图 - 时间×资源×能量状态
    X: 时间, Y: 无人机ID, Z: 电量百分比
    """
    print("生成3D甘特图...")

    fig = plt.figure(figsize=(16, 10))
    ax = fig.add_subplot(111, projection='3d')

    uav_ids = df_schedule['无人机ID'].unique()
    y_positions = {uav_id: i for i, uav_id in enumerate(uav_ids)}

    # 为每个任务绘制3D立方体
    for _, row in df_schedule.iterrows():
        uav_id = row['无人机ID']
        y_pos = y_positions[uav_id]

        start_time = row['开始时间(分钟)']
        end_time = row['结束时间(分钟)']
        duration = end_time - start_time

        # 假设能量从100%下降
        energy_start = 100
        energy_end = max(20, 100 - row['能耗(kWh)'] / 8 * 100)  # 简化计算

        # 机型颜色
        uav_type = row['机型']
        color = PALETTE_CATEGORICAL.get(uav_type, PALETTE_STATUS['flying'])

        # 绘制立方体表示任务
        xs = [start_time, end_time]
        ys = [y_pos - 0.3, y_pos + 0.3]
        zs = [energy_end, energy_start]

        # 侧面
        xx, yy = np.meshgrid(xs, ys)
        ax.plot_surface(xx, yy, np.ones_like(xx) * energy_start,
                       alpha=0.3, color=color, edgecolor=COLORS['outline'], linewidth=0.5)
        ax.plot_surface(xx, yy, np.ones_like(xx) * energy_end,
                       alpha=0.3, color=color, edgecolor=COLORS['outline'], linewidth=0.5)

        # 能量变化线
        ax.plot([start_time, end_time], [y_pos, y_pos], [energy_start, energy_end],
               color=color, linewidth=3, alpha=0.9)

        # 标注服务区
        ax.text(start_time + duration/2, y_pos, energy_start,
               row['服务区'], fontsize=8, ha='center', color=COLORS['text_main'])

    ax.set_xlabel('Time (minutes)', fontsize=12, fontweight='medium', labelpad=10)
    ax.set_ylabel('UAV ID', fontsize=12, fontweight='medium', labelpad=10)
    ax.set_zlabel('Battery Level (%)', fontsize=12, fontweight='medium', labelpad=10)
    ax.set_title('3D Multi-Trip Scheduling Gantt Chart\n(Energy-Time-Resource Space)',
                fontsize=14, fontweight='bold', pad=20)

    ax.set_yticks(range(len(uav_ids)))
    ax.set_yticklabels(uav_ids, fontsize=10)
    ax.set_zlim(0, 100)

    ax.view_init(elev=20, azim=45)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_3D甘特图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 3D甘特图已保存: {output_file}")
    plt.close()


def plot_parallel_coordinates(df_schedule):
    """
    并行坐标图 - 多维任务特征
    展示每个任务在多个维度上的值
    """
    print("生成并行坐标图...")

    # 准备数据 - 使用实际列名
    features = ['开始时间(分钟)', '飞行时长(分钟)', '总重量(kg)', '能耗(kWh)']

    # 归一化
    df_normalized = df_schedule[features].copy()
    for col in features:
        min_val = df_normalized[col].min()
        max_val = df_normalized[col].max()
        if max_val > min_val:
            df_normalized[col] = (df_normalized[col] - min_val) / (max_val - min_val)
        else:
            df_normalized[col] = 0.5

    fig, ax = plt.subplots(figsize=(14, 8))

    # 绘制每条任务线
    x = np.arange(len(features))
    for idx, row in df_normalized.iterrows():
        y = row.values
        uav_type = df_schedule.loc[idx, '机型']
        color = PALETTE_CATEGORICAL.get(uav_type, COLORS['text_secondary'])

        ax.plot(x, y, color=color, alpha=0.3, linewidth=1.5)

    # 添加坐标轴
    for i in range(len(features)):
        ax.axvline(i, color=COLORS['grid'], linestyle='--', linewidth=1, alpha=0.5)

    # 设置刻度和标签
    ax.set_xticks(x)
    ax.set_xticklabels(features, fontsize=11, fontweight='medium', rotation=15, ha='right')
    ax.set_ylim(-0.05, 1.05)
    ax.set_ylabel('Normalized Value (0-1)', fontsize=12, fontweight='medium')
    ax.set_title('Parallel Coordinates Plot - Multi-Dimensional Task Features\n(Each line = One mission)',
                fontsize=14, fontweight='bold', pad=20)

    # 添加实际值范围标注
    for i, feature in enumerate(features):
        min_val = df_schedule[feature].min()
        max_val = df_schedule[feature].max()
        ax.text(i, -0.15, f'{min_val:.1f}',
               ha='center', va='top', fontsize=9, color=COLORS['text_secondary'])
        ax.text(i, 1.15, f'{max_val:.1f}',
               ha='center', va='bottom', fontsize=9, color=COLORS['text_secondary'])

    # 图例
    legend_elements = [
        mpatches.Patch(facecolor=PALETTE_CATEGORICAL['B'], label='Type B UAV'),
        mpatches.Patch(facecolor=PALETTE_CATEGORICAL['C'], label='Type C UAV'),
    ]
    ax.legend(handles=legend_elements, loc='upper right',
             fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])

    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_并行坐标图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 并行坐标图已保存: {output_file}")
    plt.close()


def plot_treemap(df_schedule):
    """
    树状图 - 时间分配的层级结构
    第一层: 各无人机, 第二层: 飞行/充电/准备时间
    """
    print("生成树状图...")

    # 计算每架无人机的时间分配
    uav_data = []
    for uav_id in df_schedule['无人机ID'].unique():
        subset = df_schedule[df_schedule['无人机ID'] == uav_id]

        flight_time = subset['飞行时长(分钟)'].sum()
        num_charges = (subset['是否充电'] == '是').sum()
        charge_time = num_charges * 30  # 假设每次充电30分钟

        uav_data.append({
            'UAV': uav_id,
            'Flight': flight_time,
            'Charging': charge_time,
        })

    # 准备树状图数据
    labels = []
    sizes = []
    colors_list = []

    for data in uav_data:
        # 飞行时间
        labels.append(f"{data['UAV']}\nFlight\n{data['Flight']:.0f}min")
        sizes.append(data['Flight'])
        uav_type = df_schedule[df_schedule['无人机ID'] == data['UAV']]['机型'].iloc[0]
        colors_list.append(PALETTE_CATEGORICAL[uav_type])

        # 充电时间
        if data['Charging'] > 0:
            labels.append(f"{data['UAV']}\nCharging\n{data['Charging']:.0f}min")
            sizes.append(data['Charging'])
            colors_list.append(PALETTE_STATUS['charging'])

    fig, ax = plt.subplots(figsize=(14, 10))

    # 绘制树状图
    squarify.plot(sizes=sizes,
                 label=labels,
                 color=colors_list,
                 alpha=0.8,
                 edgecolor=COLORS['outline'],
                 linewidth=2,
                 text_kwargs={'fontsize': 10, 'weight': 'bold', 'color': 'white'},
                 ax=ax)

    ax.set_title('Time Allocation Treemap - Hierarchical Structure\n(Rectangle size ∝ Time duration)',
                fontsize=15, fontweight='bold', pad=20)
    ax.axis('off')

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_树状图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 树状图已保存: {output_file}")
    plt.close()


def plot_streamgraph(df_schedule):
    """
    流线图 - 能耗随时间的流动
    展示各无人机的瞬时功率随时间变化
    """
    print("生成流线图...")

    # 创建时间轴（每分钟）
    max_time = int(df_schedule['结束时间(分钟)'].max())
    time_axis = np.arange(0, max_time + 1, 1)

    # 为每架无人机创建功率曲线
    uav_ids = sorted(df_schedule['无人机ID'].unique())
    power_curves = {uav_id: np.zeros(len(time_axis)) for uav_id in uav_ids}

    for _, row in df_schedule.iterrows():
        uav_id = row['无人机ID']
        start = int(row['开始时间(分钟)'])
        end = int(row['结束时间(分钟)'])

        # 假设巡航功率为平均值
        avg_power = row['能耗(kWh)'] / (row['飞行时长(分钟)'] / 60) if row['飞行时长(分钟)'] > 0 else 0

        # 填充功率
        power_curves[uav_id][start:end] = avg_power

    # 绘制流线图
    fig, ax = plt.subplots(figsize=(16, 8))

    # 堆叠区域图
    colors = [PALETTE_CATEGORICAL[df_schedule[df_schedule['无人机ID'] == uid]['机型'].iloc[0]]
             for uid in uav_ids]

    baseline = np.zeros(len(time_axis))
    for i, uav_id in enumerate(uav_ids):
        ax.fill_between(time_axis,
                        baseline,
                        baseline + power_curves[uav_id],
                        color=colors[i],
                        alpha=0.7,
                        edgecolor=COLORS['outline'],
                        linewidth=1,
                        label=uav_id)
        baseline += power_curves[uav_id]

    ax.set_xlabel('Time (minutes)', fontsize=13, fontweight='medium')
    ax.set_ylabel('Total Power (kW)', fontsize=13, fontweight='medium')
    ax.set_title('Energy Flow Streamgraph - Power Consumption Over Time',
                fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])
    ax.grid(axis='both', alpha=0.3, linestyle='--', linewidth=0.8)
    ax.set_xlim(0, max_time)
    ax.set_ylim(0, baseline.max() * 1.1)

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_流线图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 流线图已保存: {output_file}")
    plt.close()


def plot_sankey_diagram(df_schedule):
    """
    桑基图（简化版）- 能耗流向
    从各无人机到各服务区的能耗分配
    """
    print("生成桑基图（简化版）...")

    # 按无人机和服务区汇总能耗
    grouped = df_schedule.groupby(['无人机ID', '服务区'])['能耗(kWh)'].sum().reset_index()

    fig, ax = plt.subplots(figsize=(14, 10))

    # 计算位置
    uav_ids = sorted(grouped['无人机ID'].unique())
    service_areas = sorted(grouped['服务区'].unique())

    n_uavs = len(uav_ids)
    n_areas = len(service_areas)

    # Y坐标
    y_uavs = np.linspace(0.1, 0.9, n_uavs)
    y_areas = np.linspace(0.1, 0.9, n_areas)

    uav_y_map = {uav: y for uav, y in zip(uav_ids, y_uavs)}
    area_y_map = {area: y for area, y in zip(service_areas, y_areas)}

    # 绘制流
    for _, row in grouped.iterrows():
        uav_id = row['无人机ID']
        area_id = row['服务区']
        energy = row['能耗(kWh)']

        y_start = uav_y_map[uav_id]
        y_end = area_y_map[area_id]

        # 绘制贝塞尔曲线
        x = np.array([0.2, 0.5, 0.8])
        y = np.array([y_start, (y_start + y_end) / 2, y_end])

        # 插值
        from scipy.interpolate import make_interp_spline
        x_smooth = np.linspace(0.2, 0.8, 100)
        spl = make_interp_spline(x, y, k=2)
        y_smooth = spl(x_smooth)

        # 线宽与能耗成正比
        linewidth = max(1, energy * 5)

        uav_type = df_schedule[df_schedule['无人机ID'] == uav_id]['机型'].iloc[0]
        color = PALETTE_CATEGORICAL[uav_type]

        ax.plot(x_smooth, y_smooth,
               color=color,
               linewidth=linewidth,
               alpha=0.5)

    # 绘制节点
    for uav_id, y in uav_y_map.items():
        ax.scatter(0.2, y, s=300, color=PALETTE_CATEGORICAL['depot'],
                  edgecolors=COLORS['outline'], linewidths=2, zorder=5)
        ax.text(0.15, y, uav_id, ha='right', va='center',
               fontsize=10, fontweight='bold')

    for area_id, y in area_y_map.items():
        ax.scatter(0.8, y, s=200, color=PALETTE_SEQUENTIAL['medium'],
                  edgecolors=COLORS['outline'], linewidths=2, zorder=5)
        ax.text(0.85, y, area_id, ha='left', va='center',
               fontsize=9)

    ax.text(0.2, 0.95, 'UAVs', ha='center', fontsize=13, fontweight='bold')
    ax.text(0.8, 0.95, 'Service Areas', ha='center', fontsize=13, fontweight='bold')

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.set_title('Energy Flow Sankey Diagram (Simplified)\n(Line width ∝ Energy consumption)',
                fontsize=15, fontweight='bold', pad=20)

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_桑基图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 桑基图已保存: {output_file}")
    plt.close()


def main():
    """主函数"""
    print("="*80)
    print("问题二 - 高级可视化（3D甘特图、并行坐标图、树状图、流线图、桑基图）")
    print("="*80)

    # 加载数据
    print("\n[加载数据]")
    loader, df_schedule = load_data()
    print(f"调度任务数: {len(df_schedule)}")

    # 创建输出目录
    output_dir = Path("结果/图表")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成所有高级图表
    print("\n[生成高级图表]")
    plot_3d_gantt(df_schedule)
    plot_parallel_coordinates(df_schedule)
    plot_treemap(df_schedule)
    plot_streamgraph(df_schedule)
    plot_sankey_diagram(df_schedule)

    print("\n" + "="*80)
    print("问题二高级可视化完成！")
    print("="*80)
    print("\n新增图表:")
    print("  1. 问题二_3D甘特图_论文版.png (600 DPI)")
    print("  2. 问题二_并行坐标图_论文版.png (600 DPI)")
    print("  3. 问题二_树状图_论文版.png (600 DPI)")
    print("  4. 问题二_流线图_论文版.png (600 DPI)")
    print("  5. 问题二_桑基图_论文版.png (600 DPI)")
    print("\n所有图表已保存到: 结果/图表/")


if __name__ == "__main__":
    main()
