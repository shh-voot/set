#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一增强版 - 详细分析与可视化（简化版）
仅读取已有结果，生成可视化图表和详细报告
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
import sys

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader


def load_solution_results():
    """加载问题一的求解结果"""
    result_file = Path("结果/问题一_配送方案.xlsx")
    if not result_file.exists():
        raise FileNotFoundError(f"未找到结果文件: {result_file}")

    df = pd.read_excel(result_file, engine='openpyxl')
    print(f"已加载 {len(df)} 个服务区的配送方案")
    return df


def generate_cargo_summary(loader, df_results):
    """
    生成货物汇总信息（不重新求解，只统计）
    """
    print("生成货物汇总信息...")

    summary_data = []
    for idx, row in df_results.iterrows():
        area_id = row['area_id']
        num_cargos = int(row['num_cargos'])

        summary_data.append({
            '服务区ID': area_id,
            '服务区名称': row['area_name'],
            '货物数量': num_cargos,
            '总重量(kg)': row['total_weight'],
            '总体积(m3)': row['total_volume'],
            '选用机型': row['uav_type'],
            '总能耗(kWh)': row['total_energy'],
            '飞行时间(分钟)': row['flight_time']
        })

    df_summary = pd.DataFrame(summary_data)

    # 保存
    output_file = Path("结果/问题一_货物汇总.xlsx")
    df_summary.to_excel(output_file, index=False, engine='openpyxl')
    print(f"货物汇总已保存: {output_file}")

    return df_summary


def plot_service_area_map(loader, df_results):
    """
    绘制服务区分布地图，标注选用的无人机类型
    """
    print("绘制服务区分布图...")

    # 创建图表
    fig, ax = plt.subplots(figsize=(14, 10))

    # 获取调度中心坐标
    depot = loader.get_depot()
    depot_lon = depot['longitude']
    depot_lat = depot['latitude']

    # 绘制调度中心
    ax.scatter(depot_lon, depot_lat, c='red', s=300, marker='*',
               edgecolors='black', linewidths=2, label='调度中心', zorder=5)
    ax.text(depot_lon, depot_lat + 0.002, depot['name'],
            fontsize=11, ha='center', weight='bold')

    # 按机型分类绘制服务区
    colors = {'A': '#FF6B6B', 'B': '#4ECDC4', 'C': '#45B7D1'}
    uav_types = df_results['uav_type'].unique()

    for uav_type in sorted(uav_types):
        subset = df_results[df_results['uav_type'] == uav_type]

        lons = []
        lats = []
        for _, row in subset.iterrows():
            area = loader.get_service_area(row['area_id'])
            if area:
                lons.append(area['longitude'])
                lats.append(area['latitude'])

        ax.scatter(lons, lats, c=colors.get(uav_type, 'gray'), s=150,
                   alpha=0.7, edgecolors='black', linewidths=1,
                   label=f'{uav_type}型无人机 ({len(subset)}个)', zorder=3)

    # 绘制连线（调度中心到服务区）
    for _, row in df_results.iterrows():
        area = loader.get_service_area(row['area_id'])
        if area:
            ax.plot([depot_lon, area['longitude']],
                   [depot_lat, area['latitude']],
                   'gray', alpha=0.2, linewidth=0.8, zorder=1)

    ax.set_xlabel('经度', fontsize=12)
    ax.set_ylabel('纬度', fontsize=12)
    ax.set_title('问题一 - 服务区分布与无人机选型', fontsize=14, weight='bold', pad=15)
    ax.legend(loc='upper right', fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.3, linestyle='--')

    # 保存
    Path("结果/图表").mkdir(parents=True, exist_ok=True)
    output_file = Path("结果/图表/问题一_服务区分布图.png")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"服务区分布图已保存: {output_file}")
    plt.close()


