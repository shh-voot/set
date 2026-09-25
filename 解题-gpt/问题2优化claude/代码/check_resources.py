#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查资源配置"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT = HERE.parents[3]
sys.path.insert(0, str(PROJECT))

from src.data.data_loader import DataLoader

def main():
    data_dir = PROJECT / "数据" / "无人机应急物资运输基础数据"
    loader = DataLoader(str(data_dir))
    loader.load_all()

    print("=== 无人机资源配置 ===")
    types_df = loader.get_uav_types()
    for _, row in types_df.iterrows():
        print(f"型号 {row['type']}: {int(row['count'])}架无人机, {int(row['battery_count'])}块电池, 充电时间{row['full_charge_time_min']:.1f}分钟")

    print("\n=== 货箱统计 ===")
    cargo_df = loader.get_cargos()
    print(f"总货箱数: {len(cargo_df)}")
    print(f"总重量: {cargo_df['重量/kg'].sum():.2f} kg")

    print("\n=== 服务区统计 ===")
    areas_df = loader.get_service_areas()
    print(f"服务区数量: {len(areas_df)}")

if __name__ == "__main__":
    main()
