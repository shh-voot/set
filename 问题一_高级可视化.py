#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一 - 高级可视化（3D点云、山脊图、小提琴图、热力图、雷达图）
使用创新的可视化方法展示多维度分析
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.patches import Circle, RegularPolygon
from matplotlib.path import Path
from matplotlib.projections.polar import PolarAxes
from matplotlib.projections import register_projection
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D
import seaborn as sns
from pathlib import Path as FilePath
import sys

# 添加src到路径
sys.path.insert(0, str(FilePath(__file__).parent / 'src'))
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

# 设置matplotlib全局样式
matplotlib.rcParams['font.sans-serif'] = ['Arial', 'SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.facecolor'] = COLORS['background']
matplotlib.rcParams['axes.facecolor'] = COLORS['background']


def load_data():
    """加载数据和结果"""
    loader = DataLoader()
    loader.load_all()

    result_file = FilePath("结果/问题一_配送方案.xlsx")
    df_results = pd.read_excel(result_file, engine='openpyxl')

    return loader, df_results


def plot_3d_scatter(loader, df_results):
    """
    三维点云图 - 服务区的三维空间分布
    X: 经度, Y: 纬度, Z: 海拔
    点大小: 货物数量, 点颜色: 选用机型
    """
    print("生成3D点云图...")

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')

    # 获取调度中心
    depot = loader.get_depot()

    # 绘制调度中心
    ax.scatter(depot['longitude'], depot['latitude'], depot['altitude'],
              c=PALETTE_CATEGORICAL['depot'],
              s=800,
              marker='*',
              edgecolors=COLORS['outline'],
              linewidths=2.5,
              label='Dispatch Center',
              zorder=10,
              alpha=0.9)

    # 按机型分类绘制服务区
    for uav_type in sorted(df_results['uav_type'].unique()):
        subset = df_results[df_results['uav_type'] == uav_type]

        lons = []
        lats = []
        alts = []
        sizes = []

        for _, row in subset.iterrows():
            area = loader.get_service_area(row['area_id'])
            if area:
                lons.append(area['longitude'])
                lats.append(area['latitude'])
                alts.append(area['altitude'])
                sizes.append(row['num_cargos'] * 100)  # 货物数量映射到点大小

        ax.scatter(lons, lats, alts,
                  c=PALETTE_CATEGORICAL[uav_type],
                  s=sizes,
                  alpha=0.7,
                  edgecolors=COLORS['outline'],
                  linewidths=1.5,
                  label=f'Type {uav_type} UAV',
                  zorder=5)

        # 绘制从调度中心到服务区的连线
        for lon, lat, alt in zip(lons, lats, alts):
            ax.plot([depot['longitude'], lon],
                   [depot['latitude'], lat],
                   [depot['altitude'], alt],
                   color=COLORS['grid'],
                   alpha=0.2,
                   linewidth=0.8,
                   zorder=1)

    ax.set_xlabel('Longitude (°E)', fontsize=12, fontweight='medium', labelpad=10)
    ax.set_ylabel('Latitude (°N)', fontsize=12, fontweight='medium', labelpad=10)
    ax.set_zlabel('Altitude (m)', fontsize=12, fontweight='medium', labelpad=10)
    ax.set_title('3D Service Area Distribution with Terrain\n(Point size ∝ Cargo quantity)',
                fontsize=14, fontweight='bold', pad=20)

    ax.legend(loc='upper left', fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)

    # 设置视角
    ax.view_init(elev=25, azim=45)

    plt.tight_layout()

    output_file = FilePath("结果/图表/问题一_3D点云图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 3D点云图已保存: {output_file}")
    plt.close()


