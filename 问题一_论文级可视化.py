#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一 - 论文级可视化
使用学术配色方案重新生成高质量图表
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
import sys

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader

# ============================================================================
# 学术配色方案 (paper-color skill)
# ============================================================================

# 使用 fresh-sky 调色板 - 适合无人机类型的分类对比
PALETTE_CATEGORICAL = {
    'A': '#80D0E4',  # 天蓝色 - A型无人机
    'B': '#568BC1',  # 深蓝色 - B型无人机 (主力)
    'C': '#AAD498',  # 草绿色 - C型无人机
    'depot': '#DD9F95',  # 暖橙色 - 调度中心
    'highlight': '#BC9DA8',  # 紫灰色 - 强调色
}

# 使用 terracotta-focus 调色板 - 适合资源利用率的渐进式展示
PALETTE_SEQUENTIAL = {
    'low': '#A6C9C1',      # 浅青 - 低利用率
    'medium': '#EED5BE',   # 米色 - 中等利用率
    'high': '#EBA48F',     # 浅橙 - 高利用率
    'critical': '#CC5536', # 深橙 - 临界/超限
    'context': '#61847D',  # 深青 - 背景色
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

    result_file = Path("结果/问题一_配送方案.xlsx")
    df_results = pd.read_excel(result_file, engine='openpyxl')

    return loader, df_results


def plot_service_area_map_academic(loader, df_results):
    """
    论文级服务区分布图
    - 清晰的图例
    - 学术配色
    - 高分辨率输出
    """
    print("生成论文级服务区分布图...")

    fig, ax = plt.subplots(figsize=(10, 8))

    # 获取调度中心
    depot = loader.get_depot()
    depot_lon = depot['longitude']
    depot_lat = depot['latitude']

    # 绘制调度中心
    ax.scatter(depot_lon, depot_lat,
              c=PALETTE_CATEGORICAL['depot'],
              s=500,
              marker='*',
              edgecolors=COLORS['text_main'],
              linewidths=2.5,
              label='Dispatch Center',
              zorder=10)

    # 按机型分类绘制
    uav_types = sorted(df_results['uav_type'].unique())

    for uav_type in uav_types:
        subset = df_results[df_results['uav_type'] == uav_type]

        lons = []
        lats = []
        for _, row in subset.iterrows():
            area = loader.get_service_area(row['area_id'])
            if area:
                lons.append(area['longitude'])
                lats.append(area['latitude'])

        ax.scatter(lons, lats,
                  c=PALETTE_CATEGORICAL[uav_type],
                  s=200,
                  alpha=0.85,
                  edgecolors=COLORS['outline'],
                  linewidths=1.5,
                  label=f'Type {uav_type} UAV (n={len(subset)})',
                  zorder=5)

    # 绘制连线
    for _, row in df_results.iterrows():
        area = loader.get_service_area(row['area_id'])
        if area:
            ax.plot([depot_lon, area['longitude']],
                   [depot_lat, area['latitude']],
                   color=COLORS['grid'],
                   alpha=0.4,
                   linewidth=1.0,
                   zorder=1,
                   linestyle='--')

    ax.set_xlabel('Longitude (°E)', fontsize=13, fontweight='medium')
    ax.set_ylabel('Latitude (°N)', fontsize=13, fontweight='medium')
    ax.set_title('Service Area Distribution and UAV Type Selection',
                fontsize=15, fontweight='bold', pad=20)
    ax.legend(loc='upper right', fontsize=11, framealpha=0.95,
             edgecolor=COLORS['outline'])
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)

    # 设置刻度
    ax.tick_params(labelsize=11)

    plt.tight_layout()

    output_file = Path("结果/图表/问题一_服务区分布图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级分布图已保存: {output_file}")
    plt.close()


