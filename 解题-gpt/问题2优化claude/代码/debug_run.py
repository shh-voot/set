"""
调试版本 - 查看为什么没有可行解
"""
import sys
from pathlib import Path
import pandas as pd

# 设置路径
HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]  # D:\claude\华为杯\D题
WORK = PROJECT / "解题-gpt"
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(WORK / "代码"))

from src.data.data_loader import DataLoader
from src.terrain.dem_loader import DEMLoader
from src.energy.energy_model import calculate_energy_consumption
from cpsat_scheduler import CPSATScheduler
from nsga2_optimizer import NSGA2Optimizer

def load_data():
    """加载官方数据"""
    # 加载数据
    loader = DataLoader(PROJECT / "数据")
    cargo = loader.load_cargo()
    types = loader.load_uav_types()
    areas = loader.load_service_areas()
    depot = loader.load_depot()

    # 加载DEM
    dem_loader = DEMLoader(PROJECT / "数据")
    dem = dem_loader.load_dem()

    return cargo, types, areas, depot, dem


def direct_mission(destination, origin, params, cargo_list, dem):
    """简化的能耗计算"""
    from src.energy.energy_model import calculate_energy_consumption

    total_weight = sum(c['单箱质量（kg）'] for c in cargo_list)
    distance = ((destination['经度'] - origin['经度'])**2 +
                (destination['纬度'] - origin['纬度'])**2)**0.5 * 111000  # 转为米

    result = calculate_energy_consumption(
        uav_type=params,
        cargo_weight=total_weight,
        distance=distance,
        dem=dem,
        origin=origin,
        destination=destination
    )

    return result


def main():
    print("=" * 60)
    print("调试模式 - 查看初始种群可行性")
    print("=" * 60)

    # 加载数据
    print("\n加载官方数据...")
    cargo, types, areas, depot, dem = load_data()

    cargo_by_id = cargo.set_index('货箱编号')

    print(f"  货箱数量: {len(cargo)}")
    print(f"  服务区数量: {len(areas)}")
    print(f"  机型数量: {len(types)}")

    # 初始化调度器和优化器
    cpsat_scheduler = CPSATScheduler(types)

    optimizer = NSGA2Optimizer(
        cargo_by_id=cargo_by_id,
        types=types,
        areas=areas,
        depot=depot,
        dem=dem,
        direct_mission_func=direct_mission,
        cpsat_scheduler=cpsat_scheduler,
        pop_size=5,  # 只测试5个个体
        max_generations=1,
        seed=42
    )

    print("\n生成初始种群...")
    population = optimizer._initialize_population()

    print(f"\n评估 {len(population)} 个个体...")
    for i, ind in enumerate(population):
        print(f"\n个体 {i+1}:")
        print(f"  架次数: {len(ind.groups)}")

        # 逐个检查架次
        feasible_missions = 0
        for j, (group, route, uav_type) in enumerate(zip(ind.groups, ind.routes, ind.types)):
            metrics = optimizer._calculate_mission_metrics(group, route, uav_type)
            if metrics:
                feasible_missions += 1
                print(f"    架次{j+1}: ✓ 可行 ({len(group)}箱, {len(route)}站, {uav_type}型, "
                      f"能耗={metrics['energy_kwh']:.2f}kWh)")
            else:
                # 找出失败原因
                params = types[uav_type]
                total_weight = sum(cargo_by_id.loc[cid]['单箱质量（kg）'] for cid in group)
                total_volume = sum(cargo_by_id.loc[cid]['单箱体积（m³）'] for cid in group)

                reason = ""
                if total_weight > float(params['max_load_kg']):
                    reason = f"超重({total_weight:.1f}kg > {params['max_load_kg']}kg)"
                elif total_volume > float(params['max_volume_m3']):
                    reason = f"超体积({total_volume:.3f}m³ > {params['max_volume_m3']}m³)"
                else:
                    reason = "航程不可行或能耗超限"

                print(f"    架次{j+1}: ✗ 不可行 - {reason}")

        print(f"  可行架次: {feasible_missions}/{len(ind.groups)}")

        # 评估整体
        evaluated = optimizer.evaluate(ind)
        print(f"  整体可行性: {'✓ 可行' if evaluated.feasible else '✗ 不可行'}")
        if evaluated.feasible:
            print(f"  目标值: 架次={int(evaluated.objectives[0])}, "
                  f"能耗={evaluated.objectives[1]:.2f}kWh, "
                  f"时间={evaluated.objectives[2]:.2f}min")

if __name__ == "__main__":
    main()
