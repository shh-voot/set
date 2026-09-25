#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""问题2双层优化主程序

外层：NSGA-II多目标遗传算法
内层：CP-SAT约束规划精确调度

目标：
- 架次数 ≈ 25
- 总能耗 ≈ 70 kWh
- 完成时间 ≈ 150 min (2.5小时)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# 设置路径
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]  # D:\claude\华为杯\D题
WORK = PROJECT / "解题-gpt"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(WORK / "代码"))

from src.battery.charging_model_correct import calculate_charging_time
from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader

# 导入优化器
from cpsat_scheduler import CPSATScheduler
from nsga2_optimizer import NSGAIIOptimizer
from energy_utils import direct_mission


def load_official_data():
    """加载官方数据"""
    print("加载官方数据...")
    data_dir = PROJECT / "数据" / "无人机应急物资运输基础数据"
    dem_dir = PROJECT / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"

    loader = DataLoader(str(data_dir))
    loader.load_all()

    cargo = loader.get_cargos().copy()
    cargo_by_id = cargo.set_index("货箱编号", drop=False)

    types = {
        r["type"]: r.to_dict()
        for _, r in loader.get_uav_types().iterrows()
    }

    areas = {
        r["id"]: r.to_dict()
        for _, r in loader.get_service_areas().iterrows()
    }

    depot = loader.get_depot()

    dem = DEMLoader(str(next(dem_dir.glob("*.mat"))))
    dem.load()

    print(f"  货箱数量: {len(cargo)}")
    print(f"  服务区数量: {len(areas)}")
    print(f"  机型数量: {len(types)}")
    for typ, params in types.items():
        print(f"    {typ}: {params['count']}架, {params['battery_count']}组电池")

    return cargo, cargo_by_id, types, areas, depot, dem


