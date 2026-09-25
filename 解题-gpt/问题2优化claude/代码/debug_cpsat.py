#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试CP-SAT调度器 - 找出为什么无法找到可行解
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main_optimize import load_official_data
from energy_utils import direct_mission
from cpsat_scheduler import CPSATScheduler, Mission


def main():
    print("=" * 60)
    print("Debug CP-SAT Scheduler")
    print("=" * 60)

    # 1. Load data
    cargo, cargo_by_id, types, areas, depot, dem = load_official_data()

    # 2. Take only 5 cargos from same area
    print("\n选择测试数据...")
    cargo_ids = list(cargo_by_id.index)[:5]
    cargo_by_id_small = cargo_by_id.loc[cargo_ids].copy()

    print(f"货箱数: {len(cargo_by_id_small)}")

    # 打印每个货箱信息
    for cid in cargo_ids:
        row = cargo_by_id_small.loc[cid]
        print(f"  {cid}: 服务区={row.get('服务区编号', row.get('sid', '?'))}, "
              f"重量={row.get('重量(kg)', row.get('weight', '?'))}kg, "
              f"时限={row.get('时限(min)', row.get('deadline', '?'))}min")

    # 3. Create scheduler
    print("\n创建CP-SAT调度器...")
    scheduler = CPSATScheduler(
        types=types,
        cargo_by_id=cargo_by_id_small,
        time_limit_sec=300  # 给更多时间
    )

    # 4. 尝试一个简单的任务
    print("\n测试单个任务调度...")

    # 构造一个简单任务：用C型（最大载重）访问第一个服务区
    first_cargo = cargo_by_id_small.iloc[0]
    sid = first_cargo.get('服务区编号', first_cargo.get('sid'))

    # 获取服务区和无人机参数
    area = areas[sid]
    params_c = types['C']

    # 准备货箱信息（需要转换为字典列表）
    cargo_list = [{
        '单箱质量（kg）': first_cargo.get('重量(kg)', first_cargo.get('weight', 10))
    }]

    # 调用direct_mission: (area, depot, params, cargo, dem)
    result = direct_mission(area, depot, params_c, cargo_list, dem)

    print(f"\n任务信息:")
    print(f"  机型: C")
    print(f"  路线: O01 -> {sid} -> O01")
    print(f"  货箱: {cargo_ids[0]}")
    print(f"  载重: {result['payload_kg']:.1f}kg / {params_c['max_load_kg']}kg")
    print(f"  飞行时间: {result['flight_time_min']:.1f}min")
    print(f"  总时间: {result['total_time_min']:.1f}min")
    print(f"  能耗: {result['energy_kwh']:.2f}kWh")
    print(f"  可行: {result['feasible']}")

    if not result['feasible']:
        print(f"  能量余量: {result['energy_margin_kwh']:.2f}kWh")
        print(f"  航程余量: {result['range_margin_km']:.2f}km")
        print("任务不可行，无法继续测试调度")
        return

    # 构造mission字典供CP-SAT使用
    test_mission = Mission(
        mission_id=0,
        area_id=sid,
        uav_type='C',
        cargo_ids=[cargo_ids[0]],
        energy_kwh=result['energy_kwh'],
        duration_min=result['total_time_min'],
        delivery_offset_min=result['delivery_time_min'],
        deadline_min=first_cargo.get('deadline', first_cargo.get('时限要求（min）', 300))
    )

    # 5. 尝试调度这个任务
    print("\n调用CP-SAT求解...")
    result = scheduler.schedule([test_mission])

    # 6. 查看结果
    print("\n" + "=" * 60)
    if result['feasible']:
        print("✓ 找到可行解!")
        print(f"  架次数: {result['num_missions']}")
        print(f"  完成时间: {result['makespan']:.1f}min")

        if result['missions']:
            print(f"\n详细调度:")
            for m in result['missions']:
                print(f"  架次{m['mission_idx']}: "
                      f"无人机{m['drone_id']}, "
                      f"电池{m['battery_id']}, "
                      f"起飞{m['start_time']:.1f}min, "
                      f"降落{m['end_time']:.1f}min")
    else:
        print("✗ 无法找到可行解!")
        print("\n可能的原因:")
        print("  1. 资源数量不足（无人机或电池）")
        print("  2. 充电时间约束冲突")
        print("  3. 时间窗口约束无法满足")
        print("  4. CP-SAT求解器超时")

        # 打印资源信息
        print("\n资源配置:")
        for tname, tinfo in types.items():
            print(f"  {tname}型: {tinfo['count']}架, {tinfo['battery_count']}块电池")


if __name__ == '__main__':
    main()
