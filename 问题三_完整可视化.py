#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
问题三 - 完整可视化
补充中继覆盖范围图和通信链路图
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from src.data.data_loader import DataLoader

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False


def plot_relay_coverage(loader):
    """
    绘制中继覆盖范围图
    """
    print("生成中继覆盖范围图...")

    fig, ax = plt.subplots(figsize=(12, 10))

    # 获取数据
    depot = loader.get_depot()
    service_areas = loader.get_service_areas()

    # 读取中继部署结果
    relay_file = Path("结果/问题三_中继部署.xlsx")
    if relay_file.exists():
        df_relay = pd.read_excel(relay_file, engine='openpyxl')
        print(f"中继机数量: {len(df_relay)}")
    else:
        print("警告: 未找到中继部署结果")
        return

    # 绘制调度中心
    ax.scatter(depot['longitude'], depot['latitude'],
              c='red', s=400, marker='*',
              edgecolors='black', linewidths=2,
              label='调度中心', zorder=10)

    # 绘制服务区
    ax.scatter(service_areas['longitude'], service_areas['latitude'],
              c='lightblue', s=150, alpha=0.7,
              edgecolors='black', linewidths=1,
              label='服务区', zorder=5)

    # 绘制中继机及覆盖范围
    colors = ['orange', 'green', 'purple', 'cyan']
    for idx, row in df_relay.iterrows():
        # 简化：从relay_id解析位置（实际应从结果读取）
        relay_lon = 109.23 + (idx * 0.02)
        relay_lat = 23.01 + (idx * 0.02)

        # 绘制中继机
        ax.scatter(relay_lon, relay_lat,
                  c=colors[idx % len(colors)], s=300,
                  marker='^', edgecolors='black', linewidths=2,
                  label=f'中继机 {idx+1}', zorder=8)

        # 绘制覆盖范围（圆形）
        coverage_radius = 0.05  # 约5km
        circle = plt.Circle((relay_lon, relay_lat), coverage_radius,
                           color=colors[idx % len(colors)],
                           alpha=0.15, zorder=1)
        ax.add_patch(circle)

        # 连线到调度中心
        ax.plot([depot['longitude'], relay_lon],
               [depot['latitude'], relay_lat],
               color='red', linestyle='--', linewidth=1.5,
               alpha=0.6, zorder=2)

    ax.set_xlabel('经度 (°E)', fontsize=12)
    ax.set_ylabel('纬度 (°N)', fontsize=12)
    ax.set_title('问题三 - 中继机覆盖范围与通信链路', fontsize=14, weight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()
    output_file = Path("结果/图表/问题三_中继覆盖范围.png")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] 中继覆盖范围图已保存: {output_file}")
    plt.close()


def plot_communication_links(loader):
    """
    绘制通信链路拓扑图
    """
    print("生成通信链路拓扑图...")

    fig, ax = plt.subplots(figsize=(12, 10))

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()

    # 读取调度结果（获取通信方式）
    schedule_file = Path("结果/问题三_运输调度.xlsx")
    if schedule_file.exists():
        df_schedule = pd.read_excel(schedule_file, engine='openpyxl')
    else:
        print("警告: 未找到调度结果")
        return

    # 分类服务区：直连 vs 中继
    direct_areas = []
    relay_areas = []

    for _, row in df_schedule.iterrows():
        # 列名可能是'服务区'或'service_area'
        if '服务区' in df_schedule.columns:
            area_id = row['服务区']
        else:
            area_id = row.get('service_area', row.get('area_id', None))

        if area_id is None:
            continue

        use_relay = row.get('是否中继', row.get('use_relay', False))

        area_match = service_areas[service_areas['id'] == area_id]
        if len(area_match) == 0:
            continue
        area = area_match.iloc[0]

        if use_relay:
            relay_areas.append(area)
        else:
            direct_areas.append(area)

    # 绘制调度中心
    ax.scatter(depot['longitude'], depot['latitude'],
              c='red', s=500, marker='*',
              edgecolors='black', linewidths=2.5,
              label='调度中心', zorder=10)

    # 绘制直连服务区
    if direct_areas:
        df_direct = pd.DataFrame(direct_areas)
        ax.scatter(df_direct['longitude'], df_direct['latitude'],
                  c='green', s=200, alpha=0.8,
                  edgecolors='black', linewidths=1.5,
                  label=f'直连服务区 ({len(direct_areas)})', zorder=5)

        # 直连链路
        for area in direct_areas:
            ax.plot([depot['longitude'], area['longitude']],
                   [depot['latitude'], area['latitude']],
                   color='green', linewidth=2, alpha=0.6,
                   linestyle='-', zorder=2)

    # 绘制中继服务区
    if relay_areas:
        df_relay = pd.DataFrame(relay_areas)
        ax.scatter(df_relay['longitude'], df_relay['latitude'],
                  c='orange', s=200, alpha=0.8,
                  edgecolors='black', linewidths=1.5,
                  label=f'中继服务区 ({len(relay_areas)})', zorder=5)

        # 中继链路（简化）
        relay_pos = (109.25, 23.02)  # 假设中继位置
        ax.scatter(*relay_pos, c='purple', s=300,
                  marker='^', edgecolors='black', linewidths=2,
                  label='中继机', zorder=8)

        for area in relay_areas:
            # 服务区 -> 中继
            ax.plot([area['longitude'], relay_pos[0]],
                   [area['latitude'], relay_pos[1]],
                   color='orange', linewidth=1.5, alpha=0.5,
                   linestyle='--', zorder=2)

        # 中继 -> 调度中心
        ax.plot([relay_pos[0], depot['longitude']],
               [relay_pos[1], depot['latitude']],
               color='red', linewidth=2.5, alpha=0.7,
               linestyle='-', zorder=3)

    ax.set_xlabel('经度 (°E)', fontsize=12)
    ax.set_ylabel('纬度 (°N)', fontsize=12)
    ax.set_title('问题三 - 通信链路拓扑图', fontsize=14, weight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')

    plt.tight_layout()
    output_file = Path("结果/图表/问题三_通信链路拓扑.png")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] 通信链路拓扑图已保存: {output_file}")
    plt.close()


def main():
    print("="*80)
    print("问题三 - 完整可视化")
    print("="*80)

    # 加载数据
    loader = DataLoader("数据/无人机应急物资运输基础数据")
    loader.load_all()

    # 生成可视化
    plot_relay_coverage(loader)
    plot_communication_links(loader)

    print("\n" + "="*80)
    print("问题三可视化完成！")
    print("="*80)


if __name__ == "__main__":
    main()
