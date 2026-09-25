#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查DataFrame列名"""
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

    types_df = loader.get_uav_types()
    print("Types DataFrame columns:")
    print(types_df.columns.tolist())
    print("\nFirst row:")
    print(types_df.iloc[0].to_dict())

if __name__ == "__main__":
    main()
