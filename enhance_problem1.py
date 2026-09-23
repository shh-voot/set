#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题一增强 - 添加详细输出和可视化
1. 详细货物清单（每个服务区选了哪些货箱）
2. 可视化地图（路径、服务区分布）
3. 论文图表（能耗对比、载重利用率等）
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import sys

# 添加src到路径
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from src.data.data_loader import DataLoader

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150


def load_solution_results():
    """加载问题一的求解结果"""
    result_file = Path("结果/问题一_配送方案.xlsx")
    if not result_file.exists():
        print("错误: 找不到问题一的结果文件，请先运行 main_problem1.py")
        sys.exit(1)

    df = pd.read_excel(result_file)
    return df


def generate_detailed_cargo_list(loader, df_results):
    """
    为每个服务区生成详细的货物清单
    重新运行背包算法，记录选中的货箱ID
    """
    print("\n" + "="*80)
    print("生成详细货物清单")
    print("="*80)

    all_cargo_details = []

    for idx, row in df_results.iterrows():
        area_id = row['服务区ID']
        area_name = row['服务区名称']
        uav_type = row['选用机型']

        print(f"\n处理 {area_id} - {area_name}...")

        # 获取该服务区的货箱
        area_cargos = loader.get_cargos_for_area(area_id)
        if area_cargos.empty:
            continue

        # 获取无人机参数
        uav = loader.get_uav_transport(uav_type)

        # 计算到该服务区的能耗
        depot = loader.get_depot()
        area = loader.get_service_area(area_id)

        energy_model = EnergyModel(uav, depot, area)

        # 准备背包问题数据
        weights = area_cargos['weight_kg'].values
        volumes = area_cargos['volume_m3'].values
        values = area_cargos['priority'].values

        # 为每个货物计算增加的能耗（载货能耗）
        distances_km = energy_model.horizontal_distance / 1000
        energies = []
        for w in weights:
            # 简化：假设载货增加的能耗与重量成正比
            base_energy = energy_model.calculate_total_energy(0)
            loaded_energy = energy_model.calculate_total_energy(w)
            delta_energy = loaded_energy - base_energy
            energies.append(delta_energy)

        energies = np.array(energies)

        # 计算容量
        W_kg = uav['max_load_kg']
        V_m3 = uav['max_volume_m3']
        battery_kwh = uav['battery_capacity_kwh']
        reserve_pct = uav['battery_reserve_pct']
        E_kwh = battery_kwh * (1 - reserve_pct)

        # 求解背包问题
        solution = knapsack_3d(
            weights=weights,
            volumes=volumes,
            energies=energies,
            values=values,
            W=W_kg,
            V=V_m3,
            E=E_kwh
        )

        # 提取选中的货箱
        selected_indices = solution['selected_items']
        selected_cargos = area_cargos.iloc[selected_indices].copy()

        # 添加到详细列表
        for _, cargo in selected_cargos.iterrows():
            all_cargo_details.append({
                '服务区ID': area_id,
                '服务区名称': area_name,
                '货箱编号': cargo['cargo_id'],
                '类型': cargo['type'],
                '重量(kg)': cargo['weight_kg'],
                '体积(m3)': cargo['volume_m3'],
                '优先级': cargo['priority'],
                '批次': cargo['batch'],
                '时限(分钟)': cargo['time_limit_min'],
                '选用机型': uav_type
            })

        print(f"  选中货箱: {len(selected_cargos)} 件")
        print(f"  货箱编号: {', '.join(selected_cargos['cargo_id'].astype(str).tolist())}")

    df_cargo_details = pd.DataFrame(all_cargo_details)

    # 保存到Excel
    output_file = Path("结果/问题一_详细货物清单.xlsx")
    df_cargo_details.to_excel(output_file, index=False)
    print(f"\n详细货物清单已保存: {output_file}")

    return df_cargo_details


def plot_service_area_map(loader, df_results):
    """
    绘制服务区分布地图
    """
    print("\n生成服务区分布地图...")

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()

    fig, ax = plt.subplots(figsize=(12, 10))

    # 绘制调度中心
    ax.scatter(depot['longitude'], depot['latitude'],
               s=300, c='red', marker='*',
               label='调度中心', zorder=5, edgecolors='black', linewidths=2)
    ax.text(depot['longitude'], depot['latitude'] + 0.002,
            depot['name'], fontsize=10, ha='center', weight='bold')

    # 绘制服务区
    colors = {'A': 'skyblue', 'B': 'lightgreen', 'C': 'orange'}

    for _, row in df_results.iterrows():
        area_id = row['服务区ID']
        area = loader.get_service_area(area_id)
        uav_type = row['选用机型']

        ax.scatter(area['longitude'], area['latitude'],
                   s=200, c=colors.get(uav_type, 'gray'),
                   marker='o', edgecolors='black', linewidths=1,
                   alpha=0.7, zorder=3)

        # 绘制连线
        ax.plot([depot['longitude'], area['longitude']],
                [depot['latitude'], area['latitude']],
                'k--', alpha=0.3, linewidth=1, zorder=1)

        # 标注服务区
        ax.text(area['longitude'], area['latitude'] + 0.001,
                f"{area_id}\n{row['货物数']}件",
                fontsize=8, ha='center', va='bottom')

    # 图例
    legend_elements = [
        mpatches.Patch(color='red', label='调度中心'),
        mpatches.Patch(color=colors['A'], label='A型无人机服务区'),
        mpatches.Patch(color=colors['B'], label='B型无人机服务区'),
        mpatches.Patch(color=colors['C'], label='C型无人机服务区')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)

    ax.set_xlabel('经度', fontsize=12)
    ax.set_ylabel('纬度', fontsize=12)
    ax.set_title('问题一 - 服务区配送方案分布图', fontsize=14, weight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal')

    plt.tight_layout()
    output_file = Path("结果/图表/问题一_服务区分布图.png")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"服务区分布图已保存: {output_file}")
    plt.close()