def plot_ridgeline(df_results):
    """
    山脊图 - 不同机型的能耗分布
    每条山脊代表一种机型的能耗分布密度
    """
    print("生成山脊图...")

    uav_types = sorted(df_results['uav_type'].unique())

    # 只显示实际存在的机型
    fig, axes = plt.subplots(len(uav_types), 1, figsize=(12, 6 + 2*len(uav_types)), sharex=True)
    if len(uav_types) == 1:
        axes = [axes]

    fig.suptitle('Energy Consumption Distribution by UAV Type',
                fontsize=15, fontweight='bold', y=0.98)

    for i, (ax, uav_type) in enumerate(zip(axes, uav_types)):
        subset = df_results[df_results['uav_type'] == uav_type]
        energy_data = subset['total_energy'].values

        # 绘制核密度估计（处理单点情况）
        from scipy import stats
        if len(energy_data) > 1:
            density = stats.gaussian_kde(energy_data)
            x_range = np.linspace(energy_data.min() * 0.9, energy_data.max() * 1.1, 200)
            y_density = density(x_range)
        else:
            # 单点情况：用高斯分布模拟
            x_range = np.linspace(energy_data[0] * 0.8, energy_data[0] * 1.2, 200)
            y_density = stats.norm.pdf(x_range, loc=energy_data[0], scale=energy_data[0] * 0.05)

        # 填充山脊
        ax.fill_between(x_range, 0, y_density,
                        color=PALETTE_CATEGORICAL[uav_type],
                        alpha=0.7,
                        edgecolor=COLORS['outline'],
                        linewidth=2)

        # 标注机型
        ax.text(0.02, 0.75, f'Type {uav_type}',
               transform=ax.transAxes,
               fontsize=13,
               fontweight='bold',
               color=COLORS['text_main'],
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white',
                        edgecolor=PALETTE_CATEGORICAL[uav_type],
                        alpha=0.9, linewidth=2))

        # 标注统计量
        mean_energy = energy_data.mean()
        std_energy = energy_data.std()
        ax.axvline(mean_energy, color=PALETTE_CATEGORICAL['highlight'],
                  linestyle='--', linewidth=2, alpha=0.8)
        ax.text(mean_energy, y_density.max() * 0.9,
               f'μ={mean_energy:.2f}',
               fontsize=10,
               ha='center',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

        # 去除上边框和右边框
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.set_yticks([])
        ax.set_ylim(0, y_density.max() * 1.2)

        if i < len(axes) - 1:
            ax.spines['bottom'].set_visible(False)
            ax.tick_params(bottom=False)

    axes[-1].set_xlabel('Energy Consumption (kWh)', fontsize=12, fontweight='medium')
    axes[-1].spines['bottom'].set_edgecolor(COLORS['text_main'])
    axes[-1].tick_params(labelsize=10)

    plt.tight_layout()

    output_file = FilePath("结果/图表/问题一_山脊图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 山脊图已保存: {output_file}")
    plt.close()


def radar_factory(num_vars, frame='circle'):
    """
    创建雷达图的辅助函数
    """
    theta = np.linspace(0, 2 * np.pi, num_vars, endpoint=False)

    class RadarAxes(PolarAxes):
        name = 'radar'

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.set_theta_zero_location('N')

        def fill(self, *args, closed=True, **kwargs):
            return super().fill(closed=closed, *args, **kwargs)

        def plot(self, *args, **kwargs):
            lines = super().plot(*args, **kwargs)
            for line in lines:
                self._close_line(line)

        def _close_line(self, line):
            x, y = line.get_data()
            if x[0] != x[-1]:
                x = np.append(x, x[0])
                y = np.append(y, y[0])
                line.set_data(x, y)

        def set_varlabels(self, labels):
            self.set_thetagrids(np.degrees(theta), labels, fontsize=11, fontweight='medium')

        def _gen_axes_patch(self):
            return Circle((0.5, 0.5), 0.5)

        def _gen_axes_spines(self):
            if frame == 'circle':
                return super()._gen_axes_spines()
            elif frame == 'polygon':
                spine = Spine(axes=self,
                            spine_type='circle',
                            path=Path.unit_regular_polygon(num_vars))
                spine.set_transform(Affine2D().scale(0.5).translate(0.5, 0.5)
                                  + self.transAxes)
                return {'polar': spine}
            else:
                raise ValueError("Unknown value for 'frame': %s" % frame)

    register_projection(RadarAxes)
    return theta


def plot_radar_chart(loader, df_results):
    """
    雷达图 - 三种机型的多维能力对比
    维度: 载重、续航、能效、速度、体积
    """
    print("生成雷达图...")

    # 获取无人机数据
    uav_types = ['A', 'B', 'C']
    categories = ['Max Load\n(kg)', 'Max Range\n(km)', 'Energy Efficiency\n(km/kWh)',
                 'Cruise Speed\n(m/s)', 'Max Volume\n(m³)']

    N = len(categories)
    theta = radar_factory(N, frame='polygon')

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='radar'))
    fig.suptitle('UAV Type Multi-Dimensional Performance Comparison',
                fontsize=15, fontweight='bold', y=0.95)

    # 准备数据并归一化
    data_matrix = []
    for uav_type in uav_types:
        uav = loader.get_uav_type(uav_type)
        if uav:
            data_matrix.append([
                uav['max_load_kg'],
                uav['max_range_km'],
                uav['max_range_km'] / uav['battery_capacity_kwh'],  # 能效
                uav['cruise_speed_ms'],
                uav['max_volume_m3']
            ])

    # 归一化到0-1
    data_matrix = np.array(data_matrix)
    data_normalized = (data_matrix - data_matrix.min(axis=0)) / (data_matrix.max(axis=0) - data_matrix.min(axis=0) + 1e-6)

    # 绘制雷达图
    for i, uav_type in enumerate(uav_types):
        values = data_normalized[i].tolist()
        values += values[:1]  # 闭合多边形

        # 确保theta和values长度匹配
        theta_closed = np.concatenate([theta, [theta[0]]])

        ax.plot(theta_closed, values,
               color=PALETTE_CATEGORICAL[uav_type],
               linewidth=2.5,
               label=f'Type {uav_type}',
               alpha=0.9)
        ax.fill(theta_closed, values,
               color=PALETTE_CATEGORICAL[uav_type],
               alpha=0.25)

    ax.set_varlabels(categories)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=9)
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.8, color=COLORS['grid'])
    ax.legend(loc='upper right', bbox_to_anchor=(1.2, 1.1),
             fontsize=11, framealpha=0.95, edgecolor=COLORS['outline'])

    plt.tight_layout()

    output_file = FilePath("结果/图表/问题一_雷达图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 雷达图已保存: {output_file}")
    plt.close()


