#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单测试CP-SAT调度器"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
sys.path.insert(0, str(PROJECT))

from src.data.data_loader import DataLoader
from cpsat_scheduler import CPSATScheduler, Mission

def main():
    print("=== CP-SAT简单测试 ===\n")

    # 加载数据
    data_dir = PROJECT / "数据" / "无人机应急物资运输基础数据"
    loader = DataLoader(str(data_dir))
    loader.load_all()

    types_df = loader.get_uav_types()
    cargos_df = loader.get_cargos()

    # 创建cargo_by_id字典
    cargo_by_id = {row['货箱编号']: row for _, row in cargos_df.iterrows()}

    # 创建types字典（保留完整的类型信息）
    types = {}
    for _, row in types_df.iterrows():
        types[row['type']] = row.to_dict()

    # 创建调度器
    scheduler = CPSATScheduler(types, cargo_by_id, time_limit_sec=30)

    # 测试1: 单个简单任务
    print("测试1: 单个A型任务到S01")
    mission1 = Mission(
        mission_id="M001",
        area_id="S01",
        uav_type="A",
        cargo_ids=["C001"],
        energy_kwh=2.0,
        duration_min=20.0,
        delivery_offset_min=15.0,
        deadline_min=180.0
    )

    result1 = scheduler.schedule([mission1])
    print(f"结果: {'成功' if result1.success else '失败'}")
    if result1.success:
        print(f"  完成时间: {result1.makespan_min:.1f}分钟")
        print(f"  任务详情: {result1.missions[0]}")
    print()

    # 测试2: 两个不冲突的任务
    print("测试2: 两个A型任务（时间错开）")
    mission2 = Mission(
        mission_id="M002",
        area_id="S02",
        uav_type="A",
        cargo_ids=["C002"],
        energy_kwh=2.0,
        duration_min=20.0,
        delivery_offset_min=15.0,
        deadline_min=180.0
    )

    result2 = scheduler.schedule([mission1, mission2])
    print(f"结果: {'成功' if result2.success else '失败'}")
    if result2.success:
        print(f"  完成时间: {result2.makespan_min:.1f}分钟")
        print(f"  任务数: {len(result2.missions)}")
    else:
        print(f"  失败原因: 可能资源冲突")
    print()

    # 测试3: 5个任务（接近实际规模）
    print("测试3: 5个A型任务")
    missions = []
    for i in range(5):
        missions.append(Mission(
            mission_id=f"M{i+1:03d}",
            area_id=f"S{(i%10)+1:02d}",
            uav_type="A",
            cargo_ids=[f"C{i+1:03d}"],
            energy_kwh=2.0,
            duration_min=20.0,
            delivery_offset_min=15.0,
            deadline_min=180.0
        ))

    result3 = scheduler.schedule(missions)
    print(f"结果: {'成功' if result3.success else '失败'}")
    if result3.success:
        print(f"  完成时间: {result3.makespan_min:.1f}分钟")
        print(f"  任务数: {len(result3.missions)}")
        print(f"  准时率: {sum(1 for m in result3.missions if m['on_time']) / len(result3.missions) * 100:.1f}%")
    print()

    # 测试4: 10个任务（可能会失败）
    print("测试4: 10个混合型号任务")
    missions = []
    for i in range(10):
        typ = ["A", "B", "C"][i % 3]
        missions.append(Mission(
            mission_id=f"M{i+1:03d}",
            area_id=f"S{(i%10)+1:02d}",
            uav_type=typ,
            cargo_ids=[f"C{i+1:03d}"],
            energy_kwh=3.0,
            duration_min=25.0,
            delivery_offset_min=18.0,
            deadline_min=180.0
        ))

    result4 = scheduler.schedule(missions)
    print(f"结果: {'成功' if result4.success else '失败'}")
    if result4.success:
        print(f"  完成时间: {result4.makespan_min:.1f}分钟")
        print(f"  任务数: {len(result4.missions)}")
    print()

    print("=== 测试完成 ===")

if __name__ == "__main__":
    main()