def plot_uav_comparison(df_results):
    """
    绘制无人机性能对比图
    """
    print("\n生成无人机性能对比图...")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 按机型汇总
    summary = df_results.groupby('选用机型').agg({
        '服务区ID': 'count',
        '总重量(kg)': 'sum',
        '总能耗(kWh)': 'sum',
        '飞行时间(分钟)': 'sum'
    }).reset_index()
    summary.columns = ['机型', '服务次数', '总载重', '总能耗', '总飞行时间']

    # 1. 机型使用次数
    ax = axes[0, 0]
    bars = ax.bar(summary['机型'], summary['服务次数'],
                   color=['skyblue', 'lightgreen', 'orange'][:len(summary)])
    ax.set_ylabel('服务次数', fontsize=11)
    ax.set_title('(a) 各机型使用次数', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom', fontsize=10)

    # 2. 总载重对比
    ax = axes[0, 1]
    bars = ax.bar(summary['机型'], summary['总载重'],
                   color=['skyblue', 'lightgreen', 'orange'][:len(summary)])
    ax.set_ylabel('总载重 (kg)', fontsize=11)
    ax.set_title('(b) 各机型总载重', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10)

    # 3. 总能耗对比
    ax = axes[1, 0]
    bars = ax.bar(summary['机型'], summary['总能耗'],
                   color=['skyblue', 'lightgreen', 'orange'][:len(summary)])
    ax.set_ylabel('总能耗 (kWh)', fontsize=11)
    ax.set_title('(c) 各机型总能耗', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}', ha='center', va='bottom', fontsize=10)

    # 4. 总飞行时间对比
    ax = axes[1, 1]
    bars = ax.bar(summary['机型'], summary['总飞行时间'],
                   color=['skyblue', 'lightgreen', 'orange'][:len(summary)])
    ax.set_ylabel('总飞行时间 (分钟)', fontsize=11)
    ax.set_title('(d) 各机型总飞行时间', fontsize=12, weight='bold')
    ax.grid(axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.0f}', ha='center', va='bottom', fontsize=10)

    plt.suptitle('问题一 - 无人机性能对比分析', fontsize=14, weight='bold', y=0.995)
    plt.tight_layout()

    output_file = Path("结果/图表/问题一_无人机性能对比.png")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"性能对比图已保存: {output_file}")
    plt.close()


