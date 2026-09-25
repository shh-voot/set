"""
能耗计算工具函数
从官方代码中提取的能耗模型
"""
import math
from typing import Dict, List, Tuple


def haversine_m(lonlat1: Tuple[float, float], lonlat2: Tuple[float, float]) -> float:
    """计算两点间的大圆距离（米）"""
    lon1, lat1 = lonlat1
    lon2, lat2 = lonlat2

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return 6371000 * c


def max_dem_height(dem, xy1: Tuple[float, float], xy2: Tuple[float, float],
                   horizontal_m: float) -> float:
    """计算路径上的最大地面高度"""
    try:
        lon1, lat1 = xy1
        lon2, lat2 = xy2

        # 采样点数
        n_samples = max(10, int(horizontal_m / 100))

        max_height = 0.0
        for i in range(n_samples + 1):
            t = i / n_samples
            lon = lon1 + t * (lon2 - lon1)
            lat = lat1 + t * (lat2 - lat1)

            height = dem.get_elevation(lat, lon)
            if height > max_height:
                max_height = height

        return max_height
    except:
        return 0.0


class EnergyModel:
    """能耗模型"""
    def __init__(self, params: Dict):
        self.params = params

    def equivalent_range_m(self, payload_kg: float) -> float:
        """计算等效航程（米）"""
        # 空载航程
        empty_range = self.params.get("empty_range_km", 50.0) * 1000
        # 满载航程
        full_range = self.params.get("full_load_range_km", 30.0) * 1000
        # 最大载荷
        max_load = self.params["max_load_kg"]

        # 线性插值
        if payload_kg <= 0:
            return empty_range
        elif payload_kg >= max_load:
            return full_range
        else:
            t = payload_kg / max_load
            return empty_range + t * (full_range - empty_range)


def leg_energy(params: Dict, horizontal_m: float, alt_start_m: float,
               alt_end_m: float) -> Tuple[float, float]:
    """计算单段飞行的能耗和时间

    Returns:
        (能耗_kWh, 时间_秒)
    """
    # 垂直速度和水平速度
    vertical_speed = params.get("vertical_speed_m_s", 3.0)
    cruise_speed = params.get("cruise_speed_m_s", 15.0)

    # 垂直距离和时间
    vertical_m = abs(alt_end_m - alt_start_m)
    vertical_time_s = vertical_m / vertical_speed if vertical_speed > 0 else 0

    # 水平时间
    horizontal_time_s = horizontal_m / cruise_speed if cruise_speed > 0 else 0

    total_time_s = vertical_time_s + horizontal_time_s

    # 能耗（简化模型：功率 × 时间）
    power_kw = params.get("hover_power_kw", 2.0)
    energy_kwh = power_kw * total_time_s / 3600

    return energy_kwh, total_time_s


def direct_mission(area: Dict, depot: Dict, params: Dict, cargo: List[Dict],
                   dem) -> Dict:
    """计算直飞任务的能耗和时间

    Args:
        area: 服务区信息
        depot: 起飞点信息
        params: 无人机参数
        cargo: 货箱列表
        dem: DEM数据加载器

    Returns:
        包含能耗、时间、可行性等信息的字典
    """
    # 坐标
    depot_xy = (depot["longitude"], depot["latitude"])
    area_xy = (area["longitude"], area["latitude"])

    # 水平距离
    horizontal_m = haversine_m(depot_xy, area_xy)

    # 地面最大高度
    try:
        ground_max = max_dem_height(dem, depot_xy, area_xy, horizontal_m)
    except:
        ground_max = 0.0

    # 巡航高度
    cruise_alt = ground_max + 50.0

    # 工作高度
    depot_work = depot.get("altitude", 0.0)
    area_work = area.get("altitude", 0.0) + 30.0

    # 载荷
    payload = sum(float(c.get("单箱质量（kg）", c.get("重量(kg)", c.get("weight_kg", 0)))) for c in cargo)

    # 去程：起飞 → 巡航 → 降落
    out1, t1 = leg_energy(params, 0.0, depot_work, cruise_alt)
    out2, t2 = leg_energy(params, horizontal_m, cruise_alt, cruise_alt)
    out3, t3 = leg_energy(params, 0.0, cruise_alt, area_work)

    # 返程：起飞 → 巡航 → 降落
    ret1, t4 = leg_energy(params, 0.0, area_work, cruise_alt)
    ret2, t5 = leg_energy(params, horizontal_m, cruise_alt, cruise_alt)
    ret3, t6 = leg_energy(params, 0.0, cruise_alt, depot_work)

    # 能耗模型
    model = EnergyModel(params)
    usable = params["battery_capacity_kwh"] * (1.0 - params.get("battery_reserve_pct", 0.1))

    # 巡航能耗（基于等效航程）
    out_cruise = horizontal_m / model.equivalent_range_m(payload) * usable
    ret_cruise = horizontal_m / model.equivalent_range_m(0.0) * usable

    # 总能耗
    energy = out1 + out_cruise + out3 + ret1 + ret_cruise + ret3

    # 飞行时间
    flight_s = t1 + t2 + t3 + t4 + t5 + t6

    # 操作时间
    operation_s = (
        params.get("prep_time_s", 60) +
        params.get("load_time_per_box_s", 10) * len(cargo) +
        params.get("handoff_base_s", 30) +
        params.get("handoff_per_box_s", 5) * len(cargo)
    )

    # 航程限制
    range_limit = model.equivalent_range_m(payload)

    # 可行性检查
    feasible = (energy <= usable + 1e-9) and (2.0 * horizontal_m <= range_limit + 1e-9)

    return {
        "energy_kwh": energy,
        "flight_time_min": flight_s / 60.0,
        "delivery_time_min": (operation_s + t1 + t2 + t3) / 60.0,
        "operation_time_min": operation_s / 60.0,
        "total_time_min": (flight_s + operation_s) / 60.0,
        "payload_kg": payload,
        "horizontal_distance_km": horizontal_m / 1000.0,
        "dem_max_ground_m": ground_max,
        "cruise_altitude_m": cruise_alt,
        "usable_energy_kwh": usable,
        "energy_margin_kwh": usable - energy,
        "equivalent_range_km": range_limit / 1000.0,
        "range_margin_km": range_limit / 1000.0 - 2.0 * horizontal_m / 1000.0,
        "feasible": feasible,
    }
