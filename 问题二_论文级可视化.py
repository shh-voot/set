#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题二 - 论文级可视化
基于VeRoViz最佳实践的甘特图和多维度分析
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib
from pathlib import Path
from datetime import datetime, timedelta
import sys

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader

# ============================================================================
# 学术配色方案 (与问题一一致)
# ============================================================================

# 使用 fresh-sky 调色板
PALETTE_CATEGORICAL = {
    'A': '#80D0E4',  # 天蓝色
    'B': '#568BC1',  # 深蓝色 (主力)
    'C': '#AAD498',  # 草绿色
    'depot': '#DD9F95',  # 暖橙色
    'highlight': '#BC9DA8',  # 紫灰色
}

# 使用 terracotta-focus 调色板 - 资源状态
PALETTE_STATUS = {
    'flying': '#568BC1',      # 深蓝 - 飞行中
    'charging': '#EBA48F',    # 浅橙 - 充电中
    'preparing': '#EED5BE',   # 米色 - 准备中
    'idle': '#A6C9C1',        # 浅青 - 空闲
    'service': '#61847D',     # 深青 - 服务中
}

# 渐进式调色板（用于对比）
PALETTE_SEQUENTIAL = {
    'low': '#A6C9C1',      # 浅青 - 低
    'medium': '#EED5BE',   # 米色 - 中
    'high': '#EBA48F',     # 浅橙 - 高
    'critical': '#CC5536', # 深橙 - 临界
    'context': '#61847D',  # 深青 - 背景
}

# 通用常量
COLORS = {
    'background': '#FFFFFF',
    'text_main': '#2B2B2B',
    'text_secondary': '#666666',
    'grid': '#E6E6E6',
    'outline': '#4A4A4A',
}

# 设置matplotlib全局样式
matplotlib.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.facecolor'] = COLORS['background']
matplotlib.rcParams['axes.facecolor'] = COLORS['background']
matplotlib.rcParams['axes.edgecolor'] = COLORS['text_main']
matplotlib.rcParams['axes.labelcolor'] = COLORS['text_main']
matplotlib.rcParams['xtick.color'] = COLORS['text_main']
matplotlib.rcParams['ytick.color'] = COLORS['text_main']
matplotlib.rcParams['text.color'] = COLORS['text_main']
matplotlib.rcParams['grid.color'] = COLORS['grid']
matplotlib.rcParams['grid.alpha'] = 0.3


def load_data():
    """加载数据和结果"""
    loader = DataLoader()
    loader.load_all()

    # 加载问题二结果
    result_file = Path("结果/问题二_调度方案.xlsx")
    if not result_file.exists():
        raise FileNotFoundError(f"请先运行问题二求解器: {result_file}")

    df_schedule = pd.read_excel(result_file, engine='openpyxl')

    return loader, df_schedule


