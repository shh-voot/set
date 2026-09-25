#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared official mission construction and fleet simulation for Problem 2."""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from src.battery.charging_model_correct import calculate_charging_time
from solve_problem1_18trips import AREA, ID, VOLUME, WEIGHT, direct_mission

FIRST = "是否首批保障"
FIRST_DEADLINE = "首批截止时间（s）"
EXPECTED_DEADLINE = "期望送达时间（s）"


def deadline_seconds(row):
    if str(row.get(FIRST, "")).strip() == "是" and pd.notna(row.get(FIRST_DEADLINE)):
        return float(row[FIRST_DEADLINE])
    return float(row[EXPECTED_DEADLINE])


def _pack(items, params, area, depot, dem):
    ordered = sorted(items, key=lambda x: (float(x[WEIGHT]), float(x[VOLUME])), reverse=True)
    bins: List[list] = []
    for item in ordered:
        placed = False
        for bucket in bins:
            trial = bucket + [item]
            if sum(float(x[WEIGHT]) for x in trial) > float(params["max_load_kg"]) + 1e-9:
                continue
            if sum(float(x[VOLUME]) for x in trial) > float(params["max_volume_m3"]) + 1e-9:
                continue
            if direct_mission(area, depot, params, trial, dem)["feasible"]:
                bucket.append(item)
                placed = True
                break
        if not placed:
            metrics = direct_mission(area, depot, params, [item], dem)
            if not metrics["feasible"]:
                raise ValueError(f"官方货箱 {item[ID]} 对机型 {params['type']} 不可行")
            bins.append([item])
    return bins


def make_plans(items, types, area, depot, dem):
    """Create feasible type-specific packing plans using official constraints."""
    plans = {}
    for typ, params in types.items():
        try:
            bins = _pack(items, params, area, depot, dem)
        except ValueError:
            continue
        missions = []
        for bucket in bins:
            metrics = direct_mission(area, depot, params, bucket, dem)
            if not metrics["feasible"]:
                raise ValueError("组批算法返回了物理不可行架次")
            missions.append({
                "area_id": area["id"],
                "uav_type": typ,
                "cargo_ids": [str(x[ID]) for x in bucket],
                "cargo_count": len(bucket),
                "energy_kwh": float(metrics["energy_kwh"]),
                "duration_min": float(metrics["total_time_min"]),
                "delivery_offset_min": float(metrics["delivery_time_min"]),
            })
        plans[typ] = {"type": typ, "missions": missions}
    if not plans:
        raise ValueError(f"没有可行机型组批: {area['id']}")
    return plans


def simulate(chosen, types, cargo_by_id):
    """Simulate finite UAV and shared-battery pools with official recharge time."""
    tasks = []
    for group_index, group in enumerate(chosen):
        plan = group["plan"]
        for mission_index, mission in enumerate(plan["missions"]):
            tasks.append((group["deadline_min"], group_index, mission_index, mission))
    tasks.sort(key=lambda x: (x[0], x[1], x[2]))

    uavs, batteries = {}, {}
    for typ, params in types.items():
        uavs[typ] = [{"id": f"U{typ}{i + 1:02d}", "available": 0.0}
                     for i in range(int(params["count"]))]
        batteries[typ] = [{"id": f"{typ}-BAT-{i + 1:02d}", "available": 0.0}
                          for i in range(int(params["battery_count"]))]

    missions_out, cargo_out = [], []
    for mission_id, (deadline, _, _, mission) in enumerate(tasks, 1):
        typ = mission["uav_type"]
        params = types[typ]
        if not uavs[typ] or not batteries[typ]:
            raise ValueError(f"机型{typ}官方实体机或共享电池库存为零")
        uav = min(uavs[typ], key=lambda x: (x["available"], x["id"]))
        battery = min(batteries[typ], key=lambda x: (x["available"], x["id"]))
        start = max(uav["available"], battery["available"])
        end = start + mission["duration_min"]
        delivery = start + mission["delivery_offset_min"]
        capacity = float(params["battery_capacity_kwh"])
        reserve = float(params["battery_reserve_pct"])
        usable = capacity * (1.0 - reserve)
        energy = float(mission["energy_kwh"])
        if energy > usable + 1e-9:
            raise ValueError(f"架次能耗{energy:.6f}超出机型{typ}返航安全可用电量{usable:.6f}")
        soc_after = 1.0 - energy / capacity
        charge = float(calculate_charging_time(
            soc_after, 1.0, float(params["full_charge_time_min"])))
        uav["available"] = end
        battery["available"] = end + charge
        record = {**mission, "mission_id": mission_id, "uav_id": uav["id"],
                  "battery_id": battery["id"], "start_min": start,
                  "delivery_min": delivery, "end_min": end,
                  "deadline_min": float(deadline), "on_time": delivery <= deadline + 1e-9,
                  "soc_after": soc_after, "charge_min": charge}
        missions_out.append(record)
        for cargo_id in mission["cargo_ids"]:
            row = cargo_by_id.loc[cargo_id]
            box_deadline = deadline_seconds(row) / 60.0
            cargo_out.append({"cargo_id": cargo_id, "mission_id": mission_id,
                              "area_id": row[AREA], "delivery_min": delivery,
                              "deadline_min": box_deadline,
                              "on_time": delivery <= box_deadline + 1e-9})
    return missions_out, cargo_out