def plot_uav_comparison(df_results):
    """
    绘制无人机性能对比图
    """
    print("绘制无人机性能对比图...")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('问题一 - 不同机型性能对比', fontsize=14, weight='bold')

    colors = {'A': '#FF6B6B', 'B': '#4ECDC4', 'C': '#45B7D1'}

    # 按机型分组统计
    grouped = df_results.groupby('uav_type')

    # 1. 使用频次
    ax = axes[0, 0]
    counts = df_results['uav_type'].value_counts().sort_index()
    bars = ax.bar(counts.index, counts.values,
                  color=[colors.get(t, 'gray') for t in counts.index],
                  edgecolor='black', linewidth=1.5, alpha=0.8)
    ax.set_ylabel('使用次数', fontsize=11)
    ax.set_title('(a) 各机型使用频次', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)

    # 添加数值标签
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=10, weight='bold')

    # 2. 平均载重
    ax = axes[0, 1]
    avg_weight = grouped['total_weight'].mean().sort_index()
    bars = ax.bar(avg_weight.index, avg_weight.values,
                  color=[colors.get(t, 'gray') for t in avg_weight.index],
                  edgecolor='black', linewidth=1.5, alpha=0.8)
    ax.set_ylabel('平均载重 (kg)', fontsize=11)
    ax.set_title('(b) 各机型平均载重', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, weight='bold')

    # 3. 平均能耗
    ax = axes[1, 0]
    avg_energy = grouped['total_energy'].mean().sort_index()
    bars = ax.bar(avg_energy.index, avg_energy.values,
                  color=[colors.get(t, 'gray') for t in avg_energy.index],
                  edgecolor='black', linewidth=1.5, alpha=0.8)
    ax.set_ylabel('平均能耗 (kWh)', fontsize=11)
    ax.set_title('(c) 各机型平均能耗', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}',
                ha='center', va='bottom', fontsize=10, weight='bold')

    # 4. 平均飞行时间
    ax = axes[1, 1]
    avg_time = grouped['flight_time'].mean().sort_index()
    bars = ax.bar(avg_time.index, avg_time.values,
                  color=[colors.get(t, 'gray') for t in avg_time.index],
                  edgecolor='black', linewidth=1.5, alpha=0.8)
    ax.set_ylabel('平均飞行时间 (分钟)', fontsize=11)
    ax.set_title('(d) 各机型平均飞行时间', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}',
                ha='center', va='bottom', fontsize=10, weight='bold')

    plt.tight_layout()

    output_file = Path("结果/图表/问题一_无人机性能对比.png")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"无人机性能对比图已保存: {output_file}")
    plt.close()