def plot_resource_utilization(df_results):
    """
    绘制资源利用率分析图
    """
    print("\n生成资源利用率分析图...")

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # 1. 重量利用率分布
    ax = axes[0]
    weight_util = df_results['重量利用率(%)']
    ax.hist(weight_util, bins=10, color='skyblue', edgecolor='black', alpha=0.7)
    ax.axvline(weight_util.mean(), color='red', linestyle='--',
               linewidth=2, label=f'平均值: {weight_util.mean():.1f}%')
    ax.set_xlabel('重量利用率 (%)', fontsize=11)
    ax.set_ylabel('服务区数量', fontsize=11)
    ax.set_title('(a) 重量利用率分布', fontsize=12, weight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # 2. 体积利用率分布
    ax = axes[1]
    volume_util = df_results['体积利用率(%)']
    ax.hist(volume_util, bins=10, color='lightgreen', edgecolor='black', alpha=0.7)
    ax.axvline(volume_util.mean(), color='red', linestyle='--',
               linewidth=2, label=f'平均值: {volume_util.mean():.1f}%')
    ax.set_xlabel('体积利用率 (%)', fontsize=11)
    ax.set_ylabel('服务区数量', fontsize=11)
    ax.set_title('(b) 体积利用率分布', fontsize=12, weight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # 3. 能耗利用率分布
    ax = axes[2]
    energy_util = df_results['能耗利用率(%)']
    ax.hist(energy_util, bins=10, color='orange', edgecolor='black', alpha=0.7)
    ax.axvline(energy_util.mean(), color='red', linestyle='--',
               linewidth=2, label=f'平均值: {energy_util.mean():.1f}%')
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


def generate_summary_report(loader, df_results, df_cargo_details):
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
    report.append(f"配送货物总数: {len(df_cargo_details)} 件")
    report.append(f"总载重: {df_results['总重量(kg)'].sum():.2f} kg")
    report.append(f"总体积: {df_results['总体积(m3)'].sum():.4f} m3")
    report.append(f"总能耗: {df_results['总能耗(kWh)'].sum():.2f} kWh")
    total_time_min = df_results['飞行时间(分钟)'].sum()
    report.append(f"总飞行时间: {total_time_min:.1f} 分钟 ({total_time_min/60:.2f} 小时)")
    report.append("")

    # 2. 机型使用统计
    report.append("二、机型使用统计")
    report.append("-" * 80)
    uav_counts = df_results['选用机型'].value_counts()
    for uav_type in ['A', 'B', 'C']:
        if uav_type in uav_counts.index:
            count = uav_counts[uav_type]
            pct = count / len(df_results) * 100
            report.append(f"{uav_type}型无人机: {count} 次 ({pct:.1f}%)")
    report.append("")

    # 3. 资源利用率统计
    report.append("三、资源利用率统计")
    report.append("-" * 80)
    report.append(f"平均重量利用率: {df_results['重量利用率(%)'].mean():.1f}%")
    report.append(f"平均体积利用率: {df_results['体积利用率(%)'].mean():.1f}%")
    report.append(f"平均能耗利用率: {df_results['能耗利用率(%)'].mean():.1f}%")
    report.append("")

    # 4. 货物类型统计
    report.append("四、货物类型统计")
    report.append("-" * 80)
    type_counts = df_cargo_details['类型'].value_counts()
    for cargo_type, count in type_counts.items():
        pct = count / len(df_cargo_details) * 100
        report.append(f"{cargo_type}: {count} 件 ({pct:.1f}%)")
    report.append("")

    # 5. 详细服务区列表
    report.append("五、详细服务区配送方案")
    report.append("-" * 80)
    for idx, row in df_results.iterrows():
        area_id = row['服务区ID']
        area_name = row['服务区名称']
        uav_type = row['选用机型']
        num_cargos = row['货物数']

        report.append(f"\n[{area_id}] {area_name}")
        report.append(f"  选用机型: {uav_type}型")
        report.append(f"  货物数量: {num_cargos} 件")
        report.append(f"  总重量: {row['总重量(kg)']:.2f} kg (利用率: {row['重量利用率(%)']:.1f}%)")
        report.append(f"  总体积: {row['总体积(m3)']:.4f} m3 (利用率: {row['体积利用率(%)']:.1f}%)")
        report.append(f"  总能耗: {row['总能耗(kWh)']:.2f} kWh (利用率: {row['能耗利用率(%)']:.1f}%)")
        report.append(f"  飞行时间: {row['飞行时间(分钟)']:.1f} 分钟")

        # 列出具体货箱
        area_cargos = df_cargo_details[df_cargo_details['服务区ID'] == area_id]
        cargo_ids = area_cargos['货箱编号'].tolist()
        report.append(f"  货箱编号: {', '.join(map(str, cargo_ids))}")

    report.append("")
    report.append("="*80)
    report.append("报告生成完毕")
    report.append("="*80)

    # 保存报告
    output_file = Path("结果/问题一_完整报告.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))

    print(f"\n完整报告已保存: {output_file}")

    # 同时打印到控制台
    print("\n" + '\n'.join(report))


def main():
    """主函数"""
    print("="*80)
    print("问题一增强 - 详细分析与可视化")
    print("="*80)

    # 1. 加载数据
    print("\n[步骤1] 加载数据...")
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 2. 加载求解结果
    print("\n[步骤2] 加载问题一求解结果...")
    df_results = load_solution_results()
    print(f"已加载 {len(df_results)} 个服务区的配送方案")

    # 3. 生成详细货物清单
    print("\n[步骤3] 生成详细货物清单...")
    df_cargo_details = generate_detailed_cargo_list(loader, df_results)

    # 4. 绘制可视化图表
    print("\n[步骤4] 生成可视化图表...")
    plot_service_area_map(loader, df_results)
    plot_uav_comparison(df_results)
    plot_resource_utilization(df_results)

    # 5. 生成汇总报告
    print("\n[步骤5] 生成汇总报告...")
    generate_summary_report(loader, df_results, df_cargo_details)

    print("\n" + "="*80)
    print("问题一增强完成！")
    print("="*80)
    print("\n生成的文件:")
    print("  1. 结果/问题一_详细货物清单.xlsx - 每个服务区的具体货箱")
    print("  2. 结果/图表/问题一_服务区分布图.png - 地理分布可视化")
    print("  3. 结果/图表/问题一_无人机性能对比.png - 机型对比分析")
    print("  4. 结果/图表/问题一_资源利用率.png - 利用率分析")
    print("  5. 结果/问题一_完整报告.txt - 详细文字报告")
    print("="*80)


if __name__ == "__main__":
    main()

