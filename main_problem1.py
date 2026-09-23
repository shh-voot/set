#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为杯D题 - 问题一主程序
为所有15个服务区求解最优配送方案
"""

import pandas as pd
from src.data.data_loader import DataLoader
from src.energy.energy_model import EnergyModel
from src.problem1.knapsack_solver import Problem1Solver


def solve_problem1():
    """求解问题一：为15个服务区分别设计单次配送方案"""

    print("="*80)
    print("问题一：单服务区无人机物资配送优化")
    print("="*80)

    # 1. 加载数据
    print("\n[步骤1] 加载基础数据...")
    loader = DataLoader()
    loader.load_all()

    depot = loader.get_depot()
    service_areas = loader.get_service_areas()
    uavs = loader.get_uav_types()
    cargos = loader.get_cargos()

    print(f"  调度中心: {depot['name']} @ ({depot['longitude']}, {depot['latitude']})")
    print(f"  服务区数量: {len(service_areas)}")
    print(f"  无人机类型: {len(uavs)}")
    print(f"  货物总数: {len(cargos)}")

    # 2. 初始化求解器
    print("\n[步骤2] 初始化求解器...")
    solver = Problem1Solver(loader)

    # 3. 为每个服务区求解
    print("\n[步骤3] 为每个服务区求解最优方案...")
    print("="*80)

    all_results = []

    for idx, area in service_areas.iterrows():
        area_id = area['id']
        area_name = area['name']

        print(f"\n{'='*80}")
        print(f"服务区 {idx+1}/{len(service_areas)}: {area_id} - {area_name}")
        print(f"{'='*80}")
        print(f"  坐标: ({area['longitude']:.6f}, {area['latitude']:.6f})")
        print(f"  海拔: {area['altitude']:.1f} m")
        print(f"  人口: {area['population']} 人")

        # 获取该服务区的货物需求
        area_cargos = cargos[cargos['服务区编号'] == area_id].copy()
        print(f"  需求货物数: {len(area_cargos)}")

        if len(area_cargos) == 0:
            print("  [跳过] 该服务区无货物需求")
            continue

        # 尝试每种无人机
        best_solution = None
        best_uav_type = None
        best_score = -1

        print(f"\n  尝试不同机型:")
        for _, uav in uavs.iterrows():
            uav_type = uav['type']
            result = solver.solve_single_trip(area_id, uav_type, method='greedy')

            if 'error' in result:
                print(f"    [{uav_type}型] 错误: {result['error']}")
                continue

            if result.get('is_feasible', False):
                # 评分: 优先级总和 / 能耗
                score = result['total_value'] / max(result['energy_kwh'], 0.1)
                print(f"    [{uav_type}型] 可行 - 货物:{result['num_cargos']}个, "
                      f"重量:{result['total_weight_kg']:.1f}kg, "
                      f"能耗:{result['energy_kwh']:.2f}kWh, "
                      f"评分:{score:.2f}")

                if score > best_score:
                    best_score = score
                    best_solution = result
                    best_uav_type = uav_type
            else:
                print(f"    [{uav_type}型] 不可行 - {result.get('reason', '未知原因')}")

        # 保存最优方案
        if best_solution:
            print(f"\n  [最优方案] {best_uav_type}型无人机")
            print(f"    配送货物: {best_solution['num_cargos']} 件")
            print(f"    总重量: {best_solution['total_weight_kg']:.2f} kg "
                  f"({best_solution['weight_utilization']*100:.1f}%)")
            print(f"    总体积: {best_solution['total_volume_m3']:.4f} m3 "
                  f"({best_solution['volume_utilization']*100:.1f}%)")
            print(f"    总能耗: {best_solution['energy_kwh']:.2f} kWh "
                  f"({best_solution['energy_utilization']*100:.1f}%)")
            print(f"    飞行时间: {best_solution['flight_time_min']:.1f} 分钟")
            print(f"    货物总价值: {best_solution['total_value']:.0f}")

            all_results.append({
                'area_id': area_id,
                'area_name': area_name,
                'uav_type': best_uav_type,
                'num_cargos': best_solution['num_cargos'],
                'total_weight': best_solution['total_weight_kg'],
                'total_volume': best_solution['total_volume_m3'],
                'total_energy': best_solution['energy_kwh'],
                'flight_time': best_solution['flight_time_min'],
                'total_value': best_solution['total_value']
            })
        else:
            print(f"\n  [无解] 所有机型均不可行")

    # 4. 汇总结果
    print(f"\n\n{'='*80}")
    print("问题一求解完成 - 结果汇总")
    print(f"{'='*80}\n")

    if all_results:
        df_results = pd.DataFrame(all_results)

        print(f"成功求解服务区数: {len(df_results)}/{len(service_areas)}")
        print(f"\n机型使用统计:")
        for uav_type in ['A', 'B', 'C']:
            count = len(df_results[df_results['uav_type'] == uav_type])
            if count > 0:
                print(f"  {uav_type}型: {count} 次")

        print(f"\n汇总数据:")
        print(f"  总配送货物数: {df_results['num_cargos'].sum()} 件")
        print(f"  总重量: {df_results['total_weight'].sum():.2f} kg")
        print(f"  总能耗: {df_results['total_energy'].sum():.2f} kWh")
        print(f"  总飞行时间: {df_results['flight_time'].sum():.1f} 分钟")

        # 保存结果
        output_file = "结果/问题一_配送方案.xlsx"
        df_results.to_excel(output_file, index=False)
        print(f"\n结果已保存至: {output_file}")
    else:
        print("未找到可行解！")

    print("\n" + "="*80)


if __name__ == "__main__":
    solve_problem1()