def plot_uav_performance_academic(df_results):
    """
    论文级无人机性能对比图
    - 4子图布局
    - 统一配色
    - 清晰的数值标注
    """
    print("生成论文级性能对比图...")

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle('UAV Performance Comparison',
                fontsize=16, fontweight='bold', y=0.995)

    grouped = df_results.groupby('uav_type')
    uav_types = sorted(df_results['uav_type'].unique())
    colors_list = [PALETTE_CATEGORICAL[t] for t in uav_types]

    # (a) 使用频次
    ax = axes[0, 0]
    counts = df_results['uav_type'].value_counts().sort_index()
    bars = ax.bar(counts.index, counts.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Number of Missions', fontsize=12, fontweight='medium')
    ax.set_title('(a) Mission Frequency by UAV Type',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(counts.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.3,
                f'{int(height)}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (b) 平均载重
    ax = axes[0, 1]
    avg_weight = grouped['total_weight'].mean().sort_index()
    bars = ax.bar(avg_weight.index, avg_weight.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Average Payload (kg)', fontsize=12, fontweight='medium')
    ax.set_title('(b) Average Payload per Mission',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(avg_weight.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1.5,
                f'{height:.1f}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (c) 平均能耗
    ax = axes[1, 0]
    avg_energy = grouped['total_energy'].mean().sort_index()
    bars = ax.bar(avg_energy.index, avg_energy.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Average Energy (kWh)', fontsize=12, fontweight='medium')
    ax.set_title('(c) Average Energy Consumption',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(avg_energy.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{height:.2f}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    # (d) 平均飞行时间
    ax = axes[1, 1]
    avg_time = grouped['flight_time'].mean().sort_index()
    bars = ax.bar(avg_time.index, avg_time.values,
                  color=colors_list,
                  edgecolor=COLORS['outline'],
                  linewidth=1.5,
                  alpha=0.9)
    ax.set_ylabel('Average Flight Time (min)', fontsize=12, fontweight='medium')
    ax.set_title('(d) Average Mission Duration',
                fontsize=13, fontweight='bold', pad=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, max(avg_time.values) * 1.15)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.6,
                f'{height:.1f}',
                ha='center', va='bottom',
                fontsize=11, fontweight='bold',
                color=COLORS['text_main'])

    plt.tight_layout()

    output_file = Path("结果/图表/问题一_性能对比_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级性能对比图已保存: {output_file}")
    plt.close()


def plot_utilization_academic(loader, df_results):
    """
    论文级资源利用率分析图
    - 使用渐进配色突出不同利用率区间
    - 添加统计线和区间标注
    """
    print("生成论文级资源利用率图...")

    # 计算利用率
    weight_utils = []
    volume_utils = []
    energy_utils = []

    for _, row in df_results.iterrows():
        uav = loader.get_uav_type(row['uav_type'])
        if uav:
            weight_util = (row['total_weight'] / uav['max_load_kg']) * 100
            volume_util = (row['total_volume'] / uav['max_volume_m3']) * 100
            energy_util = (row['total_energy'] /
                          (uav['battery_capacity_kwh'] * (1 - uav['battery_reserve_pct']))) * 100

            weight_utils.append(weight_util)
            volume_utils.append(volume_util)
            energy_utils.append(energy_util)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle('Resource Utilization Analysis',
                fontsize=16, fontweight='bold', y=1.00)

    datasets = [
        (weight_utils, 'Weight', '(a) Payload Utilization'),
        (volume_utils, 'Volume', '(b) Volume Utilization'),
        (energy_utils, 'Energy', '(c) Battery Utilization'),
    ]

    for idx, (data, label, title) in enumerate(datasets):
        ax = axes[idx]

        # 根据利用率分配颜色
        colors = []
        for val in data:
            if val < 60:
                colors.append(PALETTE_SEQUENTIAL['low'])
            elif val < 80:
                colors.append(PALETTE_SEQUENTIAL['medium'])
            elif val < 95:
                colors.append(PALETTE_SEQUENTIAL['high'])
            else:
                colors.append(PALETTE_SEQUENTIAL['critical'])

        # 绘制直方图
        n, bins, patches = ax.hist(data, bins=12,
                                   edgecolor=COLORS['outline'],
                                   linewidth=1.2,
                                   alpha=0.85)

        # 为每个bin设置颜色
        for patch, bin_edge in zip(patches, bins):
            bin_center = (bin_edge + bins[list(bins).index(bin_edge) + 1] if list(bins).index(bin_edge) < len(bins)-1 else bin_edge) / 2
            if bin_center < 60:
                patch.set_facecolor(PALETTE_SEQUENTIAL['low'])
            elif bin_center < 80:
                patch.set_facecolor(PALETTE_SEQUENTIAL['medium'])
            elif bin_center < 95:
                patch.set_facecolor(PALETTE_SEQUENTIAL['high'])
            else:
                patch.set_facecolor(PALETTE_SEQUENTIAL['critical'])

        # 添加平均值线
        mean_val = np.mean(data)
        ax.axvline(mean_val, color=COLORS['text_main'],
                  linestyle='--', linewidth=2.5,
                  label=f'Mean: {mean_val:.1f}%',
                  zorder=10)

        # 添加关键阈值线
        if label == 'Energy':
            ax.axvline(95, color=PALETTE_SEQUENTIAL['critical'],
                      linestyle=':', linewidth=2.0,
                      label='95% threshold',
                      alpha=0.7)

        ax.set_xlabel(f'{label} Utilization (%)', fontsize=12, fontweight='medium')
        ax.set_ylabel('Frequency', fontsize=12, fontweight='medium')
        ax.set_title(title, fontsize=13, fontweight='bold', pad=10)
        ax.legend(loc='upper left', fontsize=10, framealpha=0.95)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_xlim(0, max(data) * 1.05)

    plt.tight_layout()

    output_file = Path("结果/图表/问题一_资源利用率_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 论文级资源利用率图已保存: {output_file}")
    plt.close()


def generate_latex_table(df_results):
    """
    生成LaTeX格式的表格（用于论文）
    """
    print("生成LaTeX表格...")

    # 选取前10个服务区作为示例
    df_sample = df_results.head(10).copy()

    latex_lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Delivery Plan for Service Areas (Sample)}",
        "\\label{tab:problem1_solution}",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "Area ID & UAV Type & Cargos & Weight (kg) & Volume (m³) & Energy (kWh) & Time (min) \\\\",
        "\\midrule",
    ]

    for _, row in df_sample.iterrows():
        line = f"{row['area_id']} & {row['uav_type']} & {int(row['num_cargos'])} & " \
               f"{row['total_weight']:.1f} & {row['total_volume']:.3f} & " \
               f"{row['total_energy']:.2f} & {row['flight_time']:.1f} \\\\"
        latex_lines.append(line)

    latex_lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\end{table}",
    ])

    latex_content = '\n'.join(latex_lines)

    output_file = Path("结果/问题一_LaTeX表格.tex")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(latex_content)

    print(f"[OK] LaTeX表格已保存: {output_file}")
    return latex_content


def main():
    print("=" * 80)
    print("问题一 - 论文级可视化生成")
    print("=" * 80)
    print(f"\n使用配色方案:")
    print(f"  - Categorical: fresh-sky (UAV types)")
    print(f"  - Sequential: terracotta-focus (utilization levels)")
    print()

    # 加载数据
    print("[步骤1] 加载数据...")
    loader, df_results = load_data()
    print(f"[OK] 已加载 {len(df_results)} 个服务区的配送方案\n")

    # 生成图表
    print("[步骤2] 生成论文级图表...")
    Path("结果/图表").mkdir(parents=True, exist_ok=True)

    plot_service_area_map_academic(loader, df_results)
    plot_uav_performance_academic(df_results)
    plot_utilization_academic(loader, df_results)

    # 生成LaTeX表格
    print("\n[步骤3] 生成LaTeX表格...")
    generate_latex_table(df_results)

    print("\n" + "=" * 80)
    print("论文级可视化生成完成！")
    print("=" * 80)
    print("\n生成的文件:")
    print("  1. 结果/图表/问题一_服务区分布图_论文版.png (600 DPI)")
    print("  2. 结果/图表/问题一_性能对比_论文版.png (600 DPI)")
    print("  3. 结果/图表/问题一_资源利用率_论文版.png (600 DPI)")
    print("  4. 结果/问题一_LaTeX表格.tex")
    print("\n配色说明:")
    print(f"  - 调度中心: {PALETTE_CATEGORICAL['depot']}")
    print(f"  - B型无人机: {PALETTE_CATEGORICAL['B']} (主力机型)")
    print(f"  - C型无人机: {PALETTE_CATEGORICAL['C']}")
    print(f"  - 低利用率 (<60%): {PALETTE_SEQUENTIAL['low']}")
    print(f"  - 中等利用率 (60-80%): {PALETTE_SEQUENTIAL['medium']}")
    print(f"  - 高利用率 (80-95%): {PALETTE_SEQUENTIAL['high']}")
    print(f"  - 临界/超限 (>95%): {PALETTE_SEQUENTIAL['critical']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
