#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Authoritative Problem 1 solver.

It uses the official per-box list, the 30 m DEM and the Appendix 2
segment convention. Problem 1 ignores physical UAV inventory as required by
the statement, but still enforces type capacity, equivalent range and return
energy reserve for every direct O01 -> Si -> O01 mission.
"""

from pathlib import Path
import hashlib
import json
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.data.data_loader import DataLoader
from src.energy.energy_model import EnergyModel
from src.terrain.dem_loader import DEMLoader


ID = "\u8d27\u7bb1\u7f16\u53f7"
AREA = "\u670d\u52a1\u533a\u7f16\u53f7"
WEIGHT = "\u5355\u7bb1\u8d28\u91cf\uff08kg\uff09"
VOLUME = "\u5355\u7bb1\u4f53\u79ef\uff08m\u00b3\uff09"
PRIORITY = "\u5e94\u6025\u4f18\u5148\u7cfb\u6570"


def haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lon1, lat1 = a
    lon2, lat2 = b
    r = 6371000.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    q = (np.sin(dlat / 2) ** 2 +
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) *
         np.sin(dlon / 2) ** 2)
    return float(r * 2 * np.arctan2(np.sqrt(q), np.sqrt(1 - q)))


def max_dem_height(dem: DEMLoader, a: Tuple[float, float], b: Tuple[float, float],
                   horizontal_m: float) -> float:
    samples = max(2, int(np.ceil(horizontal_m / 30.0)) + 1)
    heights = []
    for t in np.linspace(0.0, 1.0, samples):
        h = dem.get_height(a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        if h is not None and np.isfinite(h):
            heights.append(float(h))
    if not heights:
        raise ValueError(f"DEM does not cover segment {a} -> {b}")
    return max(heights)


def leg_energy(params: Dict, horizontal_m: float, start_alt: float,
               end_alt: float) -> Tuple[float, float]:
    """Return (kWh, seconds) using Appendix 2's three phases."""
    delta = end_alt - start_alt
    climb_s = max(delta, 0.0) / params["ascent_speed_ms"]
    descend_s = max(-delta, 0.0) / params["descent_speed_ms"]
    cruise_s = horizontal_m / params["cruise_speed_ms"]
    p = params["cruise_power_kw"]
    energy = (
        p * cruise_s / 3600.0
        + p * params["ascent_efficiency"] * climb_s / 3600.0
        + p * params["descent_efficiency"] * descend_s / 3600.0
    )
    return energy, climb_s + cruise_s + descend_s


def direct_mission(area: Dict, depot: Dict, params: Dict, cargo: List[Dict],
                   dem: DEMLoader) -> Dict:
    depot_xy = (depot["longitude"], depot["latitude"])
    area_xy = (area["longitude"], area["latitude"])
    horizontal_m = haversine_m(depot_xy, area_xy)
    ground_max = max_dem_height(dem, depot_xy, area_xy, horizontal_m)
    cruise_alt = ground_max + 50.0
    depot_work = depot["altitude"]
    area_work = area["altitude"] + 30.0
    payload = sum(float(x[WEIGHT]) for x in cargo)

    out1, t1 = leg_energy(params, 0.0, depot_work, cruise_alt)
    out2, t2 = leg_energy(params, horizontal_m, cruise_alt, cruise_alt)
    out3, t3 = leg_energy(params, 0.0, cruise_alt, area_work)
    ret1, t4 = leg_energy(params, 0.0, area_work, cruise_alt)
    ret2, t5 = leg_energy(params, horizontal_m, cruise_alt, cruise_alt)
    ret3, t6 = leg_energy(params, 0.0, cruise_alt, depot_work)
    # Horizontal cruise energy follows the official empty/full-load
    # equivalent-range interpolation; the return leg is empty after delivery.
    model = EnergyModel(params)
    usable = params["battery_capacity_kwh"] * (1.0 - params["battery_reserve_pct"])
    out_cruise = horizontal_m / model.equivalent_range_m(payload) * usable
    ret_cruise = horizontal_m / model.equivalent_range_m(0.0) * usable
    energy = out1 + out_cruise + out3 + ret1 + ret_cruise + ret3
    flight_s = t1 + t2 + t3 + t4 + t5 + t6
    operation_s = (params["prep_time_s"] + params["load_time_per_box_s"] * len(cargo)
                   + params["handoff_base_s"] + params["handoff_per_box_s"] * len(cargo))
    usable = params["battery_capacity_kwh"] * (1.0 - params["battery_reserve_pct"])
    range_limit = model.equivalent_range_m(payload)
    return {
        "energy_kwh": energy,
        "flight_time_min": flight_s / 60.0,
        "delivery_time_min": (operation_s + t1 + t2 + t3) / 60.0,
        "operation_time_min": operation_s / 60.0,
        "total_time_min": (flight_s + operation_s) / 60.0,
        "payload_kg": payload,
        "total_volume_m3": sum(float(x[VOLUME]) for x in cargo),
        "horizontal_distance_km": horizontal_m / 1000.0,
        "dem_max_ground_m": ground_max,
        "cruise_altitude_m": cruise_alt,
        "usable_energy_kwh": usable,
        "energy_margin_kwh": usable - energy,
        "equivalent_range_km": range_limit / 1000.0,
        "range_margin_km": range_limit / 1000.0 - 2.0 * horizontal_m / 1000.0,
        "feasible": energy <= usable + 1e-9 and 2.0 * horizontal_m <= range_limit + 1e-9,
    }