def plot_violin(loader, df_results):
    """
    小提琴图 - 资源利用率的分布特征
    展示重量、体积、能耗利用率的分布和密度
    """
    print("生成小提琴图...")

    # 计算利用率
    utilization_data = []
    for _, row in df_results.iterrows():
        uav = loader.get_uav_type(row['uav_type'])
        if uav:
            utilization_data.append({
                'Type': 'Weight\nUtilization',
                'Utilization (%)': (row['total_weight'] / uav['max_load_kg']) * 100,
                'UAV Type': row['uav_type']
            })
            utilization_data.append({
                'Type': 'Volume\nUtilization',
                'Utilization (%)': (row['total_volume'] / uav['max_volume_m3']) * 100,
                'UAV Type': row['uav_type']
            })
            # 计算能耗利用率（相对于满载理论值）
            max_distance = np.sqrt(
                (row['distance'] ** 2) if 'distance' in row else 0
            )
            theoretical_energy = (max_distance / 1000) * uav['cruise_power_kw'] / uav['cruise_speed_ms'] * 3600
            if theoretical_energy > 0:
                utilization_data.append({
                    'Type': 'Energy\nUtilization',
                    'Utilization (%)': (row['total_energy'] / uav['battery_capacity_kwh']) * 100,
                    'UAV Type': row['uav_type']
                })

    df_util = pd.DataFrame(utilization_data)

    fig, ax = plt.subplots(figsize=(12, 8))

    # 绘制小提琴图
    parts = ax.violinplot(
        [df_util[df_util['Type'] == t]['Utilization (%)'].values
         for t in df_util['Type'].unique()],
        positions=range(len(df_util['Type'].unique())),
        widths=0.7,
        showmeans=True,
        showmedians=True,
        showextrema=True
    )

    # 设置颜色
    colors = [PALETTE_SEQUENTIAL['medium'], PALETTE_SEQUENTIAL['high'], PALETTE_SEQUENTIAL['critical']]
    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(colors[i % len(colors)])
        pc.set_edgecolor(COLORS['outline'])
        pc.set_alpha(0.7)
        pc.set_linewidth(1.5)

    # 配置样式
    for partname in ('cbars', 'cmins', 'cmaxes', 'cmedians', 'cmeans'):
        if partname in parts:
            parts[partname].set_edgecolor(COLORS['text_main'])
            parts[partname].set_linewidth(2)

    ax.set_xticks(range(len(df_util['Type'].unique())))
    ax.set_xticklabels(df_util['Type'].unique(), fontsize=12, fontweight='medium')
    ax.set_ylabel('Utilization Rate (%)', fontsize=13, fontweight='medium')
    ax.set_title('Resource Utilization Distribution - Violin Plot\n(Width ∝ Probability density)',
                fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3, linestyle='--', linewidth=0.8)
    ax.set_ylim(0, 100)

    # 添加参考线
    ax.axhline(y=80, color=PALETTE_SEQUENTIAL['critical'],
              linestyle='--', linewidth=2, alpha=0.6, label='80% Threshold')
    ax.legend(fontsize=10, framealpha=0.95, edgecolor=COLORS['outline'])

    plt.tight_layout()

    output_file = FilePath("结果/图表/问题一_小提琴图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 小提琴图已保存: {output_file}")
    plt.close()