def plot_gantt_chart_academic(df_schedule):
    """
    论文级甘特图
    基于VeRoViz和Operations Research最佳实践

    显示:
    - 每架无人机的时间轴
    - 飞行、充电、准备状态
    - 服务区标注
    - 时间窗口指示
    """
    print("生成论文级甘特图...")

    # 创建图表
    fig, ax = plt.subplots(figsize=(16, 8))

    # 获取所有无人机
    uav_ids = df_schedule['无人机ID'].unique()
    n_uavs = len(uav_ids)

    # Y轴位置
    y_positions = {uav_id: i for i, uav_id in enumerate(uav_ids)}

    # 绘制每个任务
    for _, row in df_schedule.iterrows():
        uav_id = row['无人机ID']
        y_pos = y_positions[uav_id]

        start_time = row['开始时间(分钟)']
        end_time = row['结束时间(分钟)']
        duration = end_time - start_time

        # 机型颜色
        uav_type = row['机型']
        color = PALETTE_CATEGORICAL.get(uav_type, PALETTE_STATUS['flying'])

        # 绘制飞行段
        rect = mpatches.Rectangle(
            (start_time, y_pos - 0.35),
            duration,
            0.7,
            facecolor=color,
            edgecolor=COLORS['outline'],
            linewidth=1.5,
            alpha=0.85,
            zorder=3
        )
        ax.add_patch(rect)

        # 标注服务区
        service_area = row['服务区']
        ax.text(
            start_time + duration/2,
            y_pos,
            service_area,
            ha='center',
            va='center',
            fontsize=9,
            fontweight='bold',
            color='white',
            zorder=4
        )

    # 绘制充电段（如果有）
    prev_end = {}
    for uav_id in uav_ids:
        prev_end[uav_id] = 0

    for _, row in df_schedule.iterrows():
        if row['是否充电'] == '是':
            uav_id = row['无人机ID']
            y_pos = y_positions[uav_id]

            # 充电开始时间 = 上一任务结束时间
            if uav_id in prev_end and prev_end[uav_id] > 0:
                charge_start = prev_end[uav_id]
                charge_duration = 30  # 充电时间

                # 绘制充电段
                rect = mpatches.Rectangle(
                    (charge_start, y_pos - 0.35),
                    charge_duration,
                    0.7,
                    facecolor=PALETTE_STATUS['charging'],
                    edgecolor=COLORS['outline'],
                    linewidth=1.5,
                    alpha=0.7,
                    hatch='///',
                    zorder=2
                )
                ax.add_patch(rect)

                # 标注"充电"
                ax.text(
                    charge_start + charge_duration/2,
                    y_pos,
                    'Charging',
                    ha='center',
                    va='center',
                    fontsize=8,
                    style='italic',
                    color=COLORS['text_main'],
                    zorder=4
                )

        prev_end[row['无人机ID']] = row['结束时间(分钟)']

    # 设置坐标轴
    ax.set_yticks(range(n_uavs))
    ax.set_yticklabels(uav_ids, fontsize=11)
    ax.set_xlabel('Time (minutes)', fontsize=13, fontweight='medium')
    ax.set_ylabel('UAV ID', fontsize=13, fontweight='medium')
    ax.set_title('Multi-Trip UAV Scheduling - Gantt Chart',
                fontsize=15, fontweight='bold', pad=20)

    # X轴范围
    max_time = df_schedule['结束时间(分钟)'].max()
    ax.set_xlim(0, max_time * 1.05)
    ax.set_ylim(-0.5, n_uavs - 0.5)

    # 网格
    ax.grid(axis='x', alpha=0.3, linestyle='--', linewidth=0.8)
    ax.set_axisbelow(True)

    # 图例
    legend_elements = [
        mpatches.Patch(facecolor=PALETTE_CATEGORICAL['B'],
                      edgecolor=COLORS['outline'], linewidth=1.5,
                      label='Type B UAV - Flying'),
        mpatches.Patch(facecolor=PALETTE_CATEGORICAL['C'],
                      edgecolor=COLORS['outline'], linewidth=1.5,
                      label='Type C UAV - Flying'),
        mpatches.Patch(facecolor=PALETTE_STATUS['charging'],
                      edgecolor=COLORS['outline'], linewidth=1.5,
                      hatch='///', label='Battery Charging'),
    ]
    ax.legend(handles=legend_elements, loc='upper right',
             fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_甘特图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级甘特图已保存: {output_file}")
    plt.close()


def plot_uav_utilization_academic(df_schedule):
    """
    论文级无人机利用率分析
    - 工作时间分解
    - 利用率对比
    - 能耗分析
    """
    print("生成论文级利用率分析图...")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('UAV Fleet Utilization Analysis',
                fontsize=16, fontweight='bold', y=0.995)

    # 按无人机分组
    grouped = df_schedule.groupby('无人机ID')

    # (a) 任务数分布
    ax = axes[0, 0]
    mission_counts = grouped.size().sort_index()
    uav_types = df_schedule.groupby('无人机ID')['机型'].first()
    colors_list = [PALETTE_CATEGORICAL[uav_types[uav_id]]
                   for uav_id in mission_counts.index]

    bars = ax.bar(mission_counts.index, mission_counts.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Number of Missions', fontsize=12, fontweight='medium')
    ax.set_xlabel('UAV ID', fontsize=12, fontweight='medium')
    ax.set_title('(a) Mission Count per UAV',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(mission_counts.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (b) 总飞行时间
    ax = axes[0, 1]
    flight_times = grouped['飞行时长(分钟)'].sum().sort_index()

    bars = ax.bar(flight_times.index, flight_times.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Total Flight Time (min)', fontsize=12, fontweight='medium')
    ax.set_xlabel('UAV ID', fontsize=12, fontweight='medium')
    ax.set_title('(b) Total Flight Time per UAV',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(flight_times.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 3,
                f'{height:.1f}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (c) 总能耗
    ax = axes[1, 0]
    energy_totals = grouped['能耗(kWh)'].sum().sort_index()

    bars = ax.bar(energy_totals.index, energy_totals.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Total Energy Consumption (kWh)', fontsize=12, fontweight='medium')
    ax.set_xlabel('UAV ID', fontsize=12, fontweight='medium')
    ax.set_title('(c) Energy Consumption per UAV',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(energy_totals.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.3,
                f'{height:.2f}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (d) 利用率（飞行时间 / 总完成时间）
    ax = axes[1, 1]
    max_completion = df_schedule['结束时间(分钟)'].max()
    utilization = (flight_times / max_completion * 100).sort_index()

    bars = ax.bar(utilization.index, utilization.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Utilization Rate (%)', fontsize=12, fontweight='medium')
    ax.set_xlabel('UAV ID', fontsize=12, fontweight='medium')
    ax.set_title('(d) UAV Utilization Rate',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, 100)

    # 添加平均线
    avg_util = utilization.mean()
    ax.axhline(y=avg_util, color=PALETTE_CATEGORICAL['highlight'],
              linestyle='--', linewidth=2, label=f'Average: {avg_util:.1f}%')

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{height:.1f}%',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    ax.legend(fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_利用率分析_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级利用率分析图已保存: {output_file}")
    plt.close()


def plot_time_comparison_academic(df_schedule):
    """
    问题一vs问题二时间对比
    """
    print("生成问题对比图...")

    fig, ax = plt.subplots(figsize=(10, 6))

    # 数据
    problem1_time = df_schedule['飞行时长(分钟)'].sum()
    problem2_time = df_schedule['结束时间(分钟)'].max()

    categories = ['Problem 1\n(Sequential)', 'Problem 2\n(Parallel)']
    times = [problem1_time, problem2_time]
    colors = [PALETTE_SEQUENTIAL['medium'], PALETTE_CATEGORICAL['B']]

    bars = ax.bar(categories, times,
                  color=colors,
                  edgecolor=COLORS['outline'],
                  linewidth=2.0,
                  alpha=0.9,
                  width=0.6)

    # 标注数值
    for i, (bar, time) in enumerate(zip(bars, times)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 10,
                f'{time:.1f} min\n({time/60:.2f} hrs)',
                ha='center', va='bottom',
                fontsize=12, fontweight='bold',
                color=COLORS['text_main'])

    # 标注改进
    improvement = (problem1_time - problem2_time) / problem1_time * 100
    ax.annotate('',
                xy=(1, problem2_time), xytext=(1, problem1_time),
                arrowprops=dict(arrowstyle='<->', color=PALETTE_CATEGORICAL['highlight'],
                              lw=2, shrinkA=5, shrinkB=5))
    ax.text(1.15, (problem1_time + problem2_time) / 2,
            f'Time Saved:\n{improvement:.1f}%',
            fontsize=11, fontweight='bold',
            color=PALETTE_CATEGORICAL['highlight'],
            va='center')

    ax.set_ylabel('Completion Time (minutes)', fontsize=13, fontweight='medium')
    ax.set_title('Problem 1 vs Problem 2 - Completion Time Comparison',
                fontsize=15, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.8)
    ax.set_ylim(0, problem1_time * 1.2)

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_时间对比_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级对比图已保存: {output_file}")
    plt.close()


def plot_charging_analysis_academic(df_schedule):
    """
    充电行为分析
    """
    print("生成充电分析图...")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('Battery Charging Analysis',
                fontsize=16, fontweight='bold', y=0.995)

    # (a) 充电次数统计
    ax = axes[0]
    charging_stats = df_schedule.groupby('无人机ID')['是否充电'].apply(
        lambda x: (x == '是').sum()
    ).sort_index()

    uav_types = df_schedule.groupby('无人机ID')['机型'].first()
    colors_list = [PALETTE_CATEGORICAL[uav_types[uav_id]]
                   for uav_id in charging_stats.index]

    bars = ax.bar(charging_stats.index, charging_stats.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Number of Charging Events', fontsize=12, fontweight='medium')
    ax.set_xlabel('UAV ID', fontsize=12, fontweight='medium')
    ax.set_title('(a) Charging Frequency per UAV',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{int(height)}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (b) 充电率（充电任务 / 总任务）
    ax = axes[1]
    total_missions = df_schedule.groupby('无人机ID').size()
    charging_rate = (charging_stats / total_missions * 100).sort_index()

    bars = ax.bar(charging_rate.index, charging_rate.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Charging Rate (%)', fontsize=12, fontweight='medium')
    ax.set_xlabel('UAV ID', fontsize=12, fontweight='medium')
    ax.set_title('(b) Charging Rate per UAV',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, 100)

    # 平均线
    avg_rate = charging_rate.mean()
    ax.axhline(y=avg_rate, color=PALETTE_CATEGORICAL['highlight'],
              linestyle='--', linewidth=2, label=f'Average: {avg_rate:.1f}%')

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{height:.1f}%',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    ax.legend(fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])

    plt.tight_layout()

    output_file = Path("结果/图表/问题二_充电分析_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级充电分析图已保存: {output_file}")
    plt.close()


def main():
    """主函数"""
    print("="*80)
    print("问题二 - 论文级可视化")
    print("="*80)

    # 加载数据
    print("\n[加载数据]")
    loader, df_schedule = load_data()
    print(f"调度任务数: {len(df_schedule)}")

    # 创建输出目录
    output_dir = Path("结果/图表")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成所有图表
    print("\n[生成图表]")
    plot_gantt_chart_academic(df_schedule)
    plot_uav_utilization_academic(df_schedule)
    plot_time_comparison_academic(df_schedule)
    plot_charging_analysis_academic(df_schedule)

    print("\n" + "="*80)
    print("问题二论文级可视化完成！")
    print("="*80)
    print("\n生成的图表:")
    print("  1. 问题二_甘特图_论文版.png (600 DPI)")
    print("  2. 问题二_利用率分析_论文版.png (600 DPI)")
    print("  3. 问题二_时间对比_论文版.png (600 DPI)")
    print("  4. 问题二_充电分析_论文版.png (600 DPI)")
    print("\n所有图表已保存到: 结果/图表/")


if __name__ == "__main__":
    main()
