#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为杯D题 - 数据读取脚本
读取所有Excel数据文件并显示结构
"""

import pandas as pd
import os

def read_all_data():
    """读取所有数据文件"""

    data_dir = "数据/无人机应急物资运输基础数据"

    files = {
        'depots': '调度中心与服务区.xlsx',
        'uav_transport': '运输无人机数据.xlsx',
        'demands': '物资需求与配送时限.xlsx',
        'uav_relay': '中继无人机数据.xlsx',
        'comm_params': '通信链路参数.xlsx'
    }

    data = {}

    for key, filename in files.items():
        filepath = os.path.join(data_dir, filename)
        if os.path.exists(filepath):
            print("\n" + "="*60)
            print(f"读取: {filename}")
            print("="*60)

            try:
                # 读取Excel文件
                xl = pd.ExcelFile(filepath)
                print(f"工作表: {xl.sheet_names}")

                sheets = {}
                for sheet_name in xl.sheet_names:
                    df = pd.read_excel(filepath, sheet_name=sheet_name)
                    sheets[sheet_name] = df

                    print(f"\n工作表: {sheet_name}")
                    print(f"形状: {df.shape} (行数×列数)")
                    print(f"列名: {list(df.columns)}")
                    print("\n前5行数据:")
                    print(df.head().to_string(index=False))

                data[key] = sheets

            except Exception as e:
                print(f"错误: {e}")

    return data

if __name__ == "__main__":
    data = read_all_data()

    print("\n" + "="*60)
    print("数据读取完成!")
    print("="*60)