def ffd(items: List[Dict], params: Dict, area: Dict, depot: Dict, dem: DEMLoader,
        key: str) -> List[List[Dict]]:
    ordered = sorted(items, key=lambda x: (x[key], x[WEIGHT], x[VOLUME]), reverse=True)
    bins: List[List[Dict]] = []
    for item in ordered:
        placed = False
        for bucket in bins:
            trial = bucket + [item]
            if sum(float(x[WEIGHT]) for x in trial) > params["max_load_kg"] + 1e-9:
                continue
            if sum(float(x[VOLUME]) for x in trial) > params["max_volume_m3"] + 1e-9:
                continue
            metrics = direct_mission(area, depot, params, trial, dem)
            if metrics["feasible"]:
                bucket.append(item)
                placed = True
                break
        if not placed:
            if not direct_mission(area, depot, params, [item], dem)["feasible"]:
                raise ValueError(f"Single box {item[ID]} is infeasible for {params['type']}")
            bins.append([item])
    return bins


def improve_bins(bins: List[List[Dict]], params: Dict, area: Dict, depot: Dict,
                 dem: DEMLoader) -> List[List[Dict]]:
    changed = True
    while changed:
        changed = False
        for i in range(len(bins) - 1, -1, -1):
            for item in list(bins[i]):
                for j in range(i):
                    trial = bins[j] + [item]
                    if (sum(float(x[WEIGHT]) for x in trial) <= params["max_load_kg"] + 1e-9 and
                            sum(float(x[VOLUME]) for x in trial) <= params["max_volume_m3"] + 1e-9 and
                            direct_mission(area, depot, params, trial, dem)["feasible"]):
                        bins[j].append(item)
                        bins[i].remove(item)
                        changed = True
                        break
                if changed:
                    break
            if changed:
                if not bins[i]:
                    bins.pop(i)
                break
    return bins


def improve_time_order(bins: List[List[Dict]], params: Dict, area: Dict,
                       depot: Dict, dem: DEMLoader) -> List[List[Dict]]:
    """Repack feasible bins to reduce the longest direct-mission time.

    This is a local post-processing pass: it never accepts a move that
    changes the number of trips or violates the official physical checks.
    """
    if len(bins) < 2:
        return bins
    changed = True
    while changed:
        changed = False
        current_max = max(direct_mission(area, depot, params, b, dem)["total_time_min"]
                          for b in bins)
        for i in range(len(bins)):
            for j in range(i + 1, len(bins)):
                for src, dst in ((i, j), (j, i)):
                    for item in list(bins[src]):
                        trial_src = [x for x in bins[src] if x is not item]
                        trial_dst = bins[dst] + [item]
                        if not trial_src:
                            continue
                        if sum(float(x[WEIGHT]) for x in trial_dst) > params["max_load_kg"] + 1e-9:
                            continue
                        if sum(float(x[VOLUME]) for x in trial_dst) > params["max_volume_m3"] + 1e-9:
                            continue
                        m_src = direct_mission(area, depot, params, trial_src, dem)
                        m_dst = direct_mission(area, depot, params, trial_dst, dem)
                        if not (m_src["feasible"] and m_dst["feasible"]):
                            continue
                        candidate_max = max(
                            [candidate["total_time_min"] for k, candidate in enumerate(
                                [direct_mission(area, depot, params, b, dem) for b in bins])
                             if k not in (src, dst)] +
                            [m_src["total_time_min"], m_dst["total_time_min"]]
                        )
                        if candidate_max + 1e-9 < current_max:
                            bins[src], bins[dst] = trial_src, trial_dst
                            changed = True
                            break
                    if changed:
                        break
                if changed:
                    break
            if changed:
                break
    return bins


def choose_type(bucket: List[Dict], area: Dict, depot: Dict,
                types: Dict[str, Dict], dem: DEMLoader) -> Tuple[str, Dict]:
    candidates = []
    for typ, params in types.items():
        if sum(float(x[WEIGHT]) for x in bucket) > params["max_load_kg"] + 1e-9:
            continue
        if sum(float(x[VOLUME]) for x in bucket) > params["max_volume_m3"] + 1e-9:
            continue
        m = direct_mission(area, depot, params, bucket, dem)
        if m["feasible"]:
            candidates.append((m["energy_kwh"], typ, m))
    if not candidates:
        raise ValueError("No feasible UAV type for a bucket")
    _, typ, metrics = min(candidates)
    return typ, metrics