def plot_heatmap(loader, df_results):
    """
    热力图 - 服务区×机型适配矩阵
    展示每个服务区选择各机型的适配度评分
    """
    print("生成热力图...")

    # 构建适配矩阵
    service_areas = df_results['area_id'].unique()
    uav_types = ['A', 'B', 'C']

    # 适配度矩阵（基于重量、体积、能耗的综合评分）
    matrix = np.zeros((len(service_areas), len(uav_types)))

    for i, area_id in enumerate(service_areas):
        area_row = df_results[df_results['area_id'] == area_id].iloc[0]
        selected_type = area_row['uav_type']

        for j, uav_type in enumerate(uav_types):
            uav = loader.get_uav_type(uav_type)
            if uav:
                # 计算适配度得分（0-100）
                weight_fit = min(100, (area_row['total_weight'] / uav['max_load_kg']) * 100)
                volume_fit = min(100, (area_row['total_volume'] / uav['max_volume_m3']) * 100)

                # 能耗效率（越低越好，转换为得分）
                energy_efficiency = uav['max_range_km'] / uav['battery_capacity_kwh']
                energy_score = energy_efficiency * 10  # 归一化

                # 综合得分
                fitness = (weight_fit + volume_fit + energy_score) / 3

                # 如果是选中的机型，加权
                if uav_type == selected_type:
                    fitness = 100

                matrix[i, j] = fitness

    # 绘制热力图
    fig, ax = plt.subplots(figsize=(10, 12))

    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0, vmax=100)

    # 设置刻度
    ax.set_xticks(np.arange(len(uav_types)))
    ax.set_yticks(np.arange(len(service_areas)))
    ax.set_xticklabels([f'Type {t}' for t in uav_types], fontsize=11, fontweight='medium')
    ax.set_yticklabels(service_areas, fontsize=10)

    # 标注数值
    for i in range(len(service_areas)):
        for j in range(len(uav_types)):
            text = ax.text(j, i, f'{matrix[i, j]:.0f}',
                         ha="center", va="center",
                         color="white" if matrix[i, j] > 50 else COLORS['text_main'],
                         fontsize=9, fontweight='bold')

    ax.set_title('Service Area × UAV Type Fitness Matrix\n(Score: 0-100, 100 = Selected)',
                fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('UAV Type', fontsize=12, fontweight='medium')
    ax.set_ylabel('Service Area ID', fontsize=12, fontweight='medium')

    # 添加颜色条
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Fitness Score', rotation=270, labelpad=20,
                   fontsize=11, fontweight='medium')
    cbar.ax.tick_params(labelsize=10)

    plt.tight_layout()

    output_file = FilePath("结果/图表/问题一_热力图_论文版.png")
    plt.savefig(output_file, dpi=600, bbox_inches='tight', facecolor='white')
    print(f"[OK] 热力图已保存: {output_file}")
    plt.close()


def main():
    """主函数"""
    print("="*80)
    print("问题一 - 高级可视化（3D点云、山脊图、雷达图、小提琴图、热力图）")
    print("="*80)

    # 加载数据
    print("\n[加载数据]")
    loader, df_results = load_data()
    print(f"配送方案数: {len(df_results)}")

    # 创建输出目录
    output_dir = FilePath("结果/图表")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 生成所有高级图表
    print("\n[生成高级图表]")
    plot_3d_scatter(loader, df_results)
    plot_ridgeline(df_results)
    plot_radar_chart(loader, df_results)
    plot_violin(loader, df_results)
    plot_heatmap(loader, df_results)

    print("\n" + "="*80)
    print("问题一高级可视化完成！")
    print("="*80)
    print("\n新增图表:")
    print("  1. 问题一_3D点云图_论文版.png (600 DPI)")
    print("  2. 问题一_山脊图_论文版.png (600 DPI)")
    print("  3. 问题一_雷达图_论文版.png (600 DPI)")
    print("  4. 问题一_小提琴图_论文版.png (600 DPI)")
    print("  5. 问题一_热力图_论文版.png (600 DPI)")
    print("\n所有图表已保存到: 结果/图表/")


if __name__ == "__main__":
    main()