def plot_resource_utilization(loader, df_results):
    """
    绘制资源利用率分析图
    """
    print("绘制资源利用率分析图...")

    # 计算利用率（需要获取无人机参数）
    weight_utils = []
    volume_utils = []
    energy_utils = []

    for _, row in df_results.iterrows():
        uav_type = row['uav_type']
        uav = loader.get_uav_type(uav_type)

        if uav:
            # 重量利用率
            weight_util = (row['total_weight'] / uav['max_load_kg']) * 100
            weight_utils.append(weight_util)

            # 体积利用率
            volume_util = (row['total_volume'] / uav['max_volume_m3']) * 100
            volume_utils.append(volume_util)

            # 能耗利用率（使用可用电池容量）
            available_energy = uav['battery_capacity_kwh'] * (1 - uav['battery_reserve_pct'])
            energy_util = (row['total_energy'] / available_energy) * 100
            energy_utils.append(energy_util)

    weight_utils = np.array(weight_utils)
    volume_utils = np.array(volume_utils)
    energy_utils = np.array(energy_utils)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # 1. 重量利用率分布
    ax = axes[0]
    ax.hist(weight_utils, bins=10, color='skyblue', edgecolor='black', alpha=0.7)
    ax.axvline(weight_utils.mean(), color='red', linestyle='--',
               linewidth=2, label=f'平均值: {weight_utils.mean():.1f}%')
    ax.set_xlabel('重量利用率 (%)', fontsize=11)
    ax.set_ylabel('服务区数量', fontsize=11)
    ax.set_title('(a) 重量利用率分布', fontsize=12, weight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # 2. 体积利用率分布
    ax = axes[1]
    ax.hist(volume_utils, bins=10, color='lightgreen', edgecolor='black', alpha=0.7)
    ax.axvline(volume_utils.mean(), color='red', linestyle='--',
               linewidth=2, label=f'平均值: {volume_utils.mean():.1f}%')
    ax.set_xlabel('体积利用率 (%)', fontsize=11)
    ax.set_ylabel('服务区数量', fontsize=11)
    ax.set_title('(b) 体积利用率分布', fontsize=12, weight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # 3. 能耗利用率分布
    ax = axes[2]
    ax.hist(energy_utils, bins=10, color='orange', edgecolor='black', alpha=0.7)
    ax.axvline(energy_utils.mean(), color='red', linestyle='--',
               linewidth=2, label=f'平均值: {energy_utils.mean():.1f}%')
    ax.set_xlabel('能耗利用率 (%)', fontsize=11)
    ax.set_ylabel('服务区数量', fontsize=11)
    ax.set_title('(c) 能耗利用率分布', fontsize=12, weight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    plt.suptitle('问题一 - 资源利用率分析', fontsize=14, weight='bold', y=1.02)
    plt.tight_layout()

    output_file = Path("结果/图表/问题一_资源利用率.png")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"资源利用率图已保存: {output_file}")
    plt.close()

    return weight_utils, volume_utils, energy_utils


def generate_summary_report(loader, df_results, weight_utils, volume_utils, energy_utils):
    """
    生成问题一汇总报告
    """
    print("\n生成汇总报告...")

    report = []
    report.append("="*80)
    report.append("问题一 - 单架次配送方案 - 完整报告")
    report.append("="*80)
    report.append("")

    # 1. 总体统计
    report.append("一、总体统计")
    report.append("-" * 80)
    report.append(f"服务区总数: {len(df_results)}")
    report.append(f"配送货物总数: {df_results['num_cargos'].sum():.0f} 件")
    report.append(f"总载重: {df_results['total_weight'].sum():.2f} kg")
    report.append(f"总体积: {df_results['total_volume'].sum():.4f} m³")
    report.append(f"总能耗: {df_results['total_energy'].sum():.2f} kWh")
    total_time_min = df_results['flight_time'].sum()
    report.append(f"总飞行时间: {total_time_min:.1f} 分钟 ({total_time_min/60:.2f} 小时)")
    report.append("")

    # 2. 机型使用统计
    report.append("二、机型使用统计")
    report.append("-" * 80)
    uav_counts = df_results['uav_type'].value_counts()
    for uav_type in ['A', 'B', 'C']:
        if uav_type in uav_counts.index:
            count = uav_counts[uav_type]
            pct = count / len(df_results) * 100
            report.append(f"{uav_type}型无人机: {count} 次 ({pct:.1f}%)")
    report.append("")

    # 3. 资源利用率统计
    report.append("三、资源利用率统计")
    report.append("-" * 80)
    report.append(f"平均重量利用率: {weight_utils.mean():.1f}%")
    report.append(f"平均体积利用率: {volume_utils.mean():.1f}%")
    report.append(f"平均能耗利用率: {energy_utils.mean():.1f}%")
    report.append("")

    # 4. 详细服务区列表
    report.append("四、详细服务区配送方案")
    report.append("-" * 80)
    for idx, row in df_results.iterrows():
        area_id = row['area_id']
        area_name = row['area_name']
        uav_type = row['uav_type']
        num_cargos = int(row['num_cargos'])

        report.append(f"\n[{area_id}] {area_name}")
        report.append(f"  选用机型: {uav_type}型")
        report.append(f"  货物数量: {num_cargos} 件")
        report.append(f"  总重量: {row['total_weight']:.2f} kg (利用率: {weight_utils[idx]:.1f}%)")
        report.append(f"  总体积: {row['total_volume']:.4f} m³ (利用率: {volume_utils[idx]:.1f}%)")
        report.append(f"  总能耗: {row['total_energy']:.2f} kWh (利用率: {energy_utils[idx]:.1f}%)")
        report.append(f"  飞行时间: {row['flight_time']:.1f} 分钟")

    report.append("")
    report.append("="*80)
    report.append("报告生成完毕")
    report.append("="*80)

    # 保存报告
    output_file = Path("结果/问题一_完整报告.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    print(f"\n完整报告已保存: {output_file}")

    # 打印摘要到控制台（避免编码问题）
    try:
        print("\n" + '\n'.join(report[:30]))  # 只打印前30行
    except UnicodeEncodeError:
        print("\n[报告摘要无法在控制台显示，请查看文件]")


def main():
    """主函数"""
    print("="*80)
    print("问题一增强 - 详细分析与可视化（简化版）")
    print("="*80)

    # 1. 加载数据
    print("\n[步骤1] 加载数据...")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 2. 加载求解结果
    print("\n[步骤2] 加载问题一求解结果...")
    df_results = load_solution_results()

    # 3. 生成货物汇总
    print("\n[步骤3] 生成货物汇总...")
    generate_cargo_summary(loader, df_results)

    # 4. 绘制可视化图表
    print("\n[步骤4] 生成可视化图表...")
    plot_service_area_map(loader, df_results)
    plot_uav_comparison(df_results)
    weight_utils, volume_utils, energy_utils = plot_resource_utilization(loader, df_results)

    # 5. 生成汇总报告
    print("\n[步骤5] 生成汇总报告...")
    generate_summary_report(loader, df_results, weight_utils, volume_utils, energy_utils)

    print("\n" + "="*80)
    print("问题一增强完成！")
    print("="*80)
    print("\n生成的文件:")
    print("  1. 结果/问题一_货物汇总.xlsx - 货物汇总信息")
    print("  2. 结果/图表/问题一_服务区分布图.png - 地理分布可视化")
    print("  3. 结果/图表/问题一_无人机性能对比.png - 机型对比分析")
    print("  4. 结果/图表/问题一_资源利用率.png - 利用率分析")
    print("  5. 结果/问题一_完整报告.txt - 详细文字报告")
    print("="*80)


if __name__ == "__main__":
    main()