def main():
    root = Path(__file__).parent
    data_dir = root / "\u6570\u636e" / "\u65e0\u4eba\u673a\u5e94\u6025\u7269\u8d44\u8fd0\u8f93\u57fa\u7840\u6570\u636e"
    dem_dir = root / "\u6570\u636e" / "\u9547\u9f99\u4e61\u5730\u7406\u7a7a\u95f4\u6570\u636e" / "\u9547\u9f99\u4e61\u53ca\u5468\u8fb9\u5730\u7406\u6570\u636e" / "\u6570\u5b57\u9ad8\u7a0b\u6a21\u578b\u6570\u636e\uff08DEM\uff09"
    dem_path = next(dem_dir.glob("*.mat"))
    loader = DataLoader(str(data_dir))
    loader.load_all()
    dem = DEMLoader(str(dem_path))
    dem.load()
    depot = loader.get_depot()
    areas = {r["id"]: r for _, r in loader.get_service_areas().iterrows()}
    cargo_df = loader.get_cargos().copy()
    types = {r["type"]: r.to_dict() for _, r in loader.get_uav_types().iterrows()}
    c_params = types["C"]

    # Deadline and priority-based ordering can reduce the longest delivery
    # time without changing official data or the number of feasible trips.
    strategies = [WEIGHT, VOLUME, PRIORITY, "_deadline", "_priority_deadline"]
    all_bins = {}
    for area_id, group in cargo_df.groupby(AREA, sort=True):
        items = group.to_dict("records")
        for item in items:
            first = str(item.get("是否首批保障", "")).strip() == "是"
            deadline = item.get("首批截止时间（s）") if first else item.get("期望送达时间（s）")
            item["_deadline"] = -float(deadline) if pd.notna(deadline) else 0.0
            item["_priority_deadline"] = (float(item.get(PRIORITY, 0.0)), item["_deadline"])
        best = None
        for key in strategies:
            bins = ffd(items, c_params, areas[area_id], depot, dem, key)
            bins = improve_bins(bins, c_params, areas[area_id], depot, dem)
            bins = improve_time_order(bins, c_params, areas[area_id], depot, dem)
            score = (len(bins), sum(direct_mission(areas[area_id], depot, c_params, b, dem)["energy_kwh"] for b in bins))
            if best is None or score < best[0]:
                best = (score, bins)
        all_bins[area_id] = best[1]

    records = []
    validation = []
    trip_id = 1
    for area_id, bins in all_bins.items():
        area = areas[area_id]
        for bucket in bins:
            typ, metrics = choose_type(bucket, area, depot, types, dem)
            ids = [x[ID] for x in bucket]
            records.append({
                "trip_id": trip_id, "area_id": area_id, "uav_type": typ,
                "cargo_count": len(ids), "cargo_ids": ",".join(ids),
                "total_weight_kg": metrics["payload_kg"],
                "total_volume_m3": metrics["total_volume_m3"],
                "energy_kwh": metrics["energy_kwh"],
                "flight_time_min": metrics["flight_time_min"],
                "delivery_time_min": metrics["delivery_time_min"],
                "operation_time_min": metrics["operation_time_min"],
                "total_time_min": metrics["total_time_min"],
                "dem_max_ground_m": metrics["dem_max_ground_m"],
                "cruise_altitude_m": metrics["cruise_altitude_m"],
                "usable_energy_kwh": metrics["usable_energy_kwh"],
                "energy_margin_kwh": metrics["energy_margin_kwh"],
                "equivalent_range_km": metrics["equivalent_range_km"],
                "range_margin_km": metrics["range_margin_km"],
                "feasible": metrics["feasible"],
            })
            validation.extend({"cargo_id": x[ID], "trip_id": trip_id, "area_id": area_id, "uav_type": typ} for x in bucket)
            trip_id += 1

    result = pd.DataFrame(records)
    cargo_check = pd.DataFrame(validation)
    output_dir = root / "\u7ed3\u679c"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "\u95ee\u9898\u4e00_18\u67b6\u6b21\u65b9\u6848_\u4fee\u590d\u7248.xlsx"
    meta = pd.DataFrame({"key": ["target_trips", "actual_trips", "cargo_count", "unique_cargo_count", "all_feasible"],
                         "value": [18, len(result), len(cargo_check), cargo_check["cargo_id"].nunique(), bool(result["feasible"].all())]})
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="\u67b6\u6b21\u65b9\u6848", index=False)
        cargo_check.to_excel(writer, sheet_name="\u8d27\u7bb1\u6838\u9a8c", index=False)
        meta.to_excel(writer, sheet_name="\u6821\u9a8c", index=False)
    print(json.dumps({"output": str(output_file), "trips": len(result), "cargo_count": len(cargo_check),
                      "unique_cargo_count": int(cargo_check["cargo_id"].nunique()),
                      "all_feasible": bool(result["feasible"].all()),
                      "energy_kwh": float(result["energy_kwh"].sum())}, ensure_ascii=True))


if __name__ == "__main__":
    main()