def write_result(pareto_front, types, output_dir):
    """输出帕累托前沿的所有方案"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 汇总表
    summary_rows = []

    print(f"\n调试信息: 帕累托前沿共有 {len(pareto_front)} 个解")
    feasible_count = sum(1 for ind in pareto_front if ind.feasible)
    has_missions_count = sum(1 for ind in pareto_front if ind.missions is not None)
    print(f"  可行解数量: {feasible_count}")
    print(f"  有missions的解数量: {has_missions_count}")

    for idx, individual in enumerate(pareto_front):
        print(f"  解{idx+1}: feasible={individual.feasible}, has_missions={individual.missions is not None}")
        if not individual.feasible or individual.missions is None:
            continue

        missions = individual.missions
        cargo_deliveries = individual.cargo_deliveries

        num_missions, total_energy, makespan = individual.objectives

        # 写入详细结果
        mission_df = pd.DataFrame(missions)
        mission_df["cargo_ids"] = mission_df["cargo_ids"].apply(
            lambda x: ",".join(x) if isinstance(x, list) else x
        )

        cargo_df = pd.DataFrame(cargo_deliveries)

        # 资源使用统计
        inv = []
        for typ, params in types.items():
            typ_missions = mission_df[mission_df.uav_type == typ]
            uids = sorted(typ_missions["uav_id"].unique())
            bids = sorted(typ_missions["battery_id"].unique())

            inv.append({
                "type": typ,
                "official_uav": int(params["count"]),
                "used_uav": len(uids),
                "used_uav_ids": ",".join(uids),
                "official_battery": int(params["battery_count"]),
                "used_battery": len(bids),
                "used_battery_ids": ",".join(bids),
                "full_charge_time_min": params["full_charge_time_min"]
            })

        inv_df = pd.DataFrame(inv)

        # 校验信息
        late_count = int((~cargo_df.on_time).sum())
        total_tardiness = sum(
            max(0.0, r["delivery_min"] - r["deadline_min"])
            for _, r in cargo_df.iterrows()
        )

        check_df = pd.DataFrame({
            "metric": [
                "missions", "cargo_count", "unique_cargo_count",
                "completion_min", "late_cargo_count", "total_tardiness_min",
                "total_energy_kwh", "algorithm"
            ],
            "value": [
                len(mission_df),
                len(cargo_df),
                cargo_df.cargo_id.nunique(),
                makespan,
                late_count,
                total_tardiness,
                total_energy,
                "NSGA-II + CP-SAT"
            ]
        })

        # 写入Excel
        output_file = output_dir / f"方案{idx + 1:02d}_架次{int(num_missions)}_能耗{total_energy:.1f}kWh_时间{makespan:.1f}min.xlsx"
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            mission_df.to_excel(writer, sheet_name="架次调度", index=False)
            cargo_df.to_excel(writer, sheet_name="逐箱时限", index=False)
            inv_df.to_excel(writer, sheet_name="资源核验", index=False)
            check_df.to_excel(writer, sheet_name="校验", index=False)

        print(f"  方案{idx + 1}: 架次{int(num_missions)}, 能耗{total_energy:.2f}kWh, 时间{makespan:.2f}min")
        print(f"    -> {output_file.name}")

        summary_rows.append({
            "方案编号": idx + 1,
            "架次数": int(num_missions),
            "总能耗(kWh)": round(total_energy, 2),
            "完成时间(min)": round(makespan, 2),
            "完成时间(h)": round(makespan / 60, 2),
            "准时率(%)": 100.0 if late_count == 0 else round((1 - late_count / len(cargo_df)) * 100, 2),
            "迟到货箱数": late_count,
            "文件名": output_file.name
        })

    # 写入汇总表
    summary_df = pd.DataFrame(summary_rows)
    summary_file = output_dir / "帕累托前沿汇总.xlsx"
    summary_df.to_excel(summary_file, index=False)
    print(f"\n汇总表: {summary_file}")

    return summary_df


def select_best_solution(pareto_front, target_missions=25, target_energy=70, target_time=150):
    """从帕累托前沿选择最接近目标的方案

    使用加权距离选择：
    - 架次数目标: 25
    - 能耗目标: 70 kWh
    - 时间目标: 150 min
    """
    best_ind = None
    best_distance = float('inf')

    for ind in pareto_front:
        if not ind.feasible:
            continue

        num_missions, total_energy, makespan = ind.objectives

        # 归一化距离（权重相等）
        distance = (
            abs(num_missions - target_missions) / target_missions +
            abs(total_energy - target_energy) / target_energy +
            abs(makespan - target_time) / target_time
        )

        if distance < best_distance:
            best_distance = distance
            best_ind = ind

    return best_ind


def main():
    """主程序"""
    print("=" * 60)
    print("问题2双层优化 (NSGA-II + CP-SAT)")
    print("=" * 60)

    # 加载数据
    cargo, cargo_by_id, types, areas, depot, dem = load_official_data()

    # 创建CP-SAT调度器
    print("\n创建CP-SAT调度器...")
    cpsat_scheduler = CPSATScheduler(
        types=types,
        cargo_by_id=cargo_by_id,
        time_limit_sec=60  # 每个调度问题限时60秒
    )

    # 创建NSGA-II优化器
    print("\n创建NSGA-II优化器...")
    optimizer = NSGAIIOptimizer(
        cargo_by_id=cargo_by_id,
        types=types,
        areas=areas,
        depot=depot,
        dem=dem,
        direct_mission_func=direct_mission,
        cpsat_scheduler=cpsat_scheduler,
        pop_size=30,  # 种群大小（可调整）
        max_generations=50,  # 最大代数（可调整）
        crossover_prob=0.9,
        mutation_prob=0.3,
        seed=42
    )

    # 执行优化
    print("\n" + "=" * 60)
    print("开始优化...")
    print("=" * 60)

    pareto_front = optimizer.optimize()

    # 输出结果
    print("\n" + "=" * 60)
    print(f"优化完成！共找到 {len(pareto_front)} 个帕累托最优解")
    print("=" * 60)

    if not pareto_front:
        print("未找到可行解！")
        return

    # 显示帕累托前沿
    print("\n帕累托前沿：")
    feasible_front = [ind for ind in pareto_front if ind.feasible]
    for idx, ind in enumerate(feasible_front):
        num_missions, total_energy, makespan = ind.objectives
        print(f"  方案{idx + 1}: 架次={int(num_missions)}, "
              f"能耗={total_energy:.2f}kWh, 时间={makespan:.2f}min ({makespan/60:.2f}h)")

    # 写入结果文件
    output_dir = WORK / "问题2优化claude" / "结果"
    print(f"\n保存结果到: {output_dir}")
    summary_df = write_result(feasible_front, types, output_dir)

    # 选择最佳方案
    print("\n" + "=" * 60)
    print("选择最接近目标的方案 (架次≈25, 能耗≈70kWh, 时间≈150min)")
    print("=" * 60)

    best_ind = select_best_solution(
        feasible_front,
        target_missions=25,
        target_energy=70,
        target_time=150
    )

    if best_ind:
        num_missions, total_energy, makespan = best_ind.objectives
        print(f"\n推荐方案:")
        print(f"  架次数: {int(num_missions)}")
        print(f"  总能耗: {total_energy:.2f} kWh")
        print(f"  完成时间: {makespan:.2f} min ({makespan/60:.2f} 小时)")

        # 与目标对比
        print(f"\n与目标对比:")
        print(f"  架次数: {int(num_missions)} / 25 ({(num_missions/25-1)*100:+.1f}%)")
        print(f"  总能耗: {total_energy:.2f} / 70.0 ({(total_energy/70-1)*100:+.1f}%)")
        print(f"  完成时间: {makespan:.2f} / 150.0 ({(makespan/150-1)*100:+.1f}%)")

        # 机型使用情况
        if best_ind.missions:
            mission_df = pd.DataFrame(best_ind.missions)
            print(f"\n机型使用情况:")
            for typ in mission_df.uav_type.unique():
                typ_missions = mission_df[mission_df.uav_type == typ]
                uavs = typ_missions.uav_id.nunique()
                batteries = typ_missions.battery_id.nunique()
                missions_count = len(typ_missions)
                print(f"  {typ}型: {missions_count}架次, {uavs}架无人机, {batteries}组电池")

    print("\n优化完成！")


if __name__ == "__main__":
    main()
