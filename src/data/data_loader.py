#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
华为杯D题 - 数据加载模块
读取所有Excel数据文件，提供统一的数据访问接口
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class DataLoader:
    """数据加载器 - 统一管理所有数据文件"""

    def __init__(self, data_dir: str = "数据/无人机应急物资运输基础数据"):
        self.data_dir = Path(data_dir)
        self.depots = None
        self.service_areas = None
        self.uav_transport = None
        self.uav_relay = None
        self.cargos = None
        self.comm_params = None

    def load_all(self):
        """加载所有数据"""
        print("开始加载数据...")
        self.load_depots_and_service_areas()
        self.load_uav_transport()
        self.load_uav_relay()
        self.load_cargo_demands()
        self.load_comm_params()
        print("数据加载完成!")

    def load_depots_and_service_areas(self):
        """加载调度中心和服务区数据"""
        filepath = self.data_dir / "调度中心与服务区.xlsx"
        df = pd.read_excel(filepath, header=None)

        # 找到调度中心数据行 (查找包含'O'的行，应该是O01)
        depot_row = None
        for i in range(len(df)):
            if pd.notna(df.iloc[i, 0]) and str(df.iloc[i, 0]).startswith('O'):
                depot_row = i
                break

        if depot_row is not None:
            self.depots = {
                'id': df.iloc[depot_row, 0],
                'name': df.iloc[depot_row, 1],
                'longitude': float(df.iloc[depot_row, 2]),
                'latitude': float(df.iloc[depot_row, 3]),
                'altitude': float(df.iloc[depot_row, 4])
            }
        else:
            # 默认值
            self.depots = {
                'id': 'O01',
                'name': '镇龙乡调度中心',
                'longitude': 109.230852,
                'latitude': 23.008509,
                'altitude': 127.7
            }

        # 找到服务区数据 (查找包含'S'开头的行)
        service_data = []
        for i in range(len(df)):
            if pd.notna(df.iloc[i, 0]) and str(df.iloc[i, 0]).startswith('S'):
                try:
                    service_data.append({
                        'id': df.iloc[i, 0],
                        'name': df.iloc[i, 1],
                        'longitude': float(df.iloc[i, 2]),
                        'latitude': float(df.iloc[i, 3]),
                        'altitude': float(df.iloc[i, 4]),
                        'population': int(df.iloc[i, 5]) if pd.notna(df.iloc[i, 5]) else 0
                    })
                except Exception as e:
                    continue

        self.service_areas = pd.DataFrame(service_data)
        print(f"[OK] 加载调度中心: {self.depots['id']}")
        print(f"[OK] 加载服务区: {len(self.service_areas)} 个")

    def load_uav_transport(self):
        """
        加载运输无人机数据

        Excel列结构(从第2行开始,第0列开始计数):
        0: 类型编号 (A/B/C)
        1: 无人机名称
        2: 单次载重(kg) - 题目中的"最大载荷"
        3: 载货体积(kg) - 实际是体积单位应该是m³但写成了kg
        4: 满载装货飞行(m³) - 实际应该是最大航程相关
        5: 计划巡航速度(m/s)
        6: 运输标准航程(m) - 最大航程
        7: 运输标准载重(m) - 数据有误,实际应该参考列2
        8: 电池容量(kWh)
        9: 电池安全余量(%)
        10: 单位货物装载时间(s)
        11: 每次装货时间(s)
        12: 抵达与起飞准备时间(s)
        13: 每次卸货后离开时间(s)
        14: 爬升加速度(m/s)
        15: 爬升降落速度(m/s)
        16: 爬升能耗效率
        17: 降落能耗效率
        """
        filepath = self.data_dir / "运输无人机数据.xlsx"
        df = pd.read_excel(filepath, header=None)

        # 查找A/B/C型无人机的行 (只取前3个有效数据行)
        uav_data = []
        for i in range(len(df)):
            if pd.notna(df.iloc[i, 0]) and str(df.iloc[i, 0]) in ['A', 'B', 'C']:
                # 检查是否有完整的数据 (至少要有速度和航程信息)
                if pd.isna(df.iloc[i, 5]) or pd.isna(df.iloc[i, 6]):
                    continue

                try:
                    # 重新理解数据:
                    # 列6实际是最大航程(米),需要转换为km
                    # 列8是电池容量(kWh)
                    # 需要推算巡航功率: P = E / (R/v)

                    max_range_m = float(df.iloc[i, 6])  # 最大航程(米)
                    cruise_speed_ms = float(df.iloc[i, 5])  # 巡航速度(m/s)
                    battery_kwh = float(df.iloc[i, 8])  # 电池容量(kWh)
                    battery_reserve = float(df.iloc[i, 9]) / 100.0  # 电池预留(转为小数)

                    # 可用电池容量
                    usable_battery = battery_kwh * (1 - battery_reserve)

                    # 巡航时间 = 航程 / 速度
                    cruise_time_h = (max_range_m / cruise_speed_ms) / 3600.0

                    # 巡航功率 = 可用电量 / 巡航时间
                    cruise_power_kw = usable_battery / cruise_time_h if cruise_time_h > 0 else 0

                    # 读取充电时间（赛题第57-59行规定的等效完全充电时间）
                    # 对于A/B型，查看col11（第12列）
                    # 对于C型，查看col13（第14列）
                    uav_type = df.iloc[i, 0]
                    if uav_type in ['A', 'B']:
                        full_charge_time_min = float(df.iloc[i, 11]) if pd.notna(df.iloc[i, 11]) else 30
                    else:  # C型
                        full_charge_time_min = float(df.iloc[i, 13]) if pd.notna(df.iloc[i, 13]) else 36

                    uav_data.append({
                        'type': df.iloc[i, 0],
                        'name': df.iloc[i, 1] if pd.notna(df.iloc[i, 1]) else f"{df.iloc[i, 0]}型无人机",
                        'max_load_kg': float(df.iloc[i, 2]),  # 单次载重
                        'max_volume_m3': float(df.iloc[i, 4]),  # 满载装货飞行(实际是体积)
                        'max_range_km': max_range_m / 1000.0,  # 转换为km
                        'cruise_speed_ms': cruise_speed_ms,
                        'cruise_power_kw': cruise_power_kw,  # 推算的巡航功率
                        'battery_capacity_kwh': battery_kwh,
                        'battery_reserve_pct': battery_reserve,
                        'full_charge_time_min': full_charge_time_min,  # 等效完全充电时间
                        'takeoff_time_s': float(df.iloc[i, 10]) if pd.notna(df.iloc[i, 10]) else 20,
                        'landing_time_s': float(df.iloc[i, 12]) if pd.notna(df.iloc[i, 12]) else 20,
                        'load_unload_time_s': float(df.iloc[i, 11]) if pd.notna(df.iloc[i, 11]) else 30,
                        'ascent_speed_ms': float(df.iloc[i, 14]) if pd.notna(df.iloc[i, 14]) else 3,
                        'descent_speed_ms': float(df.iloc[i, 15]) if pd.notna(df.iloc[i, 15]) else 2.5,
                        'ascent_efficiency': float(df.iloc[i, 16]) if pd.notna(df.iloc[i, 16]) else 0.72,
                        'descent_efficiency': float(df.iloc[i, 17]) if pd.notna(df.iloc[i, 17]) else 0.0
                    })
                except Exception as e:
                    print(f"警告: 读取无人机第{i}行数据失败: {e}")
                    continue

        self.uav_transport = pd.DataFrame(uav_data)
        print(f"[OK] 加载运输无人机: {len(self.uav_transport)} 种机型")

        # 打印调试信息
        if len(self.uav_transport) > 0:
            for _, uav in self.uav_transport.iterrows():
                print(f"    {uav['type']}型: 载重={uav['max_load_kg']}kg, "
                      f"电池={uav['battery_capacity_kwh']}kWh, "
                      f"充电={uav['full_charge_time_min']}min, "
                      f"航程={uav['max_range_km']:.1f}km, "
                      f"功率≈{uav['cruise_power_kw']:.2f}kW")

    def load_uav_relay(self):
        """加载中继无人机数据"""
        filepath = self.data_dir / "中继无人机数据.xlsx"
        df = pd.read_excel(filepath, header=None)

        # 查找R型中继机的行
        for i in range(len(df)):
            if pd.notna(df.iloc[i, 0]) and str(df.iloc[i, 0]) == 'R':
                try:
                    self.uav_relay = {
                        'type': df.iloc[i, 0],
                        'name': df.iloc[i, 1] if pd.notna(df.iloc[i, 1]) else 'R型中继无人机',
                        'max_load_kg': float(df.iloc[i, 2]),
                        'relay_module_kg': float(df.iloc[i, 3]),
                        'cruise_speed_ms': float(df.iloc[i, 5]),
                        'cruise_power_kw': float(df.iloc[i, 6]),
                        'battery_capacity_kwh': float(df.iloc[i, 7]),
                        'hover_power_kw': float(df.iloc[i, 16]) if pd.notna(df.iloc[i, 16]) else 1.0,
                        'comm_power_kw': float(df.iloc[i, 17]) if pd.notna(df.iloc[i, 17]) else 0.05,
                        'hover_altitude_m': float(df.iloc[i, 18]) if pd.notna(df.iloc[i, 18]) else 300
                    }
                    print(f"[OK] 加载中继无人机: {self.uav_relay['type']}型")
                    return
                except Exception as e:
                    print(f"警告: 读取中继无人机数据失败: {e}")

        print("警告: 未找到中继无人机数据")

    def load_cargo_demands(self):
        """加载货物需求数据"""
        filepath = self.data_dir / "物资需求与配送时限.xlsx"

        # 读取第二个sheet (货箱清单) - 这里有详细的货箱数据
        try:
            df_boxes = pd.read_excel(filepath, sheet_name=1)
            print(f"[OK] 加载货箱清单: {len(df_boxes)} 个货箱")

            # 清洗数据 - 确保列名正确
            # 预期列: 货箱编号, 目的地, 物资类别, 单箱重量(kg), 单箱体积(m³), ...
            self.cargos = df_boxes

            # 打印前几行用于调试
            if len(df_boxes) > 0:
                print(f"    示例货箱: {df_boxes.iloc[0, 0] if len(df_boxes.columns) > 0 else 'N/A'}")

        except Exception as e:
            print(f"警告: 无法读取货箱清单: {e}")
            self.cargos = pd.DataFrame()

    def load_comm_params(self):
        """加载通信链路参数"""
        filepath = self.data_dir / "通信链路参数.xlsx"
        df = pd.read_excel(filepath, header=None)

        # 解析参数表 - 查找有数值的行
        params = {}
        for i in range(len(df)):
            # 尝试从第3列和第4列读取参数名和值
            if len(df.columns) >= 5:
                param_name = df.iloc[i, 3]  # 参数符号列
                param_value = df.iloc[i, 4]  # 数值列

                if pd.notna(param_name) and pd.notna(param_value):
                    try:
                        # 尝试转换为数字
                        params[str(param_name)] = float(param_value)
                    except:
                        # 保留字符串
                        params[str(param_name)] = param_value

        self.comm_params = params
        print(f"[OK] 加载通信参数: {len(params)} 个参数")

    def get_depot(self) -> Dict:
        """获取调度中心信息"""
        return self.depots

    def get_service_areas(self) -> pd.DataFrame:
        """获取所有服务区"""
        return self.service_areas

    def get_service_area(self, area_id: str) -> Dict:
        """获取指定服务区"""
        row = self.service_areas[self.service_areas['id'] == area_id]
        if len(row) > 0:
            return row.iloc[0].to_dict()
        return None

    def get_uav_types(self) -> pd.DataFrame:
        """获取所有无人机机型"""
        return self.uav_transport

    def get_uav_type(self, uav_type: str) -> Dict:
        """获取指定机型参数"""
        row = self.uav_transport[self.uav_transport['type'] == uav_type]
        if len(row) > 0:
            return row.iloc[0].to_dict()
        return None

    def get_relay_uav(self) -> Dict:
        """获取中继无人机参数"""
        return self.uav_relay

    def get_cargos(self) -> pd.DataFrame:
        """获取所有货物"""
        return self.cargos

    def get_comm_params(self) -> Dict:
        """获取通信参数"""
        return self.comm_params

    def summary(self):
        """打印数据概要"""
        print("\n" + "="*60)
        print("数据概要")
        print("="*60)
        print(f"调度中心: {self.depots['id']} - {self.depots['name']}")
        print(f"  位置: ({self.depots['longitude']:.6f}, {self.depots['latitude']:.6f})")
        print(f"  海拔: {self.depots['altitude']}m")
        print()
        print(f"服务区数量: {len(self.service_areas)}")
        print(f"  总人口: {self.service_areas['population'].sum()}")
        print(f"  平均海拔: {self.service_areas['altitude'].mean():.1f}m")
        print()
        print(f"运输无人机机型: {len(self.uav_transport)}")
        for _, uav in self.uav_transport.iterrows():
            print(f"  {uav['type']}型: 载重{uav['max_load_kg']}kg, 航程{uav['max_range_km']}km")
        print()
        if self.cargos is not None:
            print(f"货箱数量: {len(self.cargos)}")
        print()
        if self.comm_params:
            print(f"通信参数: {len(self.comm_params)} 项")
            for key, val in list(self.comm_params.items())[:3]:
                print(f"  {key}: {val}")
        print("="*60)


def test_data_loader():
    """测试数据加载"""
    loader = DataLoader()
    loader.load_all()
    loader.summary()

    # 测试访问接口
    print("\n测试数据访问:")
    print(f"A型无人机参数: {loader.get_uav_type('A')}")
    print(f"S001服务区: {loader.get_service_area('S001')}")


if __name__ == "__main__":
    test_data_loader()
