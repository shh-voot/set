#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速运行脚本 - 小规模优化测试

使用较小的种群和代数进行快速测试（约5-10分钟）
适合验证算法和调试
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

# 设置路径
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
WORK = PROJECT / "解题-gpt"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(WORK / "代码"))

from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from solve_problem1_18trips import direct_mission
from cpsat_scheduler import CPSATScheduler
from nsga2_optimizer import NSGAIIOptimizer


def main():
    print("=" * 60)
    print("快速运行 - 小规模测试")
    print("=" * 60)

    # 加载数据
    print("\n加载数据...")
    data_dir = PROJECT / "数据" / "无人机应急物资运输基础数据"
    dem_dir = PROJECT / "数据" / "镇龙乡地理空间数据" / "镇龙乡及周边地理数据" / "数字高程模型数据（DEM）"

    loader = DataLoader(str(data_dir))
    loader.load_all()
    cargo_by_id = loader.get_cargos().set_index("货箱编号", drop=False)
    types = {r["type"]: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
    areas = {r["id"]: r.to_dict() for _, r in loader.get_service_areas().iterrows()}
    depot = loader.get_depot()
    dem = DEMLoader(str(next(dem_dir.glob("*.mat"))))
    dem.load()

    # 创建优化器（小规模参数）
    print("\n创建优化器（快速模式）...")
    cpsat_scheduler = CPSATScheduler(
        types=types,
        cargo_by_id=cargo_by_id,
        time_limit_sec=60  # 增加到60秒，提高可行解比例
    )

    optimizer = NSGAIIOptimizer(
        cargo_by_id=cargo_by_id,
        types=types,
        areas=areas,
        depot=depot,
        dem=dem,
        direct_mission_func=direct_mission,
        cpsat_scheduler=cpsat_scheduler,
        pop_size=20,  # 增加到20个体
        max_generations=20,  # 增加到20代
        crossover_prob=0.9,
        mutation_prob=0.3,
        seed=42
    )

    # 运行优化
    print("\n开始优化（预计15-20分钟）...")
    print("=" * 60)
    pareto_front = optimizer.optimize()

    # 输出结果
    print("\n" + "=" * 60)
    print(f"优化完成！找到 {len(pareto_front)} 个解")
    print("=" * 60)

    feasible = [ind for ind in pareto_front if ind.feasible]
    if not feasible:
        print("未找到可行解！")
        return

    print("\n帕累托前沿：")
    for idx, ind in enumerate(feasible):
        n, e, t = ind.objectives
        print(f"  方案{idx + 1}: 架次={int(n)}, 能耗={e:.2f}kWh, 时间={t:.2f}min ({t/60:.2f}h)")

    # 保存最优解
    best = min(feasible, key=lambda x: sum(x.objectives))
    n, e, t = best.objectives
    print(f"\n最优方案: 架次={int(n)}, 能耗={e:.2f}kWh, 时间={t:.2f}min")

    output_dir = WORK / "问题2优化claude" / "结果"
    output_dir.mkdir(parents=True, exist_ok=True)

    if best.missions:
        mission_df = pd.DataFrame(best.missions)
        mission_df["cargo_ids"] = mission_df["cargo_ids"].apply(
            lambda x: ",".join(x) if isinstance(x, list) else x
        )
        output_file = output_dir / f"快速测试_架次{int(n)}.xlsx"

        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            mission_df.to_excel(writer, sheet_name="架次调度", index=False)
            pd.DataFrame(best.cargo_deliveries).to_excel(writer, sheet_name="逐箱时限", index=False)

        print(f"\n结果已保存: {output_file}")

    print("\n完成！如需更好的结果，请运行:")
    print("  python main_optimize.py")


if __name__ == "__main__":
    main()
